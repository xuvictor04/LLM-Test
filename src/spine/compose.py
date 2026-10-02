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
sys.path made `import memory` return the old 654-line ./memory.py (archive/old-tree/ since 2026-09-28),
and `import data` would return the tracked ./data/ CORPUS DIRECTORY as a namespace package. src/data/
survives that collision only because src/data/__init__.py exists -- a regular package outranks a
namespace portion found earlier -- and it was confirmed present (0 bytes) before this file was written.
THE ENTRY POINT MUST DO `sys.path.insert(0, <root>/src)`, never `PYTHONPATH=src` from the root.

G9, THE TYPO NET. `environ` is a parameter and never a read: spine/lever.py is the only file in the
tree that may name os.environ (check O1), and build() warns loudly when it is handed None because
registry.unread_env then has no mapping to scan and a misspelled knob is silently the default. Pass
the process environment in from the entry point.
"""
import bisect
import contextlib
import hashlib

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
# package from a name this tuple already carries. SINCE 2026-09-27 (Q-EVAL-12) EVAL.pin_holdout
# draws each area's held-out window starts ONCE, per HALF, from
# rng_for("eval.holdout.<key>.<half>", seed) -- <key> is derive.stream_key(area), <half> is
# 'control' or 'report' -- at the 'probe' row, so that every reading in a run and across a resume
# scores the IDENTICAL byte windows and a verdict is computed on PAIRED differences; and the 'probe'
# row mints rng_for("eval.generate", seed) once per System for EVAL.generate's draws. Neither is
# minted at EVAL_RETENTION_EVERY=0. If a pinned stream advanced between readings the pairing would
# be lost silently -- which is why the draw happens once, at assembly, and rng.issued() is the
# surface that says which halves were drawn.
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
#
# EVERY CITATION IN THIS FILE WAS RE-RESOLVED AGAINST THE TREE ON 2026-09-04 AND TWENTY OF THEM
# NAMED THE WRONG SYMBOL. tests/test_ownership.py's O12 checks that a cited symbol EXISTS, and its
# own docstring states what it cannot reach -- "a citation naming a symbol that exists and is the
# wrong one" -- which is precisely the residue the line-number-to-symbol conversion left behind: a
# line number that had already gone stale converts to a CONFIDENTLY WRONG symbol, and every check
# stays green. What the twenty were: ckpt/api.py::install_save_signal for resume_source's "ONE
# SPELLING OF UNSET"; ckpt/api.py::check_geometry for new_retention's inert_reason; sig/api.py::
# warm_up, twice, for state_dict's SIDECAR; sig/api.py::train_step for warm_up's own "before the
# main loop"; data/api.py::open_areas for draw_stream's "dat.resample is read HERE"; data/api.py::
# data_plan for stream_state's "RETURNS: dict"; fabric/api.py::build for forward's live_domains;
# fabric/api.py::observe for contribution's baseline_logits_fn; fabric/api.py::manage for
# grow_check's two-sided stall test; lm/api.py::encode twice and lm/api.py::<module> once, all
# three for lm_loss; opt/api.py::scaled_backward for maybe_step's best_bpb Reading;
# opt/api.py::<module> for Horizon's "resolved ONCE at build()"; domains/api.py::manage for
# on_retokenize's signature; domains/api.py::observe.dom -- a LOCAL VARIABLE, which O12's AST walk
# admits as a symbol because it collects Assign targets -- for rekey's `encode`; world/api.py::
# manage for state_dict's plateau pair; train/api.py::new_clock for new_cadences' keyword-only
# `periods`; and train/api.py::<module> for bench_summary's throughput number. NONE of them was
# red. THE RULE THIS LEAVES, because no check can be made to carry it: when a citation is written
# or moved, OPEN THE CITED SYMBOL AND FIND THE SENTENCE IN IT. A citation is a claim about another
# file, and a claim nobody re-reads is how this file came to describe a mechanism that had moved.
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
    ("resume",    "CKPT",  "resume_source",   "() -- ONE spelling of unset (ckpt/api.py::resume_source); it "
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
    ("refuse",    "WORLD", "startup_refusals","(ctx_tokens=LM.ctx) -- with the RUN row above, a "
                                              "non-empty list RAISES RefusedRun here, before "
                                              "geometry and before any model tensor"),
    ("geometry",  "LM",    "resolve",         "() -- refuses width % heads and the ctx/pos_max "
                                              "overflow BEFORE a tensor is allocated, and since "
                                              "2026-09-28 a position scheme on the wrong arm -- "
                                              "LM_POS 'alibi' on the GRU, 'none' on the transformer "
                                              "(Q-LM-15)",
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
                                              "restored split. A refusal, with one admission (a "
                                              "record of key None, size 0 against a block now: "
                                              "Q-DATA-9, which the root warns of), and it yields "
                                              "nothing a later row takes: the record's area names "
                                              "land on Areas.parent_names, the areas its "
                                              "lineage drew on Areas.drawn, and the part of that "
                                              "list a record older than it could only assume on "
                                              "Areas.drawn_assumed (Q-DATA-10's review), in place"),
    ("vocab",     "TOK",   "build_vocabulary","(area_heads=Areas.bodies, seed=RUN.seed, soft_cap=CAP's "
                                              "`vocab_start` lever, readable off the frozen Config "
                                              "at any point -- NOT CAP's "
                                              "restored ceiling, which is thirty rows away and is "
                                              "the whole of M38; the body passes None today) -- "
                                              "MEASURES bytes/token on a fresh build and ADOPTS the "
                                              "parent's recorded value on a resume (the width SIG "
                                              "derives from it is fixed for the run), which three "
                                              "later rows need",
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
                                              "The two SIDECAR refusals below are ARMED as of "
                                              "2026-09-22 -- Q-CKPT-2's residue is closed, and its "
                                              "producer existed all along: both packages write a "
                                              "'sidecar' key into their OWN payload slice, which is "
                                              "where _sidecar reads it now. The GROWN population "
                                              "counts genuinely "
                                              "cannot be here (they need a built object) and are "
                                              "re-refused by WORLD.load_into and FAB.load_state_dict. "
                                              "ITS REPORT IS READ FOR ONE FIELD SINCE 2026-09-28 "
                                              "(Q-LM-15): lm.ctx and lm.pos_max are recorded "
                                              "MAY_WIDEN only at LM_CTX_WIDEN=1 and EXACT otherwise, "
                                              "and an lm.ctx the gate WIDENED is a declared "
                                              "widening, bound on System.ctx_widening for the "
                                              "segment row below and the startup notice; and the "
                                              "recorded lm.ctx is SIG's context wherever the "
                                              "checkpoint's LOOP carries no sig_ctx, bound on "
                                              "System.sig_ctx for the signature row (Q-LM-15's "
                                              "review)"),
    ("plan",      "DATA",  "data_plan",       "(epochs=RUN.epochs, win_tokens=LM.ctx, "
                                              "bytes_per_token=Vocabulary.bytes_per_token) -- the "
                                              "exposure gates, before a single step runs, and "
                                              "since 2026-09-28 the split each phase is laid in "
                                              "(Q-DATA-10), which under DATA_DRAW=replay gives each "
                                              "phase with a faded area its fixed rehearsal share",
                                              "plan -- the Plan both DATA.draw_stream rows take as "
                                              "their second positional. Plan carries NO length: "
                                              "the run's extent is MEASURED off the segmentation "
                                              "two rows down, never read off this record. Since "
                                              "2026-09-28 it carries the schedule's faded sets, "
                                              "Plan.faded per phase and Plan.parent_faded, which "
                                              "the loop's join _faded_ids hands FAB.manage as "
                                              "`faded` (Q-FAB-18), and the per-phase split both "
                                              "draw_stream rows lay and gauge, Plan.shares, with "
                                              "Plan.replay_faded naming the phases the 'replay' "
                                              "law lays by deficit (Q-DATA-10)"),
    ("focus",     "DATA",  "new_focus",       "(areas, plan, restored=Snapshot.payload['DATA']"
                                              ".get('focus')) -- THE SOURCE-RELIABILITY BOOK "
                                              "(2026-09-28, Proposal 04 SR3; Q-DATA-11), after the "
                                              "plan as 04 section 5 places it. At DATA_TRUST='off' "
                                              "it allocates nothing; 'loss' and 'loss+draw' are "
                                              "refused here with NotBuilt, before any tensor exists; "
                                              "at 'observe' it builds the int32 sketch and the claim "
                                              "table, or puts the checkpoint's book back and refuses "
                                              "a sketch or claim shape that moved by name. THE ONE "
                                              "PLACE THE BOOK IS RESTORED: DATA.restore_stream_state "
                                              "does not take focus= (04 section 5 moved it), because "
                                              "it runs at the resume's restore row, before this Plan "
                                              "exists",
                                              "focus -- the Focus record both DATA.claims_observe "
                                              "rows take and fill in place, carried on "
                                              "System.focus, and the book the C row's "
                                              "DATA.stream_state(focus=) writes into "
                                              "payload['DATA']"),
    ("stream",    "DATA",  "draw_stream",     "(areas, plan, epoch=Snapshot.epoch on a resume and 0 "
                                              "otherwise, seed=RUN.seed) -- THE RUN'S FIRST EPOCH's "
                                              "draw (it was epoch=0 unconditionally until "
                                              "2026-09-24, so a child resumed at epoch 1 under "
                                              "DATA_RESAMPLE=1 trained on epoch 0's stream; "
                                              "Q-RUN-11), and it is here rather than only at stage E "
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
                                              "(len(Segmentation.ids) - 1) // LM.ctx, never "
                                              "stream_bytes // ctx, which divides a BYTE budget by a "
                                              "TOKEN window and overstates it by the compression "
                                              "ratio. THE ROOT PRINTS ONE LINE AFTER THIS ROW, ON "
                                              "EVERY RUN: stream_bytes, len(Segmentation.ids), the "
                                              "measured bytes_per_token, windows_in_epoch and "
                                              "run_windows TOGETHER, so the ratio is checkable by "
                                              "eye. It is here and not in RUN.bench_summary, which "
                                              "can reach none of the five and returns None when "
                                              "bench is off (Q-DATA-8). A CONTINUING MID-EPOCH "
                                              "RESUME replays the checkpoint's segmentation log in "
                                              "place of this cut (Q-RUN-16), and first compares "
                                              "the redrawn stream's digest with the one the log's "
                                              "first event recorded, refusing a mismatch and a "
                                              "hold-out admission before the replay (Q-DATA-9) -- "
                                              "and, before either, a declared context widening "
                                              "(Q-LM-15), since its saved cursor counts windows of "
                                              "the parent's width",
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
                                              "LoadReport, which nothing takes as an argument: it "
                                              "is BOUND on System.lm_load and a refused one is "
                                              "appended to System.refusals, which stops the run. "
                                              "Until 2026-09-24 it was discarded and a refused "
                                              "restore trained the random model. Since 2026-09-28 "
                                              "(Q-LM-15) it refuses a moved LM_POS by name and, at "
                                              "LM_CTX_WIDEN=1, fits a larger context's learned "
                                              "position table by prefix"),
    ("signature", "SIG",   "build",           "(width_units=derive.signature_width_bytes(LM.ctx, "
                                              "bytes_per_token), alphabet_size, device, generator) "
                                              "-- the ONE width, resolved once, here, from "
                                              "System.sig_ctx, the LM_CTX the lineage's SIG was "
                                              "built at (Q-LM-15 and its review): this run's on a "
                                              "fresh run, and on a resume LOOP.sig_ctx or else the "
                                              "recorded lm.ctx, because a widened lineage's encoder "
                                              "was trained at the width it started at and SIG's "
                                              "restore refuses any other",
                                              "encode -- SIG.encode bound to the SigState by "
                                              "_sig_encode_fn, which is DOM.rekey's spelling for "
                                              "the same callable"),
    ("restore",   "SIG",   "load_state_dict", "(st, sd=Snapshot.payload['SIG'], "
                                              "sidecar=_sidecar(sysm, restored, 'SIG'), which reads "
                                              "the snapshot's "
                                              "recorded manifest under the key 'SIG'. NOTHING "
                                              "WRITES THAT KEY: the C rows record WORLD.geometry "
                                              "alone, so the sidecar was None on every real resume "
                                              "and the width_units/alphabet_size/space/d/mode "
                                              "refusal this row exists for was DISARMED. ARMED as "
                                              "of 2026-09-22: _sidecar reads Snapshot.payload["
                                              "'SIG']['sidecar'], which sig/api.py::state_dict has "
                                              "written all along and which carries all five fields "
                                              "-- the flat manifest carries three of them and "
                                              "cannot carry width_units at all. _sidecar still "
                                              "warns when a blob has no sidecar, which now means a "
                                              "blob older than the producer)"),
    ("probe",     "EVAL",  "pin_holdout",     "(blocks=Areas.holdout, seed=RUN.seed, window_bytes "
                                              "and prefix_bytes from the geometry LOOP.eval recorded "
                                              "when the snapshot carries one, else LM.ctx + 1 and "
                                              "SigState.width_units, the SIG width -- which is why "
                                              "this row follows SIG's restore row) -- THE RETENTION "
                                              "PROBE'S ONE DRAW (Q-EVAL-12): each area's held-out "
                                              "block split at its midpoint into control and report, "
                                              "each half's window starts drawn once from "
                                              "rng_for('eval.holdout.<key>.<half>', seed). EMPTY, "
                                              "with its reason and no stream minted, at "
                                              "EVAL_RETENTION_EVERY=0, with no block, or where no "
                                              "half can hold a window behind its prefix. The same "
                                              "stage mints rng_for('eval.generate', seed) ONCE PER "
                                              "System onto System.gen_rng where generation can run "
                                              "-- minted at R it would raise RngError on a second "
                                              "loop.run over one System -- and prints, never "
                                              "applies, two notices: EVAL_RETENTION_EVERY above "
                                              "160, the only measured cadence, and a phase the "
                                              "cadence would read fewer than five times "
                                              "(derive.readings_in, plus the phase-start read)",
                                              "probe_set -- EVAL.pin_holdout's ProbeSet, carried on "
                                              "System.probe_set, from which _holdout_units and "
                                              "_gen_prompts cut the units each reading and each "
                                              "generation takes"),
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
                                              "MAY_WIDEN; rank, dk, emb_hid, d_model and "
                                              "signature_dim EXACT. ARMED, like SIG's: "
                                              "fabric/api.py::state_dict writes the sidecar into "
                                              "Snapshot.payload['FAB']['sidecar'] and _sidecar "
                                              "reads it there (Q-CKPT-2). This row said the "
                                              "refusal was DISARMED and that FAB.state_dict did "
                                              "not claim to emit a sidecar, both false since "
                                              "2026-09-22; and until 2026-09-24 the sidecar's `dk` "
                                              "was d_model, so FAB's own refusal could not fire on "
                                              "FAB_DK and never saw FAB_EMB_HID -- the geometry "
                                              "gate was the only check of either)"),
    ("world",     "WORLD", "build",           "(d_model=LM.width, device, ctx_tokens=LM.ctx, rng)"),
    ("restore",   "WORLD", "load_into",       "(w, sd=Snapshot.payload['WORLD']) -- STRICTLY BEFORE "
                                              "OPT.build. WORLD.manage mints parameters mid-run "
                                              "through add_param_group, so a checkpoint taken after "
                                              "growth has more groups than a freshly built "
                                              "optimizer; replaying the population first is what "
                                              "lets OPT be built with the SAME group structure, and "
                                              "without it OPT's param_group_shape refusal fires on "
                                              "every resume of a run that ever grew (:4580-4599). "
                                              "THAT REFUSAL IS LIVE, AND THIS ROW SAID THE OPPOSITE "
                                              "UNTIL 2026-09-04. It read: the refusal 'is itself "
                                              "written against a field OPT.state_dict never says it "
                                              "writes ... so the ordering constraint this row exists "
                                              "for currently protects a guard that cannot fire'. All "
                                              "three halves of that are now false in the tree: "
                                              "opt/api.py::state_dict enumerates param_group_shape "
                                              "and says why ('A refusal armed against a value nothing "
                                              "writes is untrippable'), OptState declares the field, "
                                              "and opt/api.py::load_state refuses on it. The "
                                              "OPT.load_state row below already carried that "
                                              "correction (Q-OPT-4, 2026-09-02) while this one did "
                                              "not, so ONE TABLE SAID BOTH THINGS AT ONCE about one "
                                              "guard -- which is worse than either statement alone, "
                                              "because a reader who finds the contradiction cannot "
                                              "tell which row was re-read. The ordering constraint is "
                                              "unaffected either way and is why the row is here: it "
                                              "protects a guard that CAN fire, which is a stronger "
                                              "reason for the ordering, not a weaker one"),
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
                                              "is taken against the restored valve. IT DOES NOT "
                                              "TOUCH THE CAPS: until 2026-09-24 it wrote the saved "
                                              "caps over new_valve's answer on every unpinned arm, "
                                              "including under CAP_TARGETS=off, while new_valve's "
                                              "own checkpoint branch read a key nothing writes"),
    ("refuse",    "CAP",   "startup_refusals","(live_experts=Population.n_live) -- RAISES "
                                              "RefusedRun on a non-empty System.refusals, a "
                                              "refused LM restore's included; it needs the built "
                                              "population, so it follows allocation and precedes "
                                              "the optimizer and the SIG warm-up"),
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
                                              "of being untrippable. Its LoadReport is BOUND on "
                                              "System.opt_load and a refusal is appended to "
                                              "System.refusals; a dim-0 widening of a MAY_WIDEN "
                                              "tensor is restored with padded moments, not "
                                              "refused. continuing=System.resume_pos is not None "
                                              "(2026-09-27, Q-OPT-12): a continuing mid-epoch "
                                              "resume is the same run, so a session in progress or "
                                              "an off-arm run's declined horizon is restored "
                                              "verbatim, never re-anchored"),
    ("clock",     "RUN",   "new_clock",       "(batch_windows=OPT.batch_windows, accum=OPT.accum, "
                                              "resume_step, resume_epoch, "
                                              "resume_backwards=OptState.n_backward, "
                                              "resume_opt_steps=OptState.opt_step) -- the last two "
                                              "off the OPT restore row above, so the clock's step "
                                              "gate and OPT's evaluate one backward count (Q-RUN-9). "
                                              "A resume whose clock is already at epoch >= "
                                              "RUN_EPOCHS is REFUSED right after the epoch0 row "
                                              "(Q-RUN-10), and a mid-epoch one is WARNED with the "
                                              "windows it replays and the horizon it overruns",
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
    ("epoch0",    "RUN",   "RunClock.begin_epoch", "(windows_in_epoch=(len(Segmentation.ids)-1)//LM.ctx "
                                              "through _windows_in_epoch) -- epoch 0's length, "
                                              "MEASURED on the stream that actually exists. It is "
                                              "here and not only at stage E because the first epoch "
                                              "is never rolled into, and it needs the clock the row "
                                              "above builds. On a resume it is the RESUMED epoch's "
                                              "length, measured on the stream the `stream` row drew "
                                              "for that epoch (Q-RUN-11). The count is (len - 1) // "
                                              "ctx because a window needs ctx+1 ids (Q-RUN-12)"),
    ("warmup",    "SIG",   "warm_up",         "(stream=the epoch-0 unit stream in SIG's alphabet, "
                                              "seen_units=the WHOLE stream through "
                                              "_signature_units, opt=OPT's ENCODER optimizer) -- "
                                              "pre-loop by definition (sig/api.py::warm_up) and "
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
                                              "named neither (Q-OPT-7 RESOLVED (a)). ON A RESUME "
                                              "IT TRAINS NOTHING (Q-SIG-2): an encoder SIG's restore "
                                              "row put back is not warmed a second time, and the "
                                              "report returned is the parent's, rebuilt from the "
                                              "checkpointed curve and counters"),
    ("cadence",   "RUN",   "new_cadences",    "(periods={'curve': EVAL.curve_period(ev), "
                                              "'dom.manage': DOM.manage_period(dom), 'fab.manage': "
                                              "FAB.manage_period(fab), 'dom.rekey': "
                                              "MEM.rekey_period(mem), 'ckpt': CKPT.save_period(ck), "
                                              "'retention': EVAL.retention_period(ev), "
                                              "'data.trust': DATA.trust_period(dat), "
                                              "'progress': RUN.PROGRESS_WINDOWS}) "
                                              "-- the EIGHT gates the loop evaluates, each period "
                                              "supplied by the package that DECLARES its kind. Seven "
                                              "arrive through a typed accessor because a Config "
                                              "hands back a bare int for a Clock-unit LEVER; the "
                                              "eighth is RUN's own module CONSTANT, written "
                                              "units.Windows at its definition, so it needs no "
                                              "accessor and mints no entry point -- Q-RUN-1, "
                                              "RESOLVED 2026-09-02. 'progress' is the ONLY key here "
                                              "with no row of its own: no entry point prints the "
                                              "progress/ETA line, the loop driver does. "
                                              "new_cadences took no periods at all until 2026-08-30 "
                                              "while its docstring said every period is an "
                                              "argument; the CALL SITE was still passing none until "
                                              "this edit, which would have been a TypeError on the "
                                              "first compose() to reach this row -- a defect hidden "
                                              "behind an earlier stub, this file's oldest shape. "
                                              "THERE ARE THREE EARLIER STUBS AND NOT ONE: "
                                              "CAP.startup_refusals at row 31, RUN.new_clock at "
                                              "row 34 and RUN.RunClock.begin_epoch at row 35, each "
                                              "raising NotImplementedError before this row 37 is "
                                              "reached -- measured by stubbing them one at a time "
                                              "and re-running compose() in a fresh process (rows "
                                              "of the 42-row order; each one lower before the "
                                              "'focus' row, 2026-09-28). This "
                                              "row named RUN.process_setup until 2026-09-04 and "
                                              "then CAP.startup_refusals alone: process_setup is "
                                              "row 1 and has had a body since P4 wrote it, so it "
                                              "shields nothing, and CAP is the FIRST of the three "
                                              "rather than the reason. "
                                              "'curve' STAYS IN THE MAPPING while EVAL.curve_probe "
                                              "is deferred, so the ledger reads a declared key with "
                                              "checks == 0: DECLARED AND NEVER ASKED, which is a "
                                              "different statement from armed-and-inert and G4 "
                                              "requires both"),
    ("restore",   "RUN",   "Cadences.restore", "(state=Snapshot.payload['RUN']['cadences']) -- "
                                              "AFTER new_cadences because it restores INTO the "
                                              "ledger that row builds: every gate's seed, checks, "
                                              "fires and last fire, for the keys still declared. "
                                              "Until 2026-09-24 nothing of RUN's crossed the "
                                              "boundary and every gate re-seeded at the resumed "
                                              "step, so dom.manage fired at 261 instead of 201 on a "
                                              "160-window parent and the ledger restarted at 0 "
                                              "(Q-RUN-9). A checkpoint written before then has no "
                                              "'RUN' key and restores nothing"),
    ("audit",     "RUN",   "cadence_audit",   "(run_windows=_run_windows(sysm), which measures "
                                              "(len(Segmentation.ids)-1)//LM.ctx times RUN.epochs -- NOT "
                                              "'Plan's measured length', a field Plan does not have "
                                              "(data/api.py::<module>) and the same wrong fact "
                                              "_run_windows' own docstring already caught once; "
                                              "periods=the SAME mapping) -- states which of those "
                                              "EIGHT cannot fire at this run's length BEFORE the "
                                              "first window. Eight since 2026-09-28, when "
                                              "'data.trust' joined (DATA.trust_period, 0 at "
                                              "DATA_TRUST='off' and so reported DISARMED there -- "
                                              "in a line the root words, _trust_audit, since "
                                              "Q-DATA-11's review: RUN's advice to set a period "
                                              "arms nothing DATA_TRUST keeps off, and at 'observe' "
                                              "the book also passes at each epoch's end and a "
                                              "stop's tail, beside its gate), "
                                              "seven from 2026-09-27, when "
                                              "'retention' joined (EVAL.retention_period, off at 0 "
                                              "and so reported DISARMED -- and in a line the root "
                                              "words, _retention_audit, since the flip's review, "
                                              "wherever the probe is armed or pinned nothing: RUN's "
                                              "starved sentence called an armed probe's phase-start "
                                              "and R reads a mechanism never reached, and its advice "
                                              "to shorten the period named 04-6.2's 1000 as the "
                                              "fault), and six before that, "
                                              "since the cadence stage was repaired to pass "
                                              "_periods(sysm): the sixth was "
                                              "'progress', whose period is RUN.PROGRESS_WINDOWS, "
                                              "and the inline five-key dict this row described "
                                              "dropped it. At the shipped defaults a run is at "
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
                                              "SAVING IS OFF (ckpt/api.py::new_retention). Re-typing the "
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
#                   OPT.build and SIG.warm_up need the material before the loop starts -- all but
#                   DOM.on_retokenize, which is a ROLL's row only: epoch 0's segmentation is the
#                   first, so there is no earlier one for it to have re-cut.
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
                                      "is read INSIDE (data/api.py::draw_stream), so 'every epoch is a "
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
                                      "(len(Segmentation.ids)-1)//LM.ctx and that cannot be known until "
                                      "this call returns",
                                      "ids; positions -- Segmentation.byte_pos under MEM.write's "
                                      "spelling; windows_in_epoch and run_windows through "
                                      "_windows_in_epoch and _run_windows; bytes_per_window through "
                                      "_bytes_per_window; stream on the token arm. This is also "
                                      "the call the B row invokes on a retok, and the RetokEvent it "
                                      "is said to return is DECLARED (tok/api.py::<module>) BY NO ENTRY "
                                      "POINT'S DOCSTRING -- tokenize's says Segmentation"),
    ("E", "RUN",   "RunClock.begin_epoch", "(windows_in_epoch=(len(Segmentation.ids)-1)//LM.ctx) -- a "
                                      "MEASUREMENT, re-taken every epoch because a resampling stream "
                                      "is a different length each time and minting shortens every "
                                      "later one. THE LENGTH ARRIVES AS A COUNT OF WINDOWS. The "
                                      "partial batch was already dropped by the advance that rolled"),
    ("E", "DOM",   "on_retokenize",   "(dom, part) -- THE RetokEvent's DOM DESTINATION, delivered AT "
                                      "THE ROLL because the roll is where the re-segmentation "
                                      "happens: a mid-epoch Due.retok is deferred to it (Q-RUN-8), "
                                      "and TOK.tokenize above is the act. MEM hears of the same "
                                      "event as MEM.maintain(resegment=...) on the first flush "
                                      "after the roll. GATED ON THE MATCH TABLE HAVING MOVED since "
                                      "the last segmentation (Vocabulary.rev, the stamp tokenize "
                                      "itself reads): a roll at an unchanged table cuts the new "
                                      "text into the ids DOM's token histograms were counted "
                                      "under, and decaying them would discard valid counts "
                                      "(Q-DOM-2). THE CALL TAKES NO EVENT PARAMETER AT ALL "
                                      "(domains/api.py::on_retokenize), so DOM can only decay, "
                                      "never remap; SIG and FAB have no retokenize entry point in "
                                      "their frozen surfaces; and the event itself is a record "
                                      "type tok/api.py::<module> declares and no entry point's "
                                      "docstring returns. It had NO CALL SITE until 2026-09-24, "
                                      "which left DOM_TOKC_DECAY inert in every configuration",
                                      "no return: the decay edits part.tokc in place"),
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
                                      "under FAB.forward's, which fabric/api.py::forward is explicit is "
                                      "RUNTIME STATE and an argument rather than the "
                                      "d_live_domains wire. Same staleness as the row above: a B "
                                      "row takes live_domains every flush and this one runs on a "
                                      "cadence that may never fire. DOM.census returns "
                                      "PartitionCensus, declared in domains/api.py's RECORD TYPES "
                                      "block since 2026-09-02 under DOM's own spellings -- "
                                      "Q-MEM-11 RESOLVED (a), and this row is where its two renames "
                                      "are recorded"),
    ("A", "FAB",   "contribution",    "THE MARGINAL CONTRIBUTION (2026-09-28, register §8 3.5, "
                                      "02-R11 and C37; Q-FAB-19), INSIDE THE ONE "
                                      "Cadences.due('fab.manage', ...) ANSWER THE ROW BELOW ASKS "
                                      "-- never a second due() under that key -- and BEFORE "
                                      "FAB.manage, so the pass's contrib > 0 spares and "
                                      "FAB_FADED_CULL='contrib' read what it measured. THE ARM TEST "
                                      "COMES FIRST: FAB_CONTRIB=1 on a routed arm with the "
                                      "retention probe armed; at the shipped FAB_CONTRIB=0 the row "
                                      "is skipped, FAB.manage reads no contribution (Q-FAB-19's "
                                      "review: a child resumed at 0 carries its parent's, unread) "
                                      "and a lineage that never armed it has no fab.contrib_* "
                                      "key. The batch is "
                                      "_contrib_material's: the first (EVAL_RETENTION_N + 1) // 2 "
                                      "pinned CONTROL items of every arrived area, cut at the "
                                      "last-cut view and cut back to one length; targets are its "
                                      "ids shifted one. The root binds the memory-off closure to "
                                      "the batch (_logits_fn(sysm, use_memory=False, "
                                      "book='eval.contrib') through _contrib_baseline) as "
                                      "baseline_logits_fn, calls it once with route= to take the "
                                      "FAB.forward inputs it used -- h, signature, novelty ZEROS, "
                                      "domain_id (DOM.nearest of the first row's signature), "
                                      "live_domains and step_windows (clock.step + 1, the "
                                      "closure's routing clock) -- and scores its logits "
                                      "LM.lm_loss(lm, logits=..., y=targets) for baseline_loss; "
                                      "head is the closure's counted head. All of it under "
                                      "no_grad, frozen_rng(strict=True), every module in eval mode "
                                      "and Process.autocast. candidates is left at None: the next "
                                      "FAB_CONTRIB_MAX past-grace experts off Population's rotating "
                                      "cursor. IT PRODUCES NOTHING ANY SIGNATURE TAKES: it writes "
                                      "Population.contrib and contrib_n, the books the row below "
                                      "reads, and returns a ContribReport the root files nowhere"),
    ("A", "FAB",   "manage",          "Cadences.due('fab.manage', FAB.manage_period(fab), clock) -- "
                                      "step_windows=clock.step; flush_loss is the MEAN of the "
                                      "flush losses since the previous pass, computed by the loop "
                                      "(FAB_DEPTH_EPS is declared on the SMOOTHED flush loss, and "
                                      "one flush's loss is noise at that threshold); faded "
                                      "(2026-09-28, Q-FAB-18) is _faded_ids at this window's "
                                      "first byte -- Plan.faded for its phase and "
                                      "Plan.parent_faded, as spine/derive.py::area_id numbers -- "
                                      "which the pass counts its removals against, and at "
                                      "FAB_FADED_CULL='defer' defers them by -- at 'contrib' "
                                      "(2026-09-28, Q-FAB-19) removing one only where the row "
                                      "above, riding this same one answer, has measured the "
                                      "expert at or below 0. WORLD's growth pass used to ride "
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
                                      "sig); seen_units=_signature_cursor(sysm, sig, i) at this "
                                      "window's epoch-local 0-based index i, so the window about to "
                                      "be predicted is not yet drawable (Q-FAB-7), "
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
                                      "windows=_sample_window(sysm, sig, i) with i this window's "
                                      "epoch-local 0-based index, the "
                                      "width_units-wide slice of the unit stream ending at the "
                                      "window's FIRST byte -- never at its last, which routed every "
                                      "window on its own targets until 2026-09-24 (Q-FAB-7). "
                                      "THE SAME OBJECT goes to DOM.observe one row below, "
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
                                      "period. Two counters: tok.due_merged, seeded and bumped by "
                                      "the root at the second window of a batch (UNREACHABLE at the "
                                      "shipped batch_windows=1), and tok.due_dropped, whose "
                                      "flush-discard share is 0 by construction here -- which is "
                                      "how a later reader can tell which reading was implemented -- "
                                      "and which also counts, one per fire, the retoks no epoch "
                                      "roll reached (Q-RUN-8). At the shipped batch_windows=1 the "
                                      "two readings are identical"),
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
    ("B", "WORLD", "forecast",        "obs_emb = LM.embed's return from the row above; w is "
                                      "System.world, built at assembly. BETWEEN embed AND encode "
                                      "because its return IS encode's `extra` on the row below. "
                                      "WIRED 2026-09-24 (Q-WORLD-10 RESOLVED): world_proj is born "
                                      "ZERO, so the first call adds exactly nothing and the path "
                                      "still learns (dL/dW = dL/dout x pop(z), and pop(z) is not "
                                      "zero). None at WORLD_FEEDBACK=0 and on the null world, "
                                      "which encode accepts",
                                      "extra -- the (B, L, width) forecast world_proj(pop(z)), "
                                      "LM.encode's additive term; None when feedback is off"),
    ("B", "LM",    "encode/decode/lm_loss", "x and y are the flush's batch and its next-token "
                                      "targets, cut from Segmentation.ids at _flush_bounds -- see "
                                      "ROW_ARGUMENTS_ELSEWHERE, because no entry point returns a "
                                      "batch. live_vocab and retired_ids come from the vocabulary "
                                      "built at assembly and are refreshed by TOK.judge_probation "
                                      "at B; extra = the WORLD.forecast row's return, None when "
                                      "feedback is off",
                                      "h -- LM.encode's (B, L, width) hidden, which is FAB.forward's "
                                      "spelling; logits -- LM.decode's return, THE ONLY PLACE "
                                      "LOGITS ARE PRODUCED: through _head inside FAB.forward, one "
                                      "decode per voting expert, when the population votes "
                                      "(FabricOut.logits, Q-FAB-8), and on FabricOut.hidden here "
                                      "when nothing voted; one of the two inputs this file "
                                      "forms MEM's write gate from (:7497-7498); "
                                      "per_window_loss = per_window -- lm_loss's first return, "
                                      "FAB.observe's spelling; "
                                      "flush_loss = per_window -- the same return pooled over the "
                                      "flush, which FAB.manage and FAB.grow_check take; "
                                      "bits = per_window -- the same return over ln 2, bits per "
                                      "TOKEN, and at DOM_LEVELS re-denominated by the root to bits "
                                      "per build-time token (Q-DOM-5; this read 'bits per byte' "
                                      "until 2026-09-26, which it never was), "
                                      "DOM.note_competence's spelling. THREE SPELLINGS OF "
                                      "LM.lm_loss'S TWO RETURNS, which are a bare tuple with no "
                                      "record type to anchor them (lm/api.py::lm_loss); mean, the "
                                      "other one, is the first summand of the composed objective "
                                      "OPT.scaled_backward takes. (A FOURTH, baseline_loss for "
                                      "FAB.contribution, stood here until 2026-09-28: the "
                                      "baseline is no longer the flush's loss but the A row's "
                                      "own LM.lm_loss mean over the probe's control half, "
                                      "Q-FAB-19)"),
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
                                      "OPT.scaled_backward takes; row_events -- "
                                      "FabricOut.row_events, the expert rows FAB moved, cleared "
                                      "or re-born since the previous training pass, which "
                                      "OPT.remap_rows takes before the backward (Q-FAB-13)"),
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
    ("B", "OPT",   "remap_rows",      "row_events from FAB.forward's row (FabricOut.row_events; "
                                      "None when no row moved). BEFORE scaled_backward, because "
                                      "every move / clear / birth since the previous backward -- "
                                      "the last flush's grow_check births, a manage pass's culls, "
                                      "this forward's spawns -- has happened and this flush's "
                                      "gradient has not yet been accumulated onto the old rows. "
                                      "IT PRODUCES NOTHING: the moments it moves are OPT's own "
                                      "state (Q-FAB-13)"),
    ("B", "OPT",   "scaled_backward", "scaling and counting in ONE function, never 128 lines apart. "
                                      "total is the COMPOSED objective and has no single producer "
                                      "by design: it is LM.lm_loss's mean + LM.anchor_term's "
                                      "already-weighted term + FabricOut.aux_loss + WORLD's loss, "
                                      "four rows above this one. lm/api.py::lm_loss forbids LM "
                                      "composing it, so the sum is THIS FILE'S and the row names "
                                      "the summands rather than a producer that must not exist"),
    ("B", "RUN",   "RunClock.note_backward", "derive.accum_due on a Backwards clock -- seeded from "
                                      "OPT's restored n_backward (Q-RUN-9) and compared with "
                                      "OPT.scaled_backward's count every flush, because "
                                      "OPT.maybe_step re-decides the step on that one"),
    ("B", "OPT",   "maybe_step",      "shift_at from the root, stamped at the E draw row; returns "
                                      "StepOutcome.lr as a RETURN VALUE. Its step 2 IS "
                                      "OPT.lr_at(st, st.opt_step) -- the schedule is PURE and is "
                                      "read from inside this one function, which is why it has no "
                                      "row of its own. best_bpb <- System.probe_reading, A "
                                      "BACKWARDS EDGE CARRIED ON System the way novelty is "
                                      "(2026-09-27, Q-OPT-13): the retention probe's latest "
                                      "CONTROL-half Reading(value, seed_count=1, at), set by "
                                      "the EVAL.holdout_probe row below after the flush before "
                                      "it and read by the NEXT flush; None until the first "
                                      "reading and at EVAL_RETENTION_EVERY=0. At the shipped "
                                      "OPT_DAMP_SOURCE='off' maybe_step drops it before reading "
                                      "it, so no training decision moves; at 'probe' every "
                                      "losing restart is REFUSED (seed_count 1, PLAN 3.8) and "
                                      "counted in opt.restart.damp_refused_n1, and a Reading "
                                      "re-delivered with the same `at` counts once. It is a "
                                      "defaulted argument, so no check asks for its producer, "
                                      "which is why this row names it",
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
                                      "on one word. THE LOOP TAKES ITS BIRTH BUDGET THROUGH "
                                      "Caps.headroom(population) AND NEVER BY SUBTRACTING: "
                                      "`min(n_born, cap - fab.n())` is the C30 freeze, negative the "
                                      "moment the population exceeds the soft cap and silent for "
                                      "the whole run, and the method exists so that expression "
                                      "cannot be written at a call site (docs/04_CONTRACT.md says "
                                      "so of the record). It is credited to this row because the "
                                      "cap it differences is the one this row produces"),
    ("B", "FAB",   "observe/grow_check", "per_window_loss and flush_loss from LM.lm_loss's two "
                                      "returns; out from FAB.forward; domain_id from DOM.observe; "
                                      "area_id (2026-09-28, Q-FAB-18) is _window_areas's one id "
                                      "per window -- its first token's area off "
                                      "Segmentation.labels, as a spine/derive.py::area_id -- "
                                      "which observe books into the area_use book; "
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
                                      "this row, then deferred for want of `candidates`, "
                                      "`targets` and a `baseline_logits_fn` of the right shape; "
                                      "since 2026-09-28 (Q-FAB-19) it has an A row of its own, in "
                                      "the fab.manage answer, on the retention probe's control "
                                      "half through the memory-off closure, where `candidates` "
                                      "defaults to the next FAB_CONTRIB_MAX past-grace experts and "
                                      "`targets` are the batch's own shifted ids"),
    ("B", "MEM",   "write/maintain",  "key_fn=LM.encode bound by _key_fn; contexts and tokens are "
                                      "the flush's x and y at _flush_bounds; positions are TRUE "
                                      "BYTE OFFSETS from Segmentation.byte_pos; areas (2026-09-28, "
                                      "Q-MEM-16) is _window_areas's one area id per POSITION, each "
                                      "input token's beside its offset, which write stores in the "
                                      "`area` column MEM.census counts occupancy by; sources from "
                                      "DOM.observe; owners from FAB.forward; surprise is "
                                      "1 - the model's probability of the true next token, formed "
                                      "by this file from LM.decode's logits and y (:7497-7498) -- "
                                      "the same quantity whose per-flush mean becomes the next "
                                      "flush's novelty; now=clock.step. maintain's job 1 is this "
                                      "package's OWN retrieval on the probe_every cadence -- the "
                                      "read that moves use/last/prob, without which evict='lru' and "
                                      "evict='usage' are write-order FIFO whatever they say and "
                                      "probation can never promote; it is written without the call "
                                      "form because MEM.read is deferred as a row for want of "
                                      "`queries` and maintain reaches it in-package (Q-MEM-9). Its "
                                      "probe_contexts is the PREVIOUS flush's x, carried by the "
                                      "loop (None on the first flush of a run and of each epoch), "
                                      "SINCE 03b S0b an act hands the next maintain remap= -- the "
                                      "stored contexts decoded by TOK.Vocabulary.decode(ids) and re-cut "
                                      "at the act's view by TOK.tokenize(view=) (Q-MEM-13) -- "
                                      "and maintain issues probe_rows queries out of it, one per "
                                      "POSITION (Q-MEM-12). maintain ALSO compares "
                                      "probe_every and rekey_every against `now` INTERNALLY: two "
                                      "Windows gates with no ledger key, whose only did-it-fire "
                                      "surface is store.n_probe_fired / n_rekey_passes at R. That "
                                      "is this package's own read rather than a second retrieval is "
                                      "the reading Q-MEM-9 asks the owner to confirm"),
    ("B", "TOK",   "mint_burst",      "step=clock.step, on the Due this flush's windows produced at "
                                      "A -> LM.on_mint(sig_emb=SIG.encoder_embedding(...)). "
                                      "Due.retok IS NOT ACTED ON HERE: re-segmenting mid-epoch "
                                      "changes the epoch's window count and RunClock cannot be told "
                                      "a new length with its cursor kept (Q-RUN-8), so the fire is "
                                      "counted on System.retok_pending and the next epoch roll "
                                      "performs it -- TOK.tokenize, MEM.maintain(resegment=...) and "
                                      "DOM.on_retokenize are the E rows, and the roll's resample is "
                                      "the shift the root stamps on System.shift_at_windows for "
                                      "FAB.grow_check (Q-FAB-6). This row said the retok was acted "
                                      "on and stamped HERE until 2026-09-24",
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
    ("B", "DOM",   "note_competence", "did from DOM.observe; bits from the per-window loss, in "
                                      "the unit DOM_LEVELS sets (Q-DOM-5): at DOM_LEVELS the root "
                                      "hands bits per BUILD-TIME token -- the window's per-token "
                                      "loss / ln 2 x Vocabulary.bytes_per_token / the window's own "
                                      "bytes per token off Segmentation.byte_pos, one window at a "
                                      "time (spine/loop.py::_build_token_scale); at DOM_LEVELS=0 "
                                      "the per-token loss / ln 2, bits per token; the rate is the "
                                      "d_comp_ema wire"),
    ("B", "DATA",  "claims_observe",  "THE SOURCE-RELIABILITY BOOK (2026-09-28, Proposal 04 SR3; "
                                      "Q-DATA-11), once per window AFTER the flush and the X block "
                                      "and BEFORE the retention probe and the checkpoint gate. THE "
                                      "ARM TEST COMES FIRST -- DATA_TRUST != 'off' -- and only then "
                                      "Cadences.due('data.trust', DATA.trust_period(dat), clock), "
                                      "so at 'off' the gate is never asked and no data.trust.* key "
                                      "exists. A pass also runs on the window that rolls the epoch, "
                                      "due or not, so the book reads every unit of an epoch before "
                                      "the roll rebuilds the segmentation (on a rolling tick that "
                                      "read no window, after the cut's branches). Each pass reads "
                                      "the units consumed since the last: focus=System.focus, "
                                      "units and sources from _trust_units(sysm, lo, hi) -- lo the "
                                      "book's per-epoch cursor, hi the ids the windows cut so far "
                                      "consumed (the last cut window's end), step=clock.step, "
                                      "at=lo. An epoch roll puts lo back to 0, and the next pass "
                                      "opens the new stream. It REPORTS and changes nothing the "
                                      "run trains on; its seconds are the root's float "
                                      "data.trust.wall_s, outside every compared book. At "
                                      "DATA_TRUST_COPY='accu' the pass's vote also judges pairs "
                                      "of sources for copying and discounts a dependent pair's "
                                      "copy (SR6, Q-DATA-12) -- inside the book, and DATA times "
                                      "that step as data.trust.copy.seconds, a float outside "
                                      "them too"),
    ("B", "EVAL",  "holdout_probe",   "THE RETENTION PROBE (Q-EVAL-12), once per window AFTER the "
                                      "flush and the X block and BEFORE the checkpoint gate. THE "
                                      "ARM TEST COMES FIRST -- EVAL_RETENTION_EVERY > 0 and a "
                                      "pinned System.probe_set -- and only then "
                                      "Cadences.due('retention', EVAL.retention_period(ev), "
                                      "clock), so at 0 the gate is never asked; a PHASE-START "
                                      "read also runs at the first window of every phase (the "
                                      "window's first byte against Stream.phase_bounds, against "
                                      "the (epoch, phase) LOOP.eval last read -- or, on a "
                                      "continuing resume whose parent recorded none, the phase "
                                      "its last window fell in). One MEMORY-OFF "
                                      "reading of retention_n windows per arrived area, through "
                                      "the closure's path: DOM.nearest(dom, part, signature=...), "
                                      "SIG.encode(sig, st, [prefix]), LM.embed(lm, model, x), "
                                      "WORLD.forecast(world, w, obs_emb), LM.encode(lm, model, x, "
                                      "extra=...), FAB.forward(training=False, "
                                      "step_windows=clock.step + 1, ...), LM.decode(lm, model, h, "
                                      "...) and, for each window's ids, TOK.tokenize(view=...) at "
                                      "the view the stream was last cut at -- each writing nothing "
                                      "a training pass reads. A reading with no finite control "
                                      "mean is not forwarded -- counted eval.holdout.nonfinite "
                                      "where a control window scored non-finite, "
                                      "eval.holdout.empty where none was scored; "
                                      "otherwise it becomes System.probe_reading, the next "
                                      "flush's best_bpb"),
    ("B", "EVAL",  "blowup",          "(series=LOOP.eval's per-area and all-area control means, "
                                      "the all-area series re-armed at each arrival) -- after every "
                                      "reading that forwarded a mean. It REPORTS and changes "
                                      "nothing: eval.blowup.fired, eval.blowup.since_best"),
    ("B", "CKPT",  "Retention.consider", "(curve_bpb=the reading's control mean, step=clock.step) "
                                      "-- after the blow-up row, on the same forwarded mean. Its "
                                      "BestAction is acted on HERE: _carry(), then "
                                      "CKPT.save(reason='best', suffix='.best') when save_best, "
                                      "then CKPT.save(reason='bestN', suffix='.best<slot>') when "
                                      "rotate_slot, each followed by the C row "
                                      "Retention.note_saved with what that save returned. With "
                                      "CKPT_DIR off it tracks the best and orders nothing"),
    ("B", "CKPT",  "save",            "Cadences.due('ckpt', CKPT.save_period(ck), clock), or the "
                                      "SIGUSR1 flag -- the B-level route INTO the C block, with "
                                      "reason='periodic' or 'sigusr1'. It does not assemble "
                                      "anything: the C rows below build `payload` and the recorded "
                                      "geometry, and step=clock.step, epoch=clock.epoch. Written as "
                                      "a route rather than as four restated arguments, because a "
                                      "second copy of the signature is what these tables exist to "
                                      "avoid"),

    # -- X: THE MID-EPOCH ACT (Q-RUN-8 option (a), 03b S0b). An EVENT, not a clock: entered right
    # after a flush, with the batch empty, when TOK's retok Due (TOK.on_window's own `_due`, OR'd
    # per Q-TOK-12 and counted by the flush) asks for the stream to be re-segmented at the
    # vocabulary as it now stands. Until it existed the request waited for an epoch roll, which at
    # RUN_EPOCHS=1 never comes. One row per package call, because _rows_by_stage credits a name only
    # from its own row. A request whose match table has not moved since the last segmentation
    # (Vocabulary.rev) is refused and counted (tok.retok_noop, loop.acts_noop).
    ("X", "TOK",   "splice",          "(vocab, seg=System.segmentation, data=Stream.bytes, "
                                      "labels=Stream.labels, at=win_in_epoch*LM.ctx, "
                                      "regularize=True) -- keeps every unit up to and including "
                                      "the one under the cursor and re-segments the rest, so the "
                                      "ids minted since the last segmentation reach the stream. "
                                      "Before it the root reads TOK.view_of(vocab): an unmoved view "
                                      "is a no-op, refused; a moved one is logged with the cut "
                                      "(System.seg_log) so a resume replays it",
                                      "System.segmentation; the loop's ids; the signature stream "
                                      "re-resolved; MEM hears resegment= on the next flush"),
    ("X", "RUN",   "RunClock.revise_epoch_length", "(windows_in_epoch=(len(Segmentation.ids)-1)"
                                      "//LM.ctx) -- only if the re-measured length changed; the "
                                      "cursor is kept, so no window is replayed or skipped",
                                      "the clock's epoch length"),
    ("X", "OPT",   "revise_horizon",  "(st, run_windows=clock.step + the rest of this epoch at "
                                      "its new length + later epochs at that length) -- only if "
                                      "the length changed; LR-continuous (Q-OPT-10); inert and "
                                      "counted at OPT_HORIZON_REVISE=False (Q-OPT-12)",
                                      "st.horizon_revisions"),
    ("X", "DOM",   "on_retokenize",   "(dom, part) -- when the match table moved since the last "
                                      "segmentation, as at the roll; the act also stamps "
                                      "System.shift_at_windows/shift_at_steps, a self-inflicted "
                                      "shift", "DOM_TOKC_DECAY applied to the token histograms"),

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
    # WHAT WAS ACTUALLY LEFT was narrower and is now CLOSED (2026-09-22): the two `sidecar`
    # refusals read a per-prefix key ('SIG', 'FAB') that no row writes and that a FLAT prefixed
    # manifest cannot have at any point in its life, so both were disarmed on every resume. The
    # producer Q-CKPT-2 asked for existed the whole time in the other direction -- each package
    # writes a 'sidecar' key into its OWN payload slice -- and spine/compose.py::_sidecar reads it
    # there. Read off a real checkpoint: payload['SIG']['sidecar'] has all five compared fields and
    # payload['FAB']['sidecar'] all four, against three in the flat manifest's sig.*.
    ("C", "DATA",  "stream_state",    "(areas, focus=System.focus) -- the per-area cursors, "
                                      "without which a resume re-reads the head of every area under "
                                      "seg_contig and trains a second time on the parent's "
                                      "material; and, since 2026-09-28 (Q-DATA-11), the "
                                      "source-reliability book under 'focus' at DATA_TRUST="
                                      "'observe' -- nothing at 'off', so an 'off' payload is the "
                                      "one written before the book, unless the Focus carries a "
                                      "checkpoint's book, which it writes back unchanged",
                                      "payload['DATA'] -- and its KEY SPELLINGS ARE NOWHERE "
                                      "DECLARED (data/api.py::stream_state says 'dict' and lists the contents "
                                      "in prose), so the round trip through DATA.restore_stream_"
                                      "state is unverifiable by inspection"),
    ("C", "TOK",   "vocab_state",     "(vocab) -- retirements and probation (D-T3, which "
                                      "restore_vocab now puts back), the pair tally and "
                                      "tally_seen exactly, and the counters, which carry the "
                                      "three cadence clocks",
                                      "payload['TOK'] -- keys listed at tok/api.py::vocab_state; "
                                      "the merges themselves travel in the vocabulary file"),
    ("C", "LM",    "state_dict",      "(model, geom)", "payload['LM']"),
    ("C", "SIG",   "state_dict",      "(st) -- and the sidecar the restore row "
                                      "above compares against, which sig/api.py::state_dict says this "
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
    ("C", "RUN",   "Cadences.state",  "() -- every gate's seed, checks, fires and last fire, so a "
                                      "resumed run keeps the parent's schedule instead of "
                                      "re-seeding each gate a period late (Q-RUN-9)",
                                      "payload['RUN']['cadences']"),
    ("C", "RUN",   "RunClock.counters", "() -- in_epoch and windows_in_epoch, the clock's position "
                                      "in its epoch, which a Snapshot's step and epoch cannot say at "
                                      "epoch > 0; the child reads it to WARN about a mid-epoch "
                                      "replay (Q-RUN-10)",
                                      "payload['RUN']['clock']"),
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
                                      "RECORDED, so 'saves: 0' can name which route was never taken",
                                      "ok -- CKPT.save's return, True iff a file was written, "
                                      "which the row below hands back to the retention policy"),
    ("C", "CKPT",  "Retention.note_saved", "(ok, slot=the BestAction's rotate_slot for a bestN "
                                      "save, None for the global .best) -- ONLY after a save a "
                                      "BestAction ordered: the C fan-out runs for every save, and a "
                                      "periodic, SIGUSR1 or final save answers nothing here "
                                      "(Q-CKPT-6). A refused best save sets best_saved False; a "
                                      "refused slot save puts the slot's previous resident back and "
                                      "the pointer with it, so the ring advances only on a written "
                                      "file, as self_organize.py:6481-6483 did"),

    # -- R: the report. Once, after Tick.finished. NEVER ASKED and ASKED AND REFUSED are two
    # different statements and this stage is where the second half of the evidence is collected.
    # MEM.read and MEM.blend WERE rows HERE until 2026-08-30 and were then deferred, because nothing
    # produced `queries` and blend's `model_probs` are probabilities while every scoring hook takes a
    # logits_fn. SINCE 2026-09-27 BOTH ARE REACHED, and not as rows: the memory-on closure
    # (_logits_fn(sysm, use_memory=True)) forms softmax -> MEM.encode_queries -> MEM.read(promote=
    # False) -> MEM.blend -> log once, and the EVAL.holdout_probe row below names each call in its
    # note -- Q-MEM-10 as amended the same day, which had said blend is "called from that spine
    # helper and never from a row" and now says the helper is credited through the row that calls
    # it.
    ("R", "EVAL",  "holdout_probe",   "THE BOUNDARY READING, at the HEAD of R and INSIDE the try "
                                      "that saves the final checkpoint when the R stage raises: "
                                      "holdout_windows windows per arrived area (boundary=True), "
                                      "through BOTH closures -- memory-off, then memory-on, whose "
                                      "closure adds MEM.encode_queries(mem, contexts=x, "
                                      "key_fn=...), MEM.read(mem, store, queries=..., "
                                      "promote=False) and MEM.blend(mem, probs, retrieval), then "
                                      "log -- each paired against the resume's last start reading, "
                                      "or the parent's last boundary reading, when there is one. A "
                                      "RESUME ALSO READS AT ITS START, after run()'s refusal and "
                                      "finished-clock guards, at the parent's last-cut view and "
                                      "live-domain count, so at the same weights it equals the "
                                      "parent's final reading, and where its own first cut is at "
                                      "another view (an epoch-boundary resume of a parent that "
                                      "minted after its last cut) again at that view, the same "
                                      "count ('resume_own', 2026-10-02); "
                                      "eval.holdout.boundary_reads and eval.holdout.resume_reads "
                                      "count the two kinds. Boundary readings are reported and "
                                      "never consumed"),
    ("R", "DATA",  "claims_observe",  "THE BOOK'S TAIL (2026-09-28, Q-DATA-11), inside the same "
                                      "try, after the boundary reading and before the report: where "
                                      "a stop left units consumed since the last pass -- a "
                                      "max_windows stop mid-epoch; the finishing roll's pass has "
                                      "read the epoch to its end -- one more pass reads them, so "
                                      "the report and the final checkpoint hold every unit this "
                                      "process consumed and a continuing resume goes on from its "
                                      "cursor. The same arm test, the same join and arguments as "
                                      "the B row, and no gate"),
    ("R", "DOM",   "prior",           "(did) -- the per-domain token prior AND its weight, together. "
                                      "At R it is asked once for EACH id DOM.census's `live` list "
                                      "carries (it was asked for did=0 alone until 2026-09-24), not "
                                      "for a live Assignment, and the report prints one summary "
                                      "over them. The "
                                      "old read site is the report (:8147-8192) while the "
                                      "accumulation is per window, and the accumulated/read PAIR is "
                                      "the whole finding that the histogram was paid for every "
                                      "window and never read"),
    ("R", "MEM",   "census",          "(reconcile=True) -- the store's did-it-fire surface, re-taken "
                                      "at the end so the report's numbers are the settled ones, and "
                                      "called BEFORE the report copies store.counters so the copy "
                                      "and the checkpoint carry its reconcile. Its `gates` are "
                                      "where the two ungated gates inside MEM.maintain (mem.probe, "
                                      "mem.rekey -- no ledger key) and the other five mem.* gates "
                                      "reach the report, rendered in three states beside the "
                                      "row. Its StoreCensus.by_area is printed there BY NAME, "
                                      "the root holding the names MEM never sees: "
                                      "store.occupancy.<area> for every area of the run and "
                                      "store.occupancy_unknown (2026-09-28, Q-MEM-16)"),
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
    ("R", "CKPT",  "Retention.counters", "() -- probes_seen, new_bests, rotations, slots_used, "
                                      "saves_refused and inert_reason, which is the one surface "
                                      "that can say 'no curve value has ever arrived' instead of "
                                      "'zero local lows'. At EVAL_RETENTION_EVERY=0, the shipped "
                                      "value until 04-6.2's flip (2026-09-29), that is exactly "
                                      "what it must say"),
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
    ("R", "EVAL",  "generate",        "(logits_fn=each closure in turn, prompts_by_domain from "
                                      "_gen_prompts, rng=System.gen_rng) -- AFTER the final save, "
                                      "so generation costs the run nothing it keeps and the "
                                      "checkpoint is byte-identical with it on or off. ABSENT -- "
                                      "eval.generate.* not seeded -- at EVAL_GENERATE=0 or with no "
                                      "ProbeSet; its row in the report is added after the save"),
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
# IT IS NO LONGER ONLY EVAL, AND THAT IS THE POINT OF THE `produces` COLUMN. When the column was
# added it found seven rows ELSEWHERE in the tables naming calls with exactly the same gap as the
# EVAL entries: EVAL.curve_probe, MEM.read, MEM.blend, MEM.judge, FAB.contribution, CAP.observe and
# WORLD.manage. EVAL.curve_probe and EVAL.holdout_probe had BYTE-IDENTICAL signatures and got
# opposite verdicts. The column made every one of them decidable, and each entry names what would
# close it. NONE was deferred for being late, and none because a body was missing: the whole tree
# was stubs.
#
# THE TABLE HOLDS EIGHTEEN ENTRIES SINCE LATER ON 2026-09-28, when O17's position lever added
# LM.parent_designation (Q-LM-15), a checkpoint's question no run asks; SEVENTEEN from earlier that
# day, when FAB.contribution got its A row (Q-FAB-19), the day after the retention probe (Q-EVAL-12)
# closed five: EVAL.holdout_probe and EVAL.generate got rows, CKPT.Retention.consider got its caller,
# and MEM.read and MEM.blend are reached through the memory-on closure the R row's note names. The
# eighteen divide by WHY rather than by package:
#   TEN are deferred at the ARGUMENT or at the SCOPE. Six are EVAL's -- EVAL.null_excess,
#   EVAL.verdicts, EVAL.wrongness_probe and EVAL.verification_fit wait on an argument nothing
#   produces, and EVAL.curve_probe and EVAL.coherence, whose producers exist since the probe
#   landed, are SCOPE deferrals: no row of the register's section 8 builds them. Four are not
#   EVAL's -- MEM.judge (the scorer's (ctx, src) arity the closure does not have), CAP.observe,
#   WORLD.manage, and LM.parent_designation, whose `saved_geometry` is a checkpoint's record that no
#   row of a run produces (its caller is the unbuilt preset builder, and a tool until then).
#   EIGHT are deferred because the CALLER is missing while every argument is one the caller already
#   holds: FAB.Population's two accessors, WORLD.World.parameters, three of Vocabulary's five
#   accessors (live_size, at_cap, blen), and RUN.Timing's two.
# (Until 2026-09-27 this paragraph counted twenty-four entries, FIFTEEN by argument and NINE by
# caller with "four of Vocabulary's five" -- which was stale twice by then: the table held
# twenty-three, and three Vocabulary accessors, since TOK.Vocabulary.decode left it on 2026-09-26
# (Q-MEM-13's re-cut, 24 -> 23; until 2026-09-29 this sentence named TOK.Vocabulary.size, whose
# leaving is what made the count four). It counted eighteen, TEN by argument or scope, until
# FAB.contribution left on 2026-09-28, and seventeen, NINE by argument or scope, until
# LM.parent_designation arrived the same day.) The count is not cosmetic -- this table's whole claim
# is that every orphan is enumerated, and an enumeration whose own total is wrong is one no reader
# re-checks.
# SOME OF THOSE NOW HAVE A CALLER THAT IS NOT A ROW, AND THEIR ENTRIES SAY SO (2026-09-24):
# FAB.Population.parameters and WORLD.World.parameters are called by _base_parameters on every
# compose(), and RUN.Timing's two by spine/loop.py. They stay listed because K6 credits only a row,
# and a helper or an instrumentation span is not one; their reasons stopped describing an absence.
#
# WHAT THIS COSTS, SAID PLAINLY, because a deferral that hides its cost is the shape it replaces:
# with these unrowed the run has no capacity valve (nothing lifts a cap), no WORLD growth, no
# learning-curve probe at EVAL_CURVE_EVERY and no wrongness sweep. The retention probe that closed
# five of them was BUILT OFF (EVAL_RETENTION_EVERY=0) and ships ON since 04-6.2's flip (2026-09-29),
# so at the shipped defaults the best-model save is fed at every phase start while the restart
# damping still reads its inert reason (OPT_DAMP_SOURCE='off'); and the per-expert contribution
# that left on 2026-09-28 is BUILT OFF too (FAB_CONTRIB=0), so a default run still has no measured
# contribution and no informed contrib > 0 spare. The deferral does not remove a mechanism, it stops
# the tables claiming one, and it names the producer each mechanism is waiting on.
DEFERRED_ENTRY_POINTS = {
    # THE TWO Population ACCESSORS AND THREE OF Vocabulary'S FIVE. They arrived with their records in
    # P4's FAB and TOK slices, one increment before the rows that call them, for the same reason
    # RUN.Timing's two did: TOK.build_vocabulary has to RETURN a Vocabulary and FAB.build a
    # Population, and the contract's RECORD TYPES block names these accessors as those objects'
    # surface. (IT SAID "THE FIVE Vocabulary ACCESSORS" UNTIL 2026-09-04, when it was true of the
    # block it headed: the contract names five -- decode, blen, size, live_size, at_cap -- and all
    # five were here. TOK.Vocabulary.size LEFT, correctly, when the `vocab` row named it as
    # live_vocab, which is the STALE half of K6's two-way read doing its job; the two FAB.Population
    # entries then arrived above the comment. Four of the five, plus two that are not Vocabulary's --
    # and three since 2026-09-26, when a row named TOK.Vocabulary.decode (Q-MEM-13); this heading
    # said FOUR until 2026-09-29.) They are accessors on a record other packages receive as an argument and
    # call methods on -- which the contract states is not an import -- so their callers are LM's
    # embedding rows, TOK's own minting rows and EVAL's decode, none of which have bodies yet. Every
    # one of them takes only `self` (or an id), so there is no argument without a producer: what is
    # missing is the CALLER, and that is the whole reason each line below says which one.
    "FAB.Population.parameters":
        "CALLED ON EVERY compose(), by name, from this file: _base_parameters does "
        "`getattr(obj, \"parameters\", None)` on the model, the population and the world, and the "
        "list it returns is OPT.build's param_groups['base'] -- a default compose harvests 38 base "
        "tensors (opt.build.params.base 38) with no missing-parameters warning. Listed here, and "
        "not credited to a row, only because a helper in the composition root is not an "
        "order-table row. It takes only self, so there is no argument without a producer. (Until "
        "2026-09-24 this reason said OPT.build did not consume the list and described the cost of "
        "the method's ABSENCE -- every expert's contribution exactly zero while the population "
        "grew and culled around it. That was true before the method and the harvest landed and has "
        "not been true since.)",
    "WORLD.World.parameters":
        "CALLED ON EVERY compose(), for EXACTLY the reason the FAB entry above gives: "
        "_base_parameters in this file calls it by name through `getattr(obj, \"parameters\", "
        "None)` and hands the list to OPT.build as part of param_groups['base'], and a helper in "
        "the composition root is not an order-table row. It takes only self. WHAT FOLLOWS IS THE "
        "MEASURED COST OF ITS ABSENCE BEFORE IT LANDED, kept as the record of why it matters, and "
        "it is NOT 'the world model did not learn': WORLD's loss IS in "
        "the objective -- spine/loop.py::_flush adds it to `total` -- and it is computed on "
        "LM.embed's OUTPUT rather than a detached copy, so it reaches the language model whether or "
        "not anything steps a world tensor. At initialisation, one seed, 4 windows of 64 tokens at "
        "the shipped defaults, the world loss's gradient norm on emb.weight was 0.005194 against "
        "the language-modelling loss's own 0.006371 -- 45% of the embedding's total, and it touches "
        "nothing else in the model. So a FROZEN RANDOM network supplied nearly half the training "
        "signal to the lowest layer of the language model, for every run this tree has taken, while "
        "max|delta| over 60 windows read exactly 0.0 for encoder, qproj, preds and keys. With the "
        "method in place those same 60 windows move preds by 7.955e-02 and the encoder by "
        "8.08e-02. world_proj read 0.0 there because its only consumer is WORLD.forecast, which "
        "had no call site until Q-WORLD-10 was resolved; it is now born ZERO and moves from the "
        "first flush (|W| 1.027 after 60 windows).",
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
    "RUN.Timing.span":
        "CALLED BY spine/loop.py SINCE 2026-09-24, around the per-window and per-flush components "
        "(sig.train_step, sig.encode, dom.observe, tok.on_window, fab.manage, the flush and six "
        "calls inside it, the periodic save), outside every order-table row: a span is "
        "instrumentation around rows, not a row, which is why it stays listed here. The text below "
        "is its history. IT ARRIVED BEFORE ITS CALLER ON PURPOSE. RUN.mode has to "
        "return a RunMode, RunMode carries a `timing`, and the contract's RECORD TYPES block names "
        "span() and spans() as that object's surface -- so writing `mode` writes these two, one "
        "increment before the rows that call them. THE ALTERNATIVE WAS WORSE: a RunMode carrying "
        "None until the loop lands would make every future call site test for it, which is the "
        "second-code-path this record exists to remove (span() returns a context manager whether "
        "profiling is on or off precisely so the hot path has no branch). ITS ONE ARGUMENT, `name`, "
        "HAS NO PRODUCER AND WILL NOT HAVE ONE: it is a literal written at the call site -- the "
        "label of the component being timed ('encode', 'route', 'backward') -- so it is not a value "
        "any entry point returns and no row can name a producer for it. What is missing is the "
        "CALLER, not the argument: the flush body's per-component spans -- which is the caller "
        "spine/loop.py now is. `spans()` is read by RUN.bench_summary, which takes `timing` and is "
        "itself a stage-R row.",
    "RUN.Timing.spans":
        "CALLED at R since 2026-09-24: by RUN.bench_summary, to which spine/loop.py::_report now "
        "passes the Timing (it passed none, so RUN_BENCH=1 RUN_PROFILE=1 printed 'RUN_PROFILE is "
        "off'), and by _report itself as the RUN.Timing.spans row when RUN_PROFILE is on -- both "
        "outside any order-table row. `timing=None` in bench_summary's signature is the "
        "not-profiled case, and an EMPTY dict from it is a "
        "different statement from an absent one: 'measured nothing' versus 'did not measure'. That "
        "distinction is why RunMode always carries a Timing rather than sometimes carrying None.",
    "EVAL.curve_probe":
        "P5 (eval), AND SINCE 2026-09-27 A SCOPE DEFERRAL, NOT A GAP. Every argument it takes now "
        "has a producer in this file: units_by_domain comes off the retention probe's pinned "
        "ProbeSet (_holdout_units), logits_fn is the memory-off closure "
        "_logits_fn(sysm, use_memory=False), step is RunClock.step and rng an 'eval' child -- the "
        "join this reason used to say nothing produces (Q-EVAL-12). It is not built because no row "
        "of the register's section 8 builds it (the priority order of its section 2): the "
        "learning curve at EVAL_CURVE_EVERY is a second held-out reading beside the retention "
        "probe, on unpinned windows, and building it now would be a second instrument answering "
        "one question. The 'curve' period stays in RUN.new_cadences' mapping so the ledger "
        "carries a key with zero checks.",
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
    "EVAL.coherence":
        "P6 (eval), AND SINCE 2026-09-27 A SCOPE DEFERRAL, NOT A GAP. Its four arguments all have "
        "producers now: logits_fn is _logits_fn's closure and units_by_domain the probe's pinned "
        "held-out windows (Q-EVAL-12), `encode` is _sig_encode_fn's callable (the SAME one "
        "DOM.rekey takes), and rng an 'eval' child. It is not built because no row of the "
        "register's section 8 builds it (the priority order of its section 2). THE `sample` "
        "PARAMETER WENT 2026-09-02, Q-EVAL-10 RESOLVED: a Sample is the printed generations, so the "
        "signature invited the one argument the docstring forbids -- and EVAL.generate, which "
        "returns that Sample, is itself built since 2026-09-27, which is exactly why the "
        "parameter had to go first.",
    "EVAL.verdicts":
        "P6 (eval). Three of its four arguments -- silhouettes, affiliation, coherence_reading -- "
        "have no producer in the tree; the fourth, domain_sizes, comes from DOM.census, which the "
        "R stage above already collects.",
    "EVAL.wrongness_probe":
        "P6 (eval). Takes a `store_copy` so the instrument cannot edit what it measures; nothing in "
        "MEM's surface produces one -- the eleven entry points are open_store, write, read, "
        "encode_queries (2026-09-27), blend, maintain, apply_domain_plan, judge, census, state_dict "
        "and rekey_period, and no copy -- "
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
    "MEM.judge":
        "P4/P5 (memory + eval). `scorer(ctx, src) -> logits` is required by the DEFAULT arm: "
        "MEM.verify defaults to 'selfcon' and memory/api.py::judge says the scorer must be THE SAME "
        "FORWARD PATH TRAINING USED, passed in and never constructed there (M47). SINCE 2026-09-27 "
        "THAT PATH EXISTS AS A CLOSURE, AND ITS ARITY IS THE GAP: _logits_fn's convention is "
        "fn(x, *, prefix_bytes) (Q-EVAL-12) -- it routes on the bytes BEFORE the window, through "
        "SIG.encode and DOM.nearest -- and a STORED entry has no prefix bytes. What it carries is "
        "Store.src, the domain it was written under, which is why the declared shape is "
        "`scorer(ctx, src)` (Q-MEM-8/Q-MEM-10, 2026-09-02, and EVAL.wrongness_probe's `scorer` takes "
        "the same two arguments). A scorer of that arity routes on the stored id instead of on a "
        "signature, which is a second routing rule nobody has ruled on, so no closure is formed "
        "here. Because `scorer` carries a default, no check asks about it: a row calling "
        "judge(mem, store) passes every check in the tree and yields n_checked = 0 forever, which "
        "memory/api.py::judge itself names as the inert state. That is precisely why this is a "
        "deferral and not a row with a note. "
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
    "CAP.observe":
        "P4 (fabric + capacity). THREE arguments have no producer, not two: `elapsed_windows` was "
        "omitted from this reason until K12 counted them. It is the valve's PIN DELTA -- how many "
        "windows since the last call -- and RunClock counts windows without naming that difference, "
        "which is the whole of the pin-clock story: the delta is what derive.pin_tick accumulates, "
        "and typing it was the repair settled on 2026-08-30. "
        "`improving` and `observations` have no producer either. improving is "
        "(slow - fast)/|slow| off the growth controller's two EMAs, which live INSIDE FAB "
        "(fabric/api.py::grow_check runs the same two-sided test) and are on no returned record: "
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
        "P4 (world + opt). `plateau` contradicts the package's own state_dict: world/api.py::state_dict "
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
    "LM.parent_designation":
        "NOT A RUN'S CALL, AND NO ROW OF THIS TABLE WILL NAME IT (2026-09-28, register O17 and "
        "section 8 3.6; docs/04_CONTRACT.md Q-LM-15). It judges a CHECKPOINT, not a System: whether "
        "the checkpoint whose LM wrote `saved_geometry` may be designated B's long-lived parent, "
        "refused by name -- switchably, lm/api.py's REFUSE_CONTEXT_LOCKED_PARENT -- until its "
        "position scheme's context-widening route PASSes on GPU (section 8 5.8). `saved_geometry` "
        "HAS NO PRODUCER IN THE ORDER TABLES AND CANNOT HAVE ONE: it is payload['LM']['geometry'] of "
        "a checkpoint on disk, which the ASSEMBLY rows read only for the checkpoint this run resumes "
        "-- and a run never designates its own parent. Its caller is whatever designates one: the "
        "continue preset's builder, which is not built, and until then tools/designate_parent.py, "
        "which reads the checkpoint through CKPT.load and exits non-zero on the refusal having "
        "written nothing. Deferred at the ARGUMENT, and the argument's producer is outside the run "
        "by design, not missing from it.",
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
    "TOK.splice":
        "seg is System.segmentation -- the Segmentation in force, which the 'segment' ASSEMBLY row "
        "(TOK.tokenize) produced for epoch 0 and every later roll or act replaced; at is the loop's "
        "cursor win_in_epoch * LM.ctx, the index of the unit the next window starts on. Both are "
        "the driver's own state (spine/loop.py::run), not any package's return value (03b S0b).",
    "RUN.RunClock.revise_epoch_length":
        "windows_in_epoch is _windows_in_epoch(sysm) re-taken over the SPLICED Segmentation -- the "
        "same division begin_epoch is handed, named once at compose.py::_windows_in_epoch.",
    "OPT.revise_horizon":
        "run_windows is the root's re-measured run length after an act: RunClock.counters()' step, "
        "plus (the spliced epoch's length - in_epoch), plus the later epochs at that length -- the "
        "projection OPT.build's run_windows made from epoch 0, re-taken at the act.",
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
        "width_units is _signature_width(lm, vocab, ctx=System.sig_ctx) -- "
        "derive.signature_width_bytes over the LM_CTX the lineage's SIG was built at (LM.ctx, but "
        "across a widened lineage the one it started at, which LOOP.sig_ctx carries: Q-LM-15 and "
        "its review) and the MEASURED bytes/token, resolved ONCE here and never recomputed as the "
        "vocabulary grows, which is the C4 repair this package exists for. alphabet_size is "
        "_alphabet_size(sig, lm): 256 under space='bytes', LM.vocab_slots under 'tokens'. Neither is "
        "a row's output because neither is any package's return value -- they are the assembly's "
        "own arithmetic over two packages' frozen Configs and the lineage's record, which is exactly "
        "what the root is for.",
    "SIG.load_state_dict":
        "sidecar is _sidecar(sysm, restored, 'SIG') -- the recorded fields SIG compares its own "
        "state against, read from Snapshot.payload['SIG']['sidecar'], which sig/api.py::state_dict "
        "writes. IT WAS DISARMED UNTIL 2026-09-22, when that lookup read a per-prefix key of the "
        "FLAT manifest instead and could never match: the refusal on "
        "width_units/alphabet_size/space/d/mode could not fire, and _sidecar recorded that on "
        "System.warnings rather than letting a dead guard look armed. A guard that cannot fire must "
        "not look armed, and the repair is that it now can.",
    "FAB.load_state_dict":
        "sidecar is _sidecar(sysm, restored, 'FAB'), from Snapshot.payload['FAB']['sidecar'], which "
        "fabric/api.py::state_dict writes -- slots, rank, dk, signature_dim, the four "
        "FAB.load_state_dict refuses on. Same history as SIG's above and the same repair; the "
        "claim that FAB 'does not even CLAIM to emit a sidecar' was true of an earlier tree and is "
        "not true of this one, which is why the refusal now has a declared origin at both ends.",
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
        "would then be measured through. at_window is this window's 0-based index, so the window "
        "about to be predicted is NOT reached (Q-FAB-7): it read index + 1 until 2026-09-24, and an "
        "anchor could then be drawn from the text the same window's signature was about to route.",
    "SIG.encode":
        "windows is _sample_window(sysm, sig, at_window) -- the st.width_units-wide slice this window "
        "is encoded from, the same object domains/api.py::observe receives as sample_window. "
        "at_window is the window's 0-based index, so the slice ENDS AT ITS FIRST BYTE and holds "
        "none of its targets (Q-FAB-7).",
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
    # Each says what computes it and why no row can. Five of them are on System.__slots__ because
    # they cross a boundary the tables read forwards cannot express (the fourth is
    # shift_at_windows, added 2026-09-02 with Q-FAB-6; the fifth is its Steps twin
    # shift_at_steps, added 2026-09-24 when OPT.maybe_step was first handed a shift_at).
    "RUN.new_cadences":
        "periods is _periods(sysm) -- the EIGHT gates' thresholds. Seven arrive through their OWNING "
        "package's typed accessor (EVAL.curve_period, DOM.manage_period, FAB.manage_period, "
        "MEM.rekey_period, CKPT.save_period, since 2026-09-27 EVAL.retention_period and, since "
        "2026-09-28, DATA.trust_period); the "
        "eighth is RUN.PROGRESS_WINDOWS, a module constant "
        "and not a lever, for the progress/ETA line and the profiler dump (Q-RUN-1, RESOLVED "
        "2026-09-02). A mapping spanning seven packages is precisely the object O10 forbids any one "
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
        "windows_in_epoch is _windows_in_epoch(sysm) -- (len(Segmentation.ids) - 1) // LM.ctx, this file's "
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
        "MEM.d_owner_blocks -- and on the two fabric control arms (FAB_ON=0, FAB_NORM_ONLY=1), "
        "where weights is None by declaration, the window's domain id (`sources`) modulo the same "
        "count, counted per flush as loop.owners_from_domain because it is a different quantity "
        "under the same name (Q-FAB-11). FAB.forward does NOT return it -- FabricOut carries logits, "
        "expert_ids, weights, per_expert_logits, aux_loss and gates -- and the row claimed it did "
        "until K11 refused the claim. It is the one join in this file with no named helper, because "
        "it needs a tensor operation and nothing in src/ imports torch; P4 writes it in the loop and "
        "this entry is what says so. "
        "key_fn is _key_fn(sysm), the same bound callable MEM.maintain takes -- see above. "
        "contexts is the flush's (B, L) TOKEN IDS -- the same `x` LM.encode takes -- tokens is that "
        "cut shifted one token, and surprise is 1 - p_model(true token) at EVERY POSITION, (B, L), "
        "formed by spine/loop.py::_flush from the flush's prediction and `y` -- FabricOut.logits "
        "when the population voted (Q-FAB-8), LM.decode's logits otherwise. "
        "THIS ENTRY SAID SOMETHING ELSE UNTIL THE LOOP CALLED THE ENTRY POINT, AND ALL THREE "
        "CORRECTIONS CAME FROM THE CALL RATHER THAN FROM A READING. It read `contexts` is "
        "LM.encode's `h`; memory/api.py::write refuses a floating (B, L, width) tensor BY NAME and "
        "names this entry as the one that is wrong, because its own contract is that survivors are "
        "encoded AFTER the gate by one key_fn call and key_fn IS LM.encode -- so `h` would be "
        "encoded twice and could not be sliced to MEM_KEY_WIN preceding POSITIONS. It read "
        "`surprise` is the per-window loss LM.lm_loss returned; that is (B,) where the body "
        "requires (B, L) and _require_rows refuses it, and it is a cross-entropy in nats where the "
        "gate ranks a probability complement in [0, 1] -- write_gate=0.3 against a loss of 8.3 "
        "admits every candidate for reasons that have nothing to do with surprise. The LOOP_ORDER "
        "B row had both right all along (\'the flush\'s x and y at _flush_bounds\', \'1 - the "
        "model\'s probability of the true next token ... (:7497-7498)\'), so this was one claim "
        "stated twice and differently, which is the class this table exists to stop and evidently "
        "cannot stop by itself. The third correction is downstream: System.novelty is the "
        "PER-WINDOW MEAN of that same surprise, and the loop had been carrying the per-window LOSS "
        "under that name into FAB.forward, whose own docstring declares \'novelty: (B,) surprise "
        "from the previous step\'. "
        "owners and positions are the loop\'s own joins, above. "
        "areas (defaulted; 2026-09-28, Q-MEM-16) is _window_areas\'s one area id per POSITION, "
        "beside `positions`: TOK\'s Segmentation.labels read through spine/derive.py::area_id over "
        "Stream.area_names -- a join of two packages\' records that no entry point returns, and "
        "MEM never sees an area\'s name.",
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
    # ---- THE RETENTION PROBE'S JOINS (2026-09-27, Q-EVAL-12). Each value below is this file's work
    # over two or three packages' state, which O10 forbids any one package to form; none is a row's
    # return. They are named here because naming them in the rows would restate the signatures.
    "EVAL.pin_holdout":
        "blocks is Areas.holdout -- DATA's per-area held-out blocks, carved and removed by "
        "open_areas -- and seed is RUN.seed. window_bytes and prefix_bytes are the geometry the "
        "snapshot's LOOP.eval recorded, so a child re-pins its parent's windows, and on a fresh run "
        "LM.ctx + 1 and SigState.width_units: the root's arithmetic over LM's frozen Config and "
        "SIG's built state, which is why the row follows SIG's restore row.",
    "EVAL.holdout_probe":
        "units_by_domain is _holdout_units(sysm, ...) -- the arrived areas' pinned (prefix, window) "
        "pairs cut from System.probe_set, each area marked seen_by_parent or not. logits_fn is "
        "_logits_fn(sysm, use_memory=...) -- the memory-off closure at B, both closures at a "
        "resume's start and at R. tokenize_fn is _holdout_tokenize(sysm, view) -- TOK.tokenize bound to "
        "the vocabulary at the view the stream was last cut at (the parent's recorded view for a "
        "resume's first start reading, its own first cut's for a 'resume_own' one), with no labels "
        "and regularize=False, so it draws nothing and "
        "counts tok.segment_remap. step is RunClock.step, units.Windows, stamped on the Readings as "
        "`at`.",
    "EVAL.blowup":
        "series is LOOP.eval's reading history -- one list of control means per area and one of the "
        "all-area mean, whose entry at each arrival re-arms the alarm -- appended by the loop after "
        "every forwarded reading. A running record between calls, like SIG's boundary count, which "
        "no entry point returns.",
    "EVAL.generate":
        "logits_fn is each of the two closures in turn. prompts_by_domain is _gen_prompts(sysm) -- "
        "the report-half pinned windows of the arrived areas, each as its routing prefix, its bytes "
        "and their cut at the last-cut view. rng is "
        "System.gen_rng, rng_for('eval.generate', seed), minted once per System at the 'probe' "
        "stage so a second loop.run over one System does not raise on a duplicate stream.",
    "CKPT.Retention.consider":
        "curve_bpb is the retention probe's forwarded CONTROL mean (HoldoutReading.control_mean) -- "
        "a value the loop holds between the EVAL.holdout_probe row and this one, finite or not "
        "forwarded at all, which no produces column can carry because it is taken and consumed in "
        "one window. step is RunClock.step, units.Windows, as consider requires.",
    # ---- THE MARGINAL CONTRIBUTION'S JOINS (2026-09-28, register §8 3.5; Q-FAB-19). One batch of the
    # retention probe's pinned control items, the memory-off closure bound to it, and the FAB.forward
    # inputs that closure's own pass used: the root's work over EVAL's ProbeSet, TOK, SIG, DOM, LM and
    # WORLD, which O10 forbids any one package to form, and none of it a row's return.
    "FAB.contribution":
        "targets is the batch's ids shifted one: _contrib_material(sysm, arrived)'s y, cut from the "
        "first (EVAL_RETENTION_N + 1) // 2 pinned CONTROL items of every arrived area at the "
        "last-cut view (_holdout_tokenize, booked eval.contrib.cuts) and cut back to one length. "
        "baseline_logits_fn is _contrib_baseline(sysm, fn, x, prefix_bytes): the memory-off closure "
        "_logits_fn(sysm, use_memory=False, book='eval.contrib') bound to that batch, run with any "
        "autocast its caller holds turned off, as the closure runs standalone. baseline_loss is "
        "the mean LM.lm_loss returns for those logits against targets -- the one callable's own "
        "loss, which FAB.contribution re-scores and refuses to measure against where it differs "
        "(ISSUES P1-H11). h, signature, novelty, domain_id, live_domains and step_windows are the "
        "FAB.forward inputs that baseline pass used, taken off it through the closure's `route` "
        "dict: LM.encode's h over the batch with WORLD.forecast's extra, SIG.encode of each row's "
        "prefix units, novelty ZEROS, DOM.nearest of the first row's signature, System.live_domains "
        "and clock.step + 1, the closure's routing clock. head is the closure's counted head "
        "(fn.head), LM.decode at the live vocabulary boundary. candidates is left at None, the next "
        "FAB_CONTRIB_MAX past-grace experts off Population's rotating cursor.",
    # ---- THE SOURCE-RELIABILITY BOOK'S JOIN (2026-09-28, Proposal 04 SR3, Q-DATA-11).
    "DATA.claims_observe":
        "focus is System.focus, the 'focus' ASSEMBLY row's Focus. units and sources are "
        "_trust_units(sysm, lo, hi) -- the TOK units' bytes of System.segmentation over ids[lo:hi], "
        "cut out of Stream.bytes through Segmentation.byte_pos, and each unit's source name off "
        "Stream.sources (None for a unit whose bytes straddle two sources): two packages' records "
        "joined, which O10 forbids either to form, and the reason 04 section 5's (ids, decode) "
        "became bytes -- DATA may not import TOK. lo is the book's cursor as the loop carries it, "
        "0 after an epoch roll; hi is where the windows cut so far end; at is lo, so DATA can tell "
        "a continuation from a new stream and refuse anything else. step is RunClock.step, "
        "units.Windows.",
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
                 # `lm_load` and `opt_load` ARE THE TWO RESTORE VERDICTS, bound for the same
                 # reason and with the same history: LM.load_state and OPT.load_state refuse BY
                 # RETURNING a LoadReport, and both calls were bare expression statements until
                 # 2026-09-24, so a refused restore trained a random model or cold moments with
                 # nothing printed. A refusal is carried onto `refusals`; the records stay here
                 # so a reader can see what a PASSING restore did (rows widened, moments padded,
                 # a horizon changed). None on a fresh run.
                 "lm_load", "opt_load",
                 # `grow_gates` IS THE LAST FAB.grow_check CALL'S GrowReport.gates, and ONLY that
                 # tuple -- never the record. Same history as the three above: the call was a bare
                 # expression statement until 2026-09-24, so its per-call gates were computed and
                 # dropped, and spine/loop.py::_report now renders them at R. None until the first
                 # flush. Not a value that crosses to a later row, and not on CKPT's save path.
                 "grow_gates",
                 # THE FIVE VALUES THAT CROSS A BOUNDARY THE ORDER TABLES CANNOT EXPRESS, each
                 # named by the row that consumes it. `produces` reads FORWARDS -- an argument is
                 # supplied by an EARLIER row -- so a value produced at A and consumed at B, or
                 # produced by one flush and consumed by the next, has nowhere to live but here:
                 #   due        TOK.on_window's Due, asked PER WINDOW and acted on PER FLUSH by
                 #              mint_burst / judge_probation / the retok. batch_windows of them
                 #              reach one flush, and the root OR-s them PER CADENCE KEY (mint,
                 #              retok, probation; `frozen` from the last window, which is the same
                 #              value because it is monotone) -- Q-TOK-12, ruled 2026-09-02. The
                 #              OR is here and not at a call site because the root is the only
                 #              thing that can see a batch. tok.due_dropped's flush-discard
                 #              share must read 0; its other share is the retoks no roll reached.
                 #   novelty    the PREVIOUS flush's mean surprise, which is what FAB.forward's
                 #              `novelty` and MEM.write's `surprise` are (:7499). A backwards edge.
                 #   token_seen the per-token appearance counter LM.anchor_term takes under that
                 #              name and TOK.judge_probation takes as `appearances` -- ONE tensor,
                 #              owned by the loop, returned by no entry point (C5).
                 #   shift_at_windows
                 #              THE STEP OF THE LAST SELF-INFLICTED SHIFT, as units.Windows, added
                 #              2026-09-02 with Q-FAB-6. Q-FAB-6 names THREE sites in three
                 #              different stages -- the E draw row's resample, the retok, and OPT's
                 #              LR restart -- and only the first stamps today: the retok is deferred
                 #              to that same roll (Q-RUN-8) and the LR restart stamps nothing. It is
                 #              consumed by FAB.grow_check's
                 #              `shift_at` on a LATER flush, which is both a backwards edge and a
                 #              cross-stage one, so no `produces` column can reach it. It is a
                 #              SECOND OBJECT for the same event: OPT.maybe_step's `shift_at` is
                 #              units.Steps off clock.opt_steps and this one is units.Windows off
                 #              clock.step, because FAB's cooldown is Windows and mixing them
                 #              raises UnitError rather than being batch_windows-fold wrong. Two
                 #              typed stamps of one event is the point, not a duplication.
                 #   shift_at_steps
                 #              THE SAME EVENT AS units.Steps(clock.opt_steps + 1) -- the first
                 #              step the shift applies to, which maybe_step prices -- for OPT.maybe_step's
                 #              `shift_at`, added 2026-09-24. Until then the roll stamped only the
                 #              Windows twin and maybe_step was called with no shift_at, so
                 #              OPT_LR_SHIFT_WARM was inert on every multi-epoch run (RUN_EPOCHS=2
                 #              DATA_RESAMPLE=1 OPT_LR_SHIFT_WARM=20: opt.shift.notifications 0).
                 #              clock.opt_steps is seeded from OPT's restored opt_step on resume, so
                 #              the stamp is on the counter the schedule subtracts it from.
                 "due", "novelty", "token_seen", "shift_at_windows", "shift_at_steps",
                 # `retok_pending` IS A DUE THAT OUTLIVES ITS FLUSH. TOK's retok cadence fires at
                 # B and the act -- re-segmenting the stream with the grown vocabulary -- can only
                 # happen at the E stage's epoch roll, because changing the segmentation mid-epoch
                 # changes how many windows the epoch holds and RunClock.begin_epoch cannot be told
                 # a new length without zeroing the epoch cursor. So the event waits here, across
                 # an arbitrary number of flushes, which is a backwards edge no `produces` column
                 # can express -- the same reason `due` and `shift_at_windows` are on this record.
                 # AN int, THE NUMBER OF FIRES WAITING, AND IT WAS A bool UNTIL 2026-09-24: four
                 # fires read as one, so the roll's tok.retok_satisfied_by_roll and the end-of-run
                 # tok.due_dropped each moved by 1 however many retoks had been raised. The roll
                 # adds it to the first and zeroes it; the end of the run adds what is left to the
                 # second. None until spine/loop.py::run seeds 0.
                 "retok_pending",
                 # `rev_at_last_seg` IS THE MATCH-TABLE REVISION DOM's TOKEN HISTOGRAMS WERE COUNTED
                 # UNDER (2026-09-24), mirrored off spine/loop.py::run's local so the checkpoint can
                 # say whether the table moved since the last segmentation. A resume re-segments at
                 # the SAVED (grown) vocabulary, so when it had moved the restored histograms were
                 # counted under a table the child's stream is not cut at; compose then sets -1, which
                 # no revision equals, so the first roll tells DOM. None: a fresh run, or a checkpoint
                 # that predates the record (the loop then starts from the live revision and the roll
                 # warning says the provenance is unknown).
                 "rev_at_last_seg",
                 # THE PER-EPOCH SEGMENTATION LOG (03b S0b): {"epoch", "events"}, each event the cut
                 # or splice with its view and dropout-stream state. Written at the epoch's first
                 # segmentation, appended by every act, checkpointed by the loop, replayed by a
                 # continuing mid-epoch resume. `resume_pos` is (in_epoch, windows_in_epoch) when this
                 # process continues a parent's epoch, else None.
                 "seg_log", "resume_pos",
                 # THE LOOP'S CARRIED STATE (03b S0b): the values spine/loop.py::run carries from one
                 # window or flush to the next -- the last flush's per-window losses, the pending Due,
                 # the shift stamps, MEM's probe and pressure, the live domain count, SIG's boundary
                 # run, FAB's manage losses. Mirrored here before every save and checkpointed; a
                 # continuing mid-epoch resume puts them back, because the uninterrupted run would
                 # have read them at the very next window.
                 "loop_carried",
                 # THE MEM REMAP AN ACT HANDS THE NEXT FLUSH (03b S0b): a callable re-cutting stored
                 # contexts at the act's view, consumed by MEM.maintain(remap=) and cleared.
                 "mem_remap",
                 # `process_dtype` IS AN OBSERVATION AND NOT A DECISION, and it is here because
                 # RUN_AMP had no did-it-fire surface and was inert for the life of the driver
                 # because of it. Process.amp_state says what was ASKED FOR and what
                 # RUN.process_setup DECIDED; NEITHER of those can say whether a caller ever
                 # entered Process.autocast, and no caller did -- found on a GPU by two arms of
                 # sweep_gpu.sh returning bit-identical loss curves. spine/loop.py::_flush writes
                 # the dtype of the tensor the step actually produced here, once per flush, and
                 # run.py prints it beside amp_state. It is on System rather than on Process for
                 # the reason `warmup` is: it is a RESULT THE ROOT OWNS, measured after the frozen
                 # record was built, and a second writable field on Process would let a report
                 # quote a precision nothing had run in.
                 "process_dtype",
                 # THE VALVE POSITION THIS DRIVER HAS ALREADY ACTED ON, which is what makes
                 # TOK.lift_vocab_cap the EVENT its own docstring says it is ("AN EVENT, NOT A
                 # PERIOD ... CAP calls this function when it lifts"). The LOOP_ORDER row for
                 # CAP.caps spells the wire ("-> ... TOK.lift_vocab_cap(to=...)") and a wire has no
                 # frequency, so without this field the only call site available was PER FLUSH --
                 # a quarter of a million calls to announce a lift that happened once, with
                 # tok.cap_lift reading present-and-0 for the whole run and no way to tell that
                 # from a route that ran and moved nothing. It holds Caps.vocab and NOT the cap
                 # lift_vocab_cap returned: the two differ whenever the vocabulary's own ceiling is
                 # tighter than the valve's position, and storing the clamped answer would make
                 # every subsequent flush see a difference and fire the event again, forever.
                 # None UNTIL THE FIRST FLUSH, AND THE FIRST FLUSH IS A BASELINE AND NOT A LIFT: a
                 # lift is a CHANGE, so the first observation has nothing to be a change from.
                 "cap_vocab_seen",
                 # THE RETENTION PROBE'S STATE (2026-09-27, Q-EVAL-12), six slots:
                 #   probe_set      EVAL.pin_holdout's ProbeSet, pinned ONCE at the 'probe' stage;
                 #                  empty (with its reason) when the probe is off, no area holds a
                 #                  block, or no half of one can hold a window behind its prefix.
                 #   eval_books     the root's own did-it-fire book for the probe -- eval.holdout.*,
                 #                  eval.mem.*, eval.blowup.* and eval.generate.* -- EMPTY when the
                 #                  probe is not armed, which is this tree's ABSENT; seeded 0 when it
                 #                  is. No package can keep it: the counts are of calls the ROOT
                 #                  makes across five packages.
                 #   probe_reading  the latest forwarded CONTROL-half Reading, a BACKWARDS edge like
                 #                  novelty: set after one flush, read as OPT.maybe_step's best_bpb
                 #                  by the next. None until the first reading, or put back from
                 #                  LOOP.eval's `reading` on a resumed System (Q-OPT-13).
                 #   live_domains   DOM.census's n_live as the loop last carried it, mirrored here so
                 #                  the closures route with the count the next training window will
                 #                  use; 1 until the first dom.manage pass, like the loop's own.
                 #   gen_rng        rng_for('eval.generate', seed), minted once per System at the
                 #                  'probe' stage where generation can run, so a second loop.run
                 #                  over one System does not mint it twice (RngError).
                 #   eval_carried   the loop's probe state as the snapshot carried it (LOOP.eval)
                 #                  and as the loop mirrors it before every save: the pinned
                 #                  geometry, the arrived areas, the last (epoch, phase) read, the
                 #                  last-cut view, the live-domain count, the reading series, the
                 #                  last forwarded Reading and the books. None on a fresh run, on a
                 #                  pre-probe checkpoint, and on a probe-off run whose snapshot
                 #                  carries none; on a probe-off run whose snapshot does, ONLY its
                 #                  geometry and its book's counts, passed on unchanged -- a run
                 #                  that reads nothing does not write its parent's reading state
                 #                  as its own (the 'probe' stage says why).
                 "probe_set", "eval_books", "probe_reading", "live_domains", "gen_rng",
                 "eval_carried",
                 # THE SOURCE-RELIABILITY BOOK (2026-09-28, Proposal 04 SR3; Q-DATA-11): DATA.Focus,
                 # made at the 'focus' stage by DATA.new_focus and filled in place by both
                 # DATA.claims_observe rows; the C row's DATA.stream_state(focus=) checkpoints it.
                 # A Focus holding nothing at DATA_TRUST='off'.
                 "focus",
                 # A DECLARED CONTEXT WIDENING (2026-09-28, register §8 3.6; Q-LM-15): (the parent's
                 # LM_CTX, this run's) when the geometry gate widened lm.ctx -- which it does only at
                 # LM_CTX_WIDEN=1 -- and None everywhere else, a fresh run included. Read at the
                 # `segment` stage (refused across a continuing mid-epoch resume) and for the
                 # startup notice. Not checkpointed: it describes THIS resume, and a child of this
                 # run widens from this run's LM_CTX or not. (It was read at the `signature` stage
                 # too, until Q-LM-15's review: see sig_ctx.)
                 "ctx_widening",
                 # THE LM_CTX SIG's WIDTH IS DERIVED FROM (2026-09-28, Q-LM-15's review): this run's
                 # on a fresh run, and on a resume the lineage's -- LOOP.sig_ctx where the checkpoint
                 # carries it, the recorded lm.ctx where it does not. The `signature` stage builds SIG
                 # at signature_width_bytes(sig_ctx, the adopted bytes/token), and spine/loop.py's
                 # _payload writes it into LOOP wherever a widening has moved it off this run's
                 # LM_CTX. Until the review the stage took the parent's LM_CTX only at the resume
                 # that widened, and ctx_widening is not checkpointed, so every later resume of the
                 # widened lineage resolved SIG at its own LM_CTX and SIG's restore refused it --
                 # the child's epoch boundary, its mid-epoch save and a second widening alike.
                 "sig_ctx")

    def __init__(self, configs, wires, warnings):
        for name in self.__slots__:
            setattr(self, name, None)
        self.configs, self.wires, self.warnings = configs, wires, warnings
        self.refusals, self.stage = [], "configs"

    def __repr__(self):
        return (f"<System {len(self.configs or ())} config(s), {len(self.wires or ())} wire(s), "
                f"stage={self.stage!r}>")


class RefusedRun(RuntimeError):
    """A System that carries startup refusals, STOPPED where the refusals were taken.

    RAISED BY compose() AND NOT MERELY LISTED, SINCE 2026-09-24. RUN.startup_refusals has always
    said "the entry point raises on a non-empty list BEFORE ANY TENSOR IS ALLOCATED", and compose()
    appended the list to System.refusals and kept building: driven at RUN_EPOCHS=2 with resampling
    off, it built the 10,130,057-parameter model, ran the SIG warm-up and returned
    stage='assembled' carrying the refusal, so only a driver that read the list (run.py) stopped.
    `system` is the PARTIALLY BUILT record, so run.py still prints the banner, every refusal taken
    UP TO THIS STOP and exits 2; `stage` names how far the assembly got; `refusals` is the list
    itself. A later stop's refusals (CAP's, the restores', the finished resume) are not on it when
    an earlier stop raised: each stop pre-empts the ones after it (Q-RUN-13).

    A RuntimeError SUBCLASS, deliberately: spine/loop.py::run raises the same type on a System that
    reaches it carrying refusals by another route (the `restored=` override, a test that appends
    one), and a caller written against the RuntimeError it raised before keeps catching it.
    """

    def __init__(self, system, stage):
        self.system, self.stage, self.refusals = system, stage, list(system.refusals)
        super().__init__(
            f"compose: {len(self.refusals)} startup refusal(s) at stage {stage!r}, so nothing past "
            f"it was built -- " + " || ".join(self.refusals))


def _stop_if_refused(sysm):
    """Raise RefusedRun when the System carries a refusal. Called at the three points compose()
    takes one: after the config-only RUN/WORLD refusals (before any model tensor), after
    CAP.startup_refusals (which needs the built population, so it can only follow allocation),
    and after the restore and finished-resume refusals, before the SIG warm-up. AND AT A FOURTH,
    ONLY ON A CONTINUING MID-EPOCH RESUME (2026-09-27, Q-DATA-9): at the `segment` stage, before
    the log's replay, where a hold-out admission or a redrawn stream that is not the parent's is
    refused -- neither needs the model, and the replay would cut the parent's log over other text.
    A context widening across such a resume stops there too (2026-09-28, Q-LM-15), first."""
    if sysm.refusals:
        raise RefusedRun(sysm, sysm.stage)


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


def _stream_digest(stream):
    """A digest of one epoch's DATA.Stream -- its bytes and its segment table -- for the segmentation
    log, so a continuing resume can tell whether it redrew the stream its parent was reading.

    WHY IT EXISTS (2026-09-27, Q-DATA-9). The log replays the parent's cut and splices over whatever
    stream the `stream` row redrew, and until this digest the only check was the rebuilt LENGTH
    against the saved one (the `epoch0` stage). A redraw that moved the bytes and kept the window
    count trained on other text at the saved cursor with nothing said; one that moved the count died
    on a RuntimeError naming no lever. The fresh log and stage E's roll record this in the epoch's
    first event, and a continuing resume compares it before it replays anything.

    WHAT IS HASHED: Stream.bytes; then, per segment, its start (8 bytes, little-endian), its area
    label (utf-8) and a separator; then the stream's length. Stream.labels is one label PER BYTE,
    constant within a segment, so the segment table covers the bytes and every label exactly at
    O(segments) cost -- and a stream that moved only one segment's label digests apart. blake2b under
    its own `person`, so it cannot collide with the tree's other blake2b uses.
    """
    h = hashlib.blake2b(digest_size=16, person=b"data.stream")
    h.update(stream.bytes)
    for s in stream.splice_starts:
        h.update(int(s).to_bytes(8, "little"))
        h.update(str(stream.labels[int(s)]).encode("utf-8"))
        h.update(b"\x00")
    h.update(len(stream.bytes).to_bytes(8, "little"))
    return h.hexdigest()


def _seg_event(vocab, kind, at=None, stream=None):
    """One entry of the per-epoch segmentation log (03b S0b): what was cut, where, at which view,
    and the BPE-dropout stream's state just before the cut, so a resume can cut it again exactly.

    THE EPOCH'S FIRST EVENT ALSO CARRIES `stream` (2026-09-27, Q-DATA-9): _stream_digest of the
    Stream it cuts, passed by the two places that open a log -- compose's fresh log and stage E's
    roll. A splice cuts the same Stream again and carries none. No draw and no counter: a dict key."""
    r = getattr(vocab, "dropout_rng", None)
    size, gone = tok_api.view_of(vocab)
    event = {"kind": kind, "at": None if at is None else int(at), "view": [size, list(gone)],
             "rng": None if r is None else (r._r.getstate(), int(r._draws))}
    if stream is not None:
        event["stream"] = _stream_digest(stream)
    return event


def _set_dropout_state(vocab, state):
    r = getattr(vocab, "dropout_rng", None)
    if r is not None and state is not None:
        r._r.setstate(state[0])
        r._draws = int(state[1])


def _replay_segmentation(tok, vocab, stream, log):
    """Rebuild the Segmentation a parent held from its per-epoch log: the epoch's cut at its view,
    then every act's splice at its view, each after rewinding the dropout stream to where it stood.
    The dropout stream is then left where the parent's stood at the save (log['rng_now'])."""
    seg = None
    for event in log["events"]:
        view = (int(event["view"][0]), tuple(int(x) for x in event["view"][1]))
        _set_dropout_state(vocab, event.get("rng"))
        if event["kind"] == "tokenize":
            seg = tok_api.tokenize(tok, vocab, stream.bytes, stream.labels, regularize=True,
                                   view=view)
        else:
            seg = tok_api.splice(tok, vocab, seg, stream.bytes, stream.labels, at=int(event["at"]),
                                 regularize=True, view=view)
    _set_dropout_state(vocab, log.get("rng_now"))
    return seg


def compose(environ=None, *, restored=None):
    """Resolve every Config, then build every object, handing each package what it needs.

    Returns a System. Raises NotImplementedError from the first unimplemented stub, with
    System.stage on the partially built record naming how far it got -- so the failure says which
    package owes what rather than "something is missing". Raises RefusedRun when a startup refusal
    is taken, at the first of three points past which the refusal would otherwise be built over
    (see _stop_if_refused; a continuing mid-epoch resume has a fourth, at the `segment` stage), so
    a returned System never carries a refusal. Raises
    spine/gate.py::NotBuilt from the package that owns a declared-and-not-built arm.

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
    # Neither can live in a levers.py, and both must fire BEFORE anything is allocated -- WHICH IS
    # NOW WHAT HAPPENS, AND UNTIL 2026-09-24 IT WAS ONLY WHAT THIS COMMENT SAID: the list was
    # appended and the assembly carried on through the model build and the SIG warm-up (driven at
    # RUN_EPOCHS=2 with resampling off: stage 'assembled', 10,130,057 parameters, 50 warm-up
    # steps, then loop.run trained 6 windows). Both depend on Configs alone, so they stop here.
    sysm.stage = "refuse"
    sysm.refusals = list(run_api.startup_refusals(run, disk_stream=bool(data.resample)))
    sysm.refusals += list(world_api.startup_refusals(world, ctx_tokens=int(lm.ctx)))
    # A DAMPING SOURCE THAT CAN NEVER PRODUCE IS REFUSED BY NAME (2026-09-27, Q-OPT-13): a check over
    # two packages' frozen Configs, so it is the root's and it is taken here, before any tensor.
    # OPT_DAMP_SOURCE='probe' asks OPT to judge restarts on the retention probe's control mean, and
    # at EVAL_RETENTION_EVERY=0 there is no probe -- the armed-but-inert state this tree refuses
    # rather than runs. (Over an armed probe that pinned no window it is refused at the 'probe'
    # stage, where that can be known, since the flip's review, 2026-09-29.)
    if str(opt.damp_source) == "probe" and int(ev.retention_every) <= 0:
        sysm.refusals.append(
            f"OPT_DAMP_SOURCE='probe' with EVAL_RETENTION_EVERY={int(ev.retention_every)}: the "
            f"damping would judge every restart on the retention probe's control mean, and the "
            f"probe is off, so no Reading can ever arrive. Set EVAL_RETENTION_EVERY above 0 "
            f"(1000 is the register's 04-6.2 cadence, 160 the only measured one), or leave "
            f"OPT_DAMP_SOURCE at 'off'.")
    # FAB.contribution'S TWO CONFIG-ONLY REFUSALS (2026-09-28, register §8 3.5; Q-FAB-19), taken here
    # for the same reason: each is a check over two packages' frozen Configs. FAB_CONTRIB=1 measures
    # on the retention probe's pinned control half and at EVAL_RETENTION_EVERY=0 nothing is pinned,
    # so it would run armed and inert on every pass (FAB_CONTRIB=1 over an armed probe that pinned no
    # window is refused at the 'probe' stage, where that can be known). FAB_FADED_CULL='contrib' removes a
    # faded-area expert only on a MEASURED contribution, and at FAB_CONTRIB=0 nothing measures one,
    # so it would keep every such removal -- 'defer' under another name.
    if bool(fab.contrib) and int(ev.retention_every) <= 0:
        sysm.refusals.append(
            f"FAB_CONTRIB=1 with EVAL_RETENTION_EVERY={int(ev.retention_every)}: FAB.contribution "
            f"measures each expert on the retention probe's pinned control half, and the probe is "
            f"off, so nothing is pinned to measure on. Set EVAL_RETENTION_EVERY above 0 (any "
            f"positive value pins the probe's windows; contribution reads them on the fab.manage "
            f"cadence, not the probe's), or leave FAB_CONTRIB=0.")
    if str(fab.faded_cull) == "contrib" and not bool(fab.contrib):
        sysm.refusals.append(
            "FAB_FADED_CULL='contrib' with FAB_CONTRIB=0: the rule removes a faded-area expert only "
            "where FAB.contribution has measured it at or below 0, and with the measurement off "
            "none ever is -- every such removal would be kept, which is FAB_FADED_CULL='defer' "
            "under another name. Set FAB_CONTRIB=1 (with the retention probe armed), or choose "
            "FAB_FADED_CULL='defer' or 'as_is'.")
    _stop_if_refused(sysm)

    # -- 4. geometry, then the corpus -------------------------------------------------------------
    sysm.stage = "geometry"
    sysm.geometry = lm_api.resolve(lm)

    sysm.stage = "corpus"
    sysm.areas = data_api.open_areas(data, seed=int(run.seed))
    if "DATA" in saved:
        sysm.stage = "restore.data"
        data_api.restore_stream_state(data, sysm.areas, saved["DATA"])
        # THE ONE HOLD-OUT ADMISSION IS SAID, BEFORE THE FIRST WINDOW (2026-09-27, Q-DATA-9; the
        # Q-DOM-1 precedent). DATA counts and names it and prints nothing; the root holds the
        # warnings. What the operator must hear is the contamination: the parent trained on every
        # byte of each admitted block.
        _adm = list(sysm.areas.counters.get("data.holdout_admitted_names") or ())
        if _adm:
            sysm.warnings.append(
                f"DATA_SYNTH_HOLDOUT ADMITTED {len(_adm)} AREA(S) THE CHECKPOINT HELD NOTHING OUT "
                f"OF: {', '.join(_adm)} (data.holdout_admitted, Q-DATA-9). The parent recorded key "
                f"None and size 0 for each -- DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=0 -- and "
                f"this run carves a block out of each under the real sources' law, so each of those "
                f"bodies is a block shorter than the parent's. THE PARENT TRAINED ON THOSE BYTES: "
                f"every admitted block is text this lineage has seen, so a held-out reading on it "
                f"is not a clean held-out number for the lineage. The admission holds at an epoch "
                f"boundary, where the epoch is drawn fresh; a continuing mid-epoch resume across it "
                f"is refused at the `segment` stage.")

    # -- 5. the vocabulary, which MEASURES bytes/token --------------------------------------------
    # Ordered here and not earlier because build_vocabulary needs the corpus, and ordered before
    # DATA.data_plan and SIG.build because both need the measurement. ON A RESUME THE MEASUREMENT IS
    # THE PARENT'S: build_vocabulary adopts the value the vocabulary file recorded (tok.bpt_adopted),
    # because re-measuring on the replayed vocabulary -- grown by every online mint -- moved
    # _signature_width's answer and SIG refused the resume (192 recorded, 194 resolved, on every
    # default run resumed after its window-201 mint). derive.bytes_per_token is the
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
    sysm.ctx_widening = None
    sysm.sig_ctx = int(lm.ctx)
    if restored is not None:
        # THE REPORT IS READ FOR ONE FIELD (2026-09-28, register §8 3.6; Q-LM-15): lm.ctx. One the
        # gate WIDENED is a declared widening -- the manifest records lm.ctx MAY_WIDEN only at
        # LM_CTX_WIDEN=1 -- and two rows below act on it: the `segment` stage refuses it across a
        # continuing mid-epoch resume, and the root prints what it does to every windows cadence.
        # (parent ctx, this run's ctx), or None.
        _gate = ckpt_api.check_geometry(ckpt, restored, sysm.manifest)
        for _field, _rule, _was, _now in _gate.widened:
            if _field == "lm.ctx":
                sysm.ctx_widening = (int(_was), int(_now))
        # AND ITS RECORDED VALUE IS SIG's CONTEXT WHERE THE LINEAGE CARRIES NONE (Q-LM-15's review).
        # SIG's encoder was trained at signature_width_bytes(the LM_CTX its lineage started at, the
        # adopted bytes/token), and SIG's restore refuses any other width. A widened run writes that
        # LM_CTX into LOOP as `sig_ctx`, so every later resume of the lineage -- its epoch boundary,
        # a mid-epoch save, a second widening -- builds SIG at it; a checkpoint without the key is
        # one whose SIG was built at its own recorded lm.ctx: every one written before this ruling,
        # and every unwidened lineage's, which writes the payload it wrote before. Read at every
        # resume, not only at the one that widens: ctx_widening describes THIS resume and is not
        # checkpointed, which is how a widened child's own checkpoint came to be refused by SIG at
        # its own LM_CTX (87 units recorded, 175 resolved) until the review.
        _sig_ctx = (saved.get("LOOP") or {}).get("sig_ctx")
        for _field, _rule, _was, _now in _gate.checked:
            if _field == "lm.ctx":
                sysm.sig_ctx = int(_was) if _sig_ctx is None else int(_sig_ctx)

    sysm.stage = "plan"
    sysm.plan = data_api.data_plan(
        data, sysm.areas, epochs=int(run.epochs), win_tokens=int(lm.ctx),
        bytes_per_token=float(sysm.vocab.bytes_per_token))

    # -- THE SOURCE-RELIABILITY BOOK (2026-09-28, Proposal 04 SR3; docs/04_CONTRACT.md Q-DATA-11) ---
    # After the plan, as 04 §5 places the row, and the ONLY place the book is put back:
    # DATA.restore_stream_state ran at `restore.data`, before any Plan existed, so the checkpoint's
    # state['focus'] is handed here as `restored`. At DATA_TRUST='off' nothing is allocated; 'loss'
    # and 'loss+draw' are refused here with NotBuilt, before any tensor is built.
    sysm.stage = "focus"
    sysm.focus = data_api.new_focus(data, sysm.areas, sysm.plan,
                                    restored=(saved.get("DATA") or {}).get("focus"))

    # -- 7. EPOCH 0's MATERIAL, drawn here because two rows below need it -------------------------
    # OPT.build needs run_windows measured from a segmentation that exists (opt/api.py::build), and
    # SIG.warm_up takes the stream. The epoch level draws every LATER epoch's; the duplication is
    # the honest shape and the old tree has it too (:4104 and :6513 both call _resample()).
    # THE EPOCH THE RUN IS IN, WHICH IS 0 ONLY ON A FRESH RUN (2026-09-24, Q-RUN-11). This read
    # `epoch=0` unconditionally, so a child resumed at epoch E redrew EPOCH 0's stream under
    # DATA_RESAMPLE=1: driven at RUN_EPOCHS=2, a parent's epoch-1 draw hashed 65cd298845 and its
    # child, resumed at 'epoch 1', drew cfacafbe13 -- epoch 0's -- and trained its first window on
    # epoch 0's first window. data/api.py::draw_stream owns whether the epoch changes the draw, so
    # the root passes the number and never the decision, exactly as stage E's row does. (The
    # DATA_RESAMPLE=0 arm at epoch >= 1 is refused before a window trains: RUN.startup_refusals
    # refuses RUN_EPOCHS > 1 without resampling, and epoch 1 of RUN_EPOCHS=1 is a finished resume.) It is also what the declared mid-epoch
    # replay (train/api.py::new_clock) means by "replays the epoch it was interrupted in".
    sysm.stage = "stream"
    sysm.stream = data_api.draw_stream(
        data, sysm.areas, sysm.plan, epoch=0 if restored is None else int(restored.epoch),
        seed=int(run.seed))

    sysm.stage = "segment"
    # A MID-EPOCH RESUME REBUILDS THE PARENT'S SEGMENTATION FROM ITS LOG (03b S0b). The parent cut
    # this epoch at the vocabulary of its epoch start and then spliced the tail at every act; the
    # restored vocabulary can hold ids minted since, so a fresh tokenize would cut different ids and
    # the saved cursor would name different bytes. Replaying the log at its recorded views rebuilds
    # the exact stream, which is what lets the clock CONTINUE instead of replaying the epoch.
    sysm.resume_pos = None
    _slog = (saved.get("LOOP") or {}).get("seg_log") if restored is not None else None
    _spos = ((saved.get("RUN") or {}).get("clock") or {}) if restored is not None else {}
    if (_slog and int(_slog.get("epoch", -1)) == int(restored.epoch)
            and int(_spos.get("in_epoch") or 0) > 0 and _spos.get("windows_in_epoch") is not None):
        _where = (f"CKPT_RESUME={sysm.resume_src!r} continues epoch {int(restored.epoch)} "
                  f"mid-epoch (window {int(_spos['in_epoch'])} of {int(_spos['windows_in_epoch'])})")
        # A CONTEXT WIDENING ACROSS A CONTINUING RESUME IS REFUSED BY NAME (2026-09-28, register §8
        # 3.6; Q-LM-15), before the checks below: the saved cursor and the saved epoch length count
        # windows of the PARENT's width, so continuing at them in windows of this run's would train
        # from a position that names other text, over an epoch whose length the rebuilt-length check
        # would then refuse unnamed. A widening is a declared operation at an epoch boundary, where
        # the child cuts its epoch fresh at its own width.
        if sysm.ctx_widening is not None:
            _o, _n = sysm.ctx_widening
            sysm.refusals.append(
                f"{_where}, and LM_CTX_WIDEN=1 widens LM_CTX {_o} -> {_n} across it (Q-LM-15). The "
                f"saved cursor and epoch length count windows of {_o} tokens, so continuing them in "
                f"windows of {_n} would read from a position that names other text. Resume at "
                f"LM_CTX={_o} to continue this epoch exactly, or widen at an epoch boundary (the "
                f"final save of a finished run, or run.py --max-windows at the epoch's end), where "
                f"the child cuts its epoch fresh at LM_CTX={_n}.")
            _stop_if_refused(sysm)
        # BOTH CHECKS BELOW STOP HERE, BEFORE THE REPLAY AND BEFORE ANY ALLOCATION (2026-09-27,
        # Q-DATA-9): a refusal that depends on neither the model nor a restore row has no reason to
        # wait for the second stop, and the replay itself would cut the parent's log over other text.
        # (a) A HOLD-OUT ADMISSION ACROSS A CONTINUING RESUME IS REFUSED BY NAME. An admitted body
        # is a block shorter than the parent's, so this epoch's redraw is not the stream the parent
        # was reading; the digest below would refuse it too, but only this names the lever.
        _adm = list(sysm.areas.counters.get("data.holdout_admitted_names") or ())
        if _adm:
            sysm.refusals.append(
                f"{_where}, and DATA admitted a held-out block the checkpoint did not hold for "
                f"{len(_adm)} area(s) ({', '.join(_adm)}; data.holdout_admitted, Q-DATA-9). At "
                f"DATA_SYNTH_HOLDOUT=1 each of those bodies is a block shorter than the parent's, so "
                f"the stream the `stream` row redrew is not the one the parent was reading, and the "
                f"log's replay would cut the parent's segmentation over other text. Resume with "
                f"DATA_SYNTH_HOLDOUT=0 to continue this epoch exactly, or resume at an epoch "
                f"boundary (the final save of a finished run, or run.py --max-windows at the "
                f"epoch's end), where the child draws its epoch fresh and the admission holds.")
            _stop_if_refused(sysm)
        # (b) THE REDRAWN STREAM MUST BE THE PARENT'S, AND THE LOG SAYS WHICH ONE THAT WAS: the digest
        # its first event carries (_stream_digest). (c) A LOG FROM BEFORE THE DIGEST says nothing,
        # so the resume warns once and keeps the rebuilt-length check at the `epoch0` stage, and
        # this process's copy of the log records ITS stream, which is the one a later continuing
        # resume from this process must redraw.
        _events = list(_slog["events"])
        _have = _stream_digest(sysm.stream)
        _want = _events[0].get("stream") if _events else None
        if _want is None:
            sysm.warnings.append(
                f"{_where} from a segmentation log that carries no stream digest (written before "
                f"2026-09-27, Q-DATA-9), so whether the stream redrawn for it is the one the parent "
                f"was reading cannot be checked here. The rebuilt-length check still runs; a redraw "
                f"that keeps the window count trains on the saved cursor whatever it holds. This "
                f"process's log records its own stream from here on.")
            if _events:
                _events[0] = dict(_events[0], stream=_have)
        elif _want != _have:
            sysm.refusals.append(
                f"{_where}, and the stream the `stream` row redrew for it is not the one the parent "
                f"was reading: its digest is {_have} and the checkpoint's segmentation log recorded "
                f"{_want} (the bytes and the segment table, spine/compose.py::_stream_digest; "
                f"Q-DATA-9). The log's replay would cut the parent's segmentation over other text "
                f"and continue at the saved cursor as if nothing had moved. The draw is shaped by "
                f"RUN_SEED, the DATA levers and, on DATA_SOURCE=real, the corpus on disk; this run "
                f"has RUN_SEED={int(run.seed)} "
                f"DATA_SOURCE={data.source} DATA_DIR={data.dir} DATA_AREAS={data.areas} "
                f"DATA_N_PROCESSES={int(data.n_processes)} DATA_CORPUS_CAP={int(data.corpus_cap)} "
                f"DATA_HOLDOUT_FRAC={float(data.holdout_frac)} DATA_VAL_CAP={int(data.val_cap)} "
                f"DATA_SYNTH_HOLDOUT={int(bool(data.synth_holdout))} "
                f"DATA_STREAM_BYTES={int(data.stream_bytes)} DATA_SEG_MIN={int(data.seg_min)} "
                f"DATA_SEG_MAX={int(data.seg_max)} DATA_SEG_CONTIG={int(bool(data.seg_contig))} "
                f"DATA_DRAW={data.draw} DATA_REPLAY_SHARE={float(data.replay_share)} "
                f"DATA_REPLAY_NEWEST={float(data.replay_newest)} "
                f"DATA_REHEARSE_PARENT={int(bool(data.rehearse_parent))} "
                f"DATA_RESAMPLE={int(bool(data.resample))} "
                f"DATA_PHASE_SCHED={data.phase_sched!r} DATA_PHASES={int(data.phases)} "
                f"DATA_PHASE_LIVE={int(data.phase_live)}. Resume with the parent's values, or at an "
                f"epoch boundary, where the child draws its epoch fresh."
                # AT DATA_SEG_CONTIG=1 THE DIGEST REFUSES WITH EVERY LEVER UNCHANGED, and the
                # sentence has to say so or it sends the operator hunting for a lever that did not
                # move: the checkpointed cursors are the ones AFTER the parent drew this epoch
                # (draw_stream advances them for the whole epoch at the draw), so the redraw starts
                # past the parent's segments. Driven at ae70638, the tree before this ruling: that
                # resume (tests/test_continuation.py's BASE, saved at window 60) died at the
                # rebuilt-length check, 317 windows against 316, before this refusal existed.
                + (" AT DATA_SEG_CONTIG=1 THIS REFUSAL IS EXPECTED WITH EVERY LEVER UNCHANGED: the "
                   "checkpointed read cursors are the ones after the parent drew this epoch, so "
                   "the redraw starts past the parent's segments, and a continuing mid-epoch "
                   "resume cannot rebuild that stream on this tree." if bool(data.seg_contig)
                   else ""))
            _stop_if_refused(sysm)
        sysm.segmentation = _replay_segmentation(tok, sysm.vocab, sysm.stream, _slog)
        sysm.seg_log = {"epoch": int(_slog["epoch"]), "events": _events}
        sysm.resume_pos = (int(_spos["in_epoch"]), int(_spos["windows_in_epoch"]))
    else:
        # THE EPOCH'S FIRST EVENT CARRIES THE STREAM'S DIGEST (2026-09-27, Q-DATA-9), which a
        # continuing resume of this epoch compares with its redraw before it replays the log.
        sysm.seg_log = {"epoch": 0 if restored is None else int(restored.epoch),
                        "events": [_seg_event(sysm.vocab, "tokenize", stream=sysm.stream)]}
        sysm.segmentation = tok_api.tokenize(
            tok, sysm.vocab, sysm.stream.bytes, sysm.stream.labels,
            regularize=True, seed=int(run.seed))

    # -- 8. the model, the signature space, and the two populations -------------------------------
    sysm.stage = "model"
    sysm.model = lm_api.build_model(
        lm, sysm.geometry, device=sysm.process.device, seed=int(run.seed))
    if "LM" in saved:
        # THE REPORT IS BOUND AND A REFUSAL STOPS THE RUN. LM.load_state REFUSES BY RETURNING
        # LoadReport(refused=True, reason=...) rather than by raising, and until the resume-restore
        # repair (2026-09-24) this line was a bare expression statement: the refusal went on the
        # floor and the run trained the RANDOM model build_model had just made, under the parent's
        # AdamW moments, fabric, memory and domains, with nothing printed. Driven: a child at
        # TOK_MAX_BYTES=12 of a 160-window parent written at 16 passed the geometry gate (the
        # manifest carries no max_token_bytes), restored 0 of 8 LM tensors, restored OPT at
        # opt_step 160, and printed 0 refusals; its first three resumed losses were 8.14 / 8.07 /
        # 7.92 (ln 4096 = 8.32, a random model) against 7.35 / 7.40 / 7.43 on the control resume.
        # THAT DRIVING CASE IS NO LONGER A REFUSAL: max_token_bytes sizes only the composer's
        # tables, so with compose off LM.load_state restores all 8 tensors and names the move, and
        # the elif below warns (Q-CKPT-4). Every other geometry refusal takes this path.
        # The refusal is APPENDED here and RAISED at the next stop point, after
        # CAP.startup_refusals (_stop_if_refused), so the operator hears every refusal earned UP TO
        # THAT STOP in one run -- a RUN/WORLD refusal raised at the `refuse` stop pre-empts this one
        # and the CAP one, which appear on the next attempt (Q-RUN-13); RefusedRun carries the
        # partial System, and run.py prints the banner and every refusal on it and exits 2.
        # loop.run also refuses a System that carries any, for a caller that builds one by
        # another route.
        sysm.stage = "restore.lm"
        sysm.lm_load = lm_api.load_state(lm, sysm.model, sysm.geometry, saved["LM"])
        if sysm.lm_load.refused:
            sysm.refusals.append(
                f"LM.load_state refused the checkpoint {sysm.resume_src!r}: "
                f"{sysm.lm_load.reason} Continuing would train a randomly initialised language "
                f"model under the parent's optimizer state, fabric, memory and domains.")
        elif "TOK_MAX_BYTES" in sysm.lm_load.reason:
            # A MOVED TOK_MAX_BYTES WITH COMPOSE OFF IS RESTORED EXACTLY AND SAID (2026-09-24): it
            # sizes no LM tensor on that arm, so LM.load_state names it instead of refusing.
            sysm.warnings.append(f"LM.load_state: {sysm.lm_load.reason}.")

    sysm.stage = "signature"
    # ACROSS A WIDENED LINEAGE SIG KEEPS THE WIDTH ITS ENCODER WAS TRAINED AT (2026-09-28, Q-LM-15,
    # and its review): signature_width_bytes(sig_ctx, the adopted bytes/token), sig_ctx being the
    # LM_CTX the lineage's SIG was built at (the `gate` stage). SIG refuses a resume whose width
    # moved, and a routing signature is the same bytes-before-the-window question whatever the
    # window's width. On a fresh run and on every unwidened lineage sig_ctx IS LM_CTX, so this is
    # the width it always was.
    sysm.sig = sig_api.build(
        sig, width_units=_signature_width(lm, sysm.vocab, ctx=sysm.sig_ctx),
        alphabet_size=_alphabet_size(sig, lm),
        device=sysm.process.device, generator=sysm.streams["sig"])
    if "SIG" in saved:
        sysm.stage = "restore.sig"
        sig_api.load_state_dict(sig, sysm.sig, saved["SIG"],
                                sidecar=_sidecar(sysm, restored, "SIG"))
    # WHAT A DECLARED WIDENING DOES TO EVERY WINDOWS CADENCE, SAID BEFORE THE FIRST WINDOW AND NEVER
    # APPLIED (2026-09-28, register §8 3.6 and N4; Q-LM-15).
    if sysm.ctx_widening is not None:
        sysm.warnings.append(_widening_notice(sysm))

    # -- 8b. THE RETENTION PROBE'S ONE DRAW (2026-09-27, Proposal 04 SR0 and NEW-03, Q-EVAL-12) ---
    # AFTER SIG's restore row because the routing prefix is SIG's width, and before anything the
    # probe reads is trained. EVAL.pin_holdout draws each area's control and report windows ONCE, so
    # every reading of this run and of its resumes scores the same bytes. A RESUME RE-PINS AT ITS
    # PARENT'S GEOMETRY, which LOOP.eval records, so a child whose LM.ctx or SIG width differs still
    # reads the parent's windows; a pre-probe checkpoint carries none and pins at this run's.
    # AT EVAL_RETENTION_EVERY=0 THE ProbeSet IS EMPTY, NO STREAM IS MINTED AND THE BOOK STAYS EMPTY
    # -- every eval.* key ABSENT, this tree's "unreachable" -- so a run at 0 is this tree before the
    # probe, bit for bit (a default run was, until 04-6.2's flip to 1000 on 2026-09-29).
    sysm.stage = "probe"
    _ev_saved = ((saved.get("LOOP") or {}).get("eval") if restored is not None else None) or None
    _geo = (_ev_saved or {}).get("geometry")
    sysm.probe_set = eval_api.pin_holdout(
        ev, blocks=sysm.areas.holdout, seed=int(run.seed),
        window_bytes=int(_geo[0]) if _geo else int(lm.ctx) + 1,
        prefix_bytes=int(_geo[1]) if _geo else int(sysm.sig.width_units))
    # WHAT OF THE SNAPSHOT'S PROBE STATE THIS RUN CARRIES (2026-09-27, Q-EVAL-12's review). ARMED, ALL
    # OF IT: the loop continues its arrived set, its phase record, its series and its pairing from
    # it, and refreshes every part before each save. UNARMED, ONLY WHAT A RUN THAT READS NOTHING
    # CANNOT MAKE FALSE -- the pinned geometry and the book's counts -- passed on unchanged. This line
    # kept the whole record, and a probe-off run wrote it into every checkpoint as its own while it
    # described the parent's last reading: driven, a probe-off child trained 150 windows across three
    # phases, and its probe-on descendant took the grandparent's arrived set (eng, py) and phase
    # (0, 0), so its start read left out num, which the child had trained, called num unseen by its
    # parent, paired against a reading two generations old and read a phase start at its first
    # window. With the two parts alone a descendant re-pins the same windows, totals the lineage's
    # book, and takes the loop's ASSUMED path for the rest (spine/loop.py::run). The two gauges go with
    # the series and the arrived set they read.
    sysm.eval_carried = None
    if _ev_saved and sysm.probe_set.items:
        sysm.eval_carried = dict(_ev_saved)
    elif _ev_saved:
        sysm.eval_carried = {
            "geometry": _ev_saved.get("geometry"),
            "books": {k: int(v) for k, v in dict(_ev_saved.get("books") or {}).items()
                      if k not in _EVAL_BOOK_GAUGES}}
    sysm.eval_books = {}
    sysm.live_domains = 1
    if sysm.probe_set.items:
        # ARMED: every key the loop and the closures write is PRESENT-and-0 from here, so "armed and
        # not yet read" and "unreachable" print differently (G4). eval.holdout.seconds is a float,
        # wall-clock, this process's only, never checkpointed and never in the integer channel.
        for _k in _EVAL_BOOK_KEYS:
            sysm.eval_books[_k] = 0
        sysm.eval_books["eval.holdout.seconds"] = 0.0
        sysm.eval_books["eval.mem.blend_weight_sum"] = 0.0
        sysm.eval_books["eval.holdout.shortfall"] = sum(
            int(n) for h in sysm.probe_set.shortfall.values() for n in h.values())
        if bool(ev.generate):
            from spine import rng as _rng_g
            sysm.gen_rng = _rng_g.rng_for("eval.generate", int(run.seed))
            sysm.eval_books["eval.generate.samples"] = 0
            sysm.eval_books["eval.generate.tokens"] = 0
        # FAB.contribution'S PASSES ARE BOOKED BESIDE THE PROBE'S, UNDER THEIR OWN KEYS (2026-09-28,
        # register §8 3.5; Q-FAB-19), only where it is armed: FAB_CONTRIB=1 on a routed arm, whose
        # every pass the root makes over this ProbeSet's control half. eval.contrib.calls the
        # FAB.contribution calls, .empty the manage passes with no arrived control window to
        # measure on, .windows the batch rows, .cuts the material's and the prefixes'
        # TOK.tokenize calls, .forwards the closure passes (two a call: the root's baseline and
        # contribution's re-check), .decodes every head call those passes and the held-out walks
        # made, .sig_calls and .domain_spawn as the probe's, .sig_windows the rows those SIG
        # encodes took; eval.contrib.seconds a float, never checkpointed. The exact accounting of
        # Q-EVAL-12 then holds with both books' counts: tok.segment_remap moves by
        # eval.holdout.cuts + eval.contrib.cuts, lm.decode.calls by the two .decodes,
        # sig.encode_calls by the two .sig_calls and sig.encode_windows by eval.holdout.sig_calls +
        # eval.contrib.sig_windows, every closure-pass counter by the two .forwards, and -- the
        # pass's own -- fab.eval_passes by fab.contrib_passes more (one reference walk each),
        # fab.holdout_applied by the candidates and lm.loss.calls by eval.contrib.calls.
        if bool(fab.contrib) and bool(fab.on) and not bool(fab.norm_only):
            for _k in _CONTRIB_BOOK_KEYS:
                sysm.eval_books[_k] = 0
            sysm.eval_books["eval.contrib.seconds"] = 0.0
        # A CONTINUED LINEAGE'S BOOK IS ITS TOTAL, as every package's restored counters are; the
        # seconds and the generation counts are this process's and are never carried.
        for _k, _v in dict((_ev_saved or {}).get("books") or {}).items():
            if _k in sysm.eval_books and not isinstance(sysm.eval_books[_k], float):
                sysm.eval_books[_k] = int(_v)
        _probe_notices(sysm, ev)
    # FAB_CONTRIB=1 WITH NO CONTROL WINDOW ANYWHERE IS REFUSED (2026-09-28, Q-FAB-19): the probe is
    # armed (EVAL_RETENTION_EVERY > 0 was checked at the `refuse` stage) and pinned nothing, so
    # FAB.contribution has no held-out material and would run armed and inert on every pass. The
    # ProbeSet's reason says why nothing was pinned. Stops at the second stop point, with CAP's.
    if bool(fab.contrib) and int(ev.retention_every) > 0 and not sysm.probe_set.items:
        sysm.refusals.append(
            f"FAB_CONTRIB=1: FAB.contribution measures on the retention probe's pinned control "
            f"half, and nothing was pinned -- {sysm.probe_set.reason} Raise DATA_HOLDOUT_FRAC or "
            f"the stream's length (on the synthetic source DATA_SYNTH_HOLDOUT=1 is what holds a "
            f"block out), or leave FAB_CONTRIB=0.")
    # AND SO IS OPT_DAMP_SOURCE='probe' (2026-09-29, the flip's review; Q-OPT-13). The `refuse` stage
    # refuses it at EVAL_RETENTION_EVERY=0, and an armed probe that pinned nothing is the same source
    # that can never produce: the arm test fails, no reading is taken, and System.probe_reading stays
    # None, so the damping would run judging nothing on every restart. The gap is as old as the probe
    # -- the `refuse` stage tests the period alone -- and the flip moved where it is reached: until
    # 04-6.2's flip 'probe' composed only where EVAL_RETENTION_EVERY was set by hand, and since, at
    # the shipped 1000, so a stream whose halves hold no window -- or a synthetic one at
    # DATA_SYNTH_HOLDOUT=0 -- composed with OPT_DAMP_SOURCE='probe' as the only setting. Stops at the
    # second stop point, with FAB_CONTRIB's and CAP's.
    if str(opt.damp_source) == "probe" and int(ev.retention_every) > 0 and not sysm.probe_set.items:
        sysm.refusals.append(
            f"OPT_DAMP_SOURCE='probe': the damping would judge every restart on the retention "
            f"probe's control mean, and nothing was pinned -- {sysm.probe_set.reason} So no "
            f"Reading can ever arrive. Raise DATA_HOLDOUT_FRAC or the stream's length (on the "
            f"synthetic source DATA_SYNTH_HOLDOUT=1 is what holds a block out), or leave "
            f"OPT_DAMP_SOURCE at 'off'.")

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
        rng=sysm.streams["domains"],
        # THE STREAM POSITION CROSSES ONLY ON A CONTINUING MID-EPOCH RESUME (03b S0b): any other
        # resume starts a new stream, and DOM's restore then re-arms rather than continues.
        restored=(saved.get("DOM") if saved.get("DOM") is None or sysm.resume_pos is not None
                  else {k: v for k, v in saved["DOM"].items() if k != "position"}))
    # A TRAINED PARTITION RESTORED INTO A RUN THAT TURNED DOMAINS OFF IS SAID, NOT REFUSED (Q-DOM-1,
    # 2026-09-24). DOM_ENABLED=0 builds the same Partition the on-arm does, so the restore is sound
    # and the ablation the operator asked for is kept -- unlike WORLD_ENABLED=0, which builds a
    # NULL world with nowhere to load into and is refused. But the resume was SILENT: driven, a
    # DOM_ENABLED=0 child of a 160-window parent restored 8 domains, printed 0 refusals and 0
    # warnings, and then sent did=0 for every window -- and 0 is a REAL id: when the parent's
    # domain 0 survived, every window of the child is attributed to it (MEM's source, DOM.prior's
    # histogram), which is neither the parent's partition nor an ablation of it. DOM.census already
    # prints partition_off for this configuration ("A run with DOM_ENABLED=0 that restored domains
    # from a checkpoint still has a live-looking partition and is still off"), which is why this is
    # a sentence and not a refusal; that line is printed at the END of a run, and this one is
    # printed before the first window.
    if (not bool(dom.enabled)
            and int(sysm.partition.counters.get("part.n_restored_domains", 0)) > 0):
        _zero = 0 in sysm.partition.cent
        sysm.warnings.append(
            f"DOM_ENABLED=0 on a resume whose checkpoint carries "
            f"{int(sysm.partition.counters['part.n_restored_domains'])} trained domain(s): they "
            f"are restored, and every window of this run is did=0, so "
            + ("the parent's domain 0 -- which survived -- receives EVERY window's attribution "
               "(its memory source and its token prior), a state neither the parent's partition "
               "nor an ablation of it"
               if _zero else
               "no restored domain is ever assigned a window again and new memory is filed under "
               "source 0, an id the parent's partition no longer holds")
            + ". This continues a different optimisation from the checkpoint's under its name; to "
            "ablate domains cleanly, start a fresh run at DOM_ENABLED=0.")
    # A COMPETENCE BOOK FOLDED IN THE OTHER UNIT IS SAID, NOT REFUSED (Q-DOM-5, 2026-09-26), on the
    # Q-DOM-1 precedent above. DOM_LEVELS changes the unit the root hands DOM.note_competence, and a
    # checkpoint written before the lever existed, or at its other value, restores EMAs in the unit it
    # was folded in: open_partition keeps them (there is no per-domain bytes history to convert with,
    # and dropping them would disarm the spare) and counts part.n_comp_unit_changed. The C12 case is
    # a "pre-Levels" fleet checkpoint continued at the default.
    # AND THE SHARE AN EARLIER RESUME LEFT IS SAID TOO (2026-09-27, the build 1.2 review). The blob's
    # stamp is the unit the saving run folded in, so a child that changed unit and saved before its
    # parent's EMAs were refolded passed them on under its own stamp: its grandchild at the same value
    # was told nothing, and one at the other value was told the wrong unit. The blob now carries each
    # EMA's share of the other unit (DOM.state_dict's `comp_carry`), and part.n_comp_carried counts
    # the EMAs holding one. The unit named is the one this run does not hand DOM: with two units, it
    # is what every carried reading is in.
    if int(sysm.partition.counters.get("part.n_comp_unit_changed", 0)) > 0:
        _now_unit = ("bits per build-time token" if bool(dom.levels) else "bits per token")
        _was_unit = ("bits per token" if bool(dom.levels) else "bits per build-time token")
        _k = int(sysm.partition.counters.get("part.n_comp_carried", 0))
        _n = int(sysm.partition.counters.get("part.n_restored_domains", 0)) + 1
        sysm.warnings.append(
            f"DOM_LEVELS={int(bool(dom.levels))} on a resume whose competence book holds readings "
            f"folded in {_was_unit}: {_k} of its {_n} EMAs (one per restored domain, and the "
            f"population baseline) carry them (part.n_comp_carried) -- every one when the parent "
            f"folded in that unit, the share an earlier resume left when it did not. This run hands "
            f"DOM {_now_unit} (Q-DOM-5). The book is kept: a carried EMA's share of the other unit "
            f"is multiplied by (1 - d_comp_ema) at each reading it folds and a domain that receives "
            f"none keeps it, so until then the cull's competence spare compares readings in two units; "
            f"the checkpoint carries the shares, so a resume from it is told again. For a clean arm, "
            f"resume where part.n_comp_carried reads 0: at DOM_LEVELS={int(not bool(dom.levels))} "
            f"when the parent's book is wholly in {_was_unit}; a book an earlier resume mixed is "
            f"whole in neither unit.")

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
    # THE SECOND STOP, AND IT CANNOT BE THE FIRST: CAP's refusal compares the valve against the
    # BUILT population's n_live, so it necessarily follows the model, signature and fabric
    # allocations above. It precedes the optimizer and the SIG warm-up, which are what a refused
    # run used to spend before run.py read the list. A refused LM restore appended above stops
    # here too.
    _stop_if_refused(sysm)

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
        # AND THE REPORT IS BOUND, for the reason the LM restore's is. OPT.load_state refuses by
        # RETURNING LoadReport(refused=True), and this line discarded it: every resume that widened
        # FAB_SLOTS or LM_VOCAB_SLOTS -- the add-an-area resume the MAY_WIDEN rules exist for --
        # came back with EMPTY AdamW moments, opt_step 0 and a re-run LR warmup while the clock
        # resumed at the parent's step, and printed nothing (driven: a FAB_SLOTS=640 child of a
        # 512-slot, 160-window parent -- opt.ckpt.refused 1, 38 saved moment entries and 0 live,
        # and after 3 windows opt_step 3 at LR 7.6e-5 against 1.94e-3 once restored).
        # OPT.load_state now restores a dim-0 widening by padding the moments
        # (opt.ckpt.moments_widened), so what still refuses is a group structure the L50 guard
        # exists to stop, and that stops the run by name here.
        sysm.stage = "restore.opt"
        # AND WHETHER THIS IS THE SAME RUN (2026-09-27, the build 1.4 review; Q-OPT-12). A
        # continuing mid-epoch resume -- the one DOM's stream position crosses on, above -- is the
        # run its checkpoint was part of, and OPT cannot tell that from its own horizons: the
        # resumed build's is this epoch's length x RUN_EPOCHS, which acts and DATA_RESAMPLE move
        # under a run that changed nothing, and a session in progress was re-anchored on it.
        sysm.opt_load = opt_api.load_state(opt, sysm.optimizer, saved["OPT"],
                                           continuing=sysm.resume_pos is not None)
        if sysm.opt_load.refused:
            sysm.refusals.append(
                f"OPT.load_state refused the checkpoint {sysm.resume_src!r}: "
                f"{sysm.opt_load.reason} Continuing would train the restored weights from EMPTY "
                f"AdamW moments with the LR warmup re-run from step 0 while the clock resumes at "
                f"the parent's step. Resume at the parent's geometry, or start a new run.")

    # THE ROOT'S OWN RESUME: the appearance counter spine/loop.py::_payload writes under "LOOP".
    # No package owns System.token_seen, so no package restore row can put it back; before
    # 2026-09-24 nothing saved it and every resumed process started it at None (LM.anchor_term then
    # re-held every minted row at full weight, and TOK.judge_probation counted only post-resume
    # appearances). LM_VOCAB_SLOTS may widen across a resume, so the saved counter is a PREFIX of
    # the live one; a narrowing is refused by the geometry gate before this line.
    _loop = saved.get("LOOP") or {}
    if _loop.get("token_seen") is not None:
        sysm.stage = "restore.loop"
        # TENSOR METHODS ON THE SAVED COUNTER, NOT A torch IMPORT: this file imports no torch, and
        # the buffer takes the saved counter's dtype and is moved to the run's device.
        _seen = _loop["token_seen"]
        _live = _seen.new_zeros(int(lm.vocab_slots))
        _n = min(int(_seen.shape[0]), int(_live.shape[0]))
        _live[:_n] = _seen[:_n]
        sysm.token_seen = _live.to(sysm.process.device)
    # WERE DOM's RESTORED HISTOGRAMS COUNTED UNDER THE TABLE THIS STREAM IS CUT AT? (2026-09-24) The
    # parent's loop records whether the match table moved since its last segmentation; this
    # process re-segments at the saved vocabulary, so a moved table means they were not. Driven: a
    # 150-window parent with 2 mints since its segmentation resumed with 0 counts for the minted
    # ids in its restored histograms, 168 occurrences of them in its first 150 windows, and a roll
    # warning that called the histograms valid. -1 makes the loop's first roll tell DOM.
    if restored is not None:
        _moved = _loop.get("seg_table_moved")
        sysm.rev_at_last_seg = -1 if _moved else (-2 if _moved is None else None)

    # -- 11. the clocks, epoch 0's length, and the encoder warm-up --------------------------------
    # resume_backwards / resume_opt_steps ARE OPT'S RESTORED COUNTS, read off the two declared
    # OptState fields after the restore row above (0 and 0 on a fresh run or a refused restore).
    # Without them the clock restarted at backwards=0 while OPT resumed at n_backward, and a parent
    # saved partway through an accumulation left the two gates out of phase for the whole child:
    # zero optimizer steps, then a raise at R before the final save (Q-RUN-9).
    sysm.stage = "clock"
    _rp = sysm.resume_pos
    sysm.clock = run_api.new_clock(
        run, batch_windows=int(opt.batch_windows), accum=int(opt.accum),
        resume_step=0 if restored is None else restored.step,
        resume_epoch=0 if restored is None else restored.epoch,
        resume_backwards=int(sysm.optimizer.n_backward),
        resume_opt_steps=int(sysm.optimizer.opt_step),
        resume_in_epoch=0 if _rp is None else _rp[0],
        resume_windows_in_epoch=None if _rp is None else _rp[1])

    # Epoch 0 is never rolled into, so its length is declared here rather than at stage E. It is a
    # COUNT OF WINDOWS measured on the segmentation that exists, never stream_bytes // ctx. ON A
    # RESUME it is the RESUMED epoch's length, measured on the stream the `stream` row drew for it.
    sysm.loop_carried = None
    if _rp is not None:
        _car = (saved.get("LOOP") or {}).get("carried")
        if _car:
            from spine import units as _Uc
            sysm.loop_carried = dict(_car)
            sysm.novelty = _car.get("novelty")
            sysm.due = _car.get("due")
            sysm.retok_pending = int(_car.get("retok_pending") or 0)
            sysm.mem_remap = _car.get("mem_remap")
            if _car.get("shift_at_windows") is not None:
                sysm.shift_at_windows = _Uc.Windows(int(_car["shift_at_windows"]))
            if _car.get("shift_at_steps") is not None:
                sysm.shift_at_steps = _Uc.Steps(int(_car["shift_at_steps"]))

    sysm.stage = "epoch0"
    # ON A CONTINUING MID-EPOCH RESUME THE CLOCK IS ALREADY OPEN AT THE SAVED POSITION (new_clock),
    # and begin_epoch would zero the cursor, so it is not called; the rebuilt segmentation's length
    # must equal the saved epoch length, or the log did not rebuild what the parent held.
    if _rp is None:
        sysm.clock.begin_epoch(_windows_in_epoch(sysm))
    elif _windows_in_epoch(sysm) != _rp[1]:
        raise RuntimeError(
            f"compose: the segmentation rebuilt from the checkpoint's log holds "
            f"{_windows_in_epoch(sysm)} windows, and the parent's epoch held {_rp[1]}. The log did "
            f"not rebuild the stream the parent was reading, so continuing at window {_rp[0]} would "
            f"read different bytes; refusing rather than training on them.")

    # A RESUME OF A FINISHED RUN IS REFUSED, THE WAY RUN_EPOCHS=0 IS (2026-09-24, Q-RUN-10). The
    # loop's first act is clock.advance(), so a clock already at epoch >= RUN_EPOCHS trained one
    # window nobody asked for -- a full flush, an optimizer step, a MEM write -- and overwrote the
    # final checkpoint at step+1: driven, a 157-window finished parent resumed as '158 windows, 1
    # flushes, 1 optimizer steps' and 'CKPT.save: 1 checkpoint(s) written'. RunClock.counters
    # publishes epochs_target for exactly this question and nothing asked it. A REFUSAL rather than
    # a zero-window report, because the add-an-area continuation that forgot to raise RUN_EPOCHS
    # is the goal-B case where a silently empty child is most damaging.
    _c0 = sysm.clock.counters()
    if restored is not None and int(_c0["epoch"]) >= int(_c0["epochs_target"]):
        sysm.refusals.append(
            f"CKPT_RESUME={sysm.resume_src!r} has already completed epoch {int(_c0['epoch'])} of "
            f"RUN_EPOCHS={int(_c0['epochs_target'])} (step {int(_c0['step'])}), so the loop would "
            f"make no passes -- and before this refusal it trained one unrequested window and "
            f"overwrote the final checkpoint. Raise RUN_EPOCHS above {int(_c0['epoch'])} to "
            f"continue training from it"
            # ON THE SHIPPED DATA_RESAMPLE=0 ARM THAT ADVICE ALONE LED INTO RUN.startup_refusals'
            # resampling refusal, whose "or run one epoch" led back here (driven 2026-09-24: only
            # RUN_EPOCHS=2 DATA_RESAMPLE=1 ran). Both levers are named when resampling is off.
            + ("." if bool(data.resample) else
               f", with DATA_RESAMPLE=1 -- RUN_EPOCHS above 1 without resampling is refused "
               f"(RUN.startup_refusals), and resampling is off on this run."))
    # THE THIRD STOP: a refused OPT restore (the `restore.opt` row) and a finished resume (just
    # above) stop here, before the SIG warm-up and before the mid-epoch accounting below reads a
    # clock that will never run.
    _stop_if_refused(sysm)

    # A MID-EPOCH RESUME REPLAYS ITS EPOCH, AND THE RUN NOW SAYS SO (2026-09-24, Q-RUN-10). The
    # replay is DECLARED (train/api.py::new_clock, "A MID-EPOCH RESUME REPLAYS THE EPOCH IT WAS
    # INTERRUPTED IN") and is kept; what was missing is the operator hearing about it. Driven: a
    # 120-window parent of a 211-window epoch resumed to 331 windows, trained windows 0..119 a
    # second time and ran 120 optimizer steps past a 211-step horizon, and printed nothing. The
    # position comes from payload['RUN'] (RunClock.counters' in_epoch, written by
    # spine/loop.py::_payload); a checkpoint written before 2026-09-24 has none, and then epoch 0's
    # position is still exact (it began at step 0) while a later epoch's is unknown and said so.
    if restored is not None:
        _run_saved = saved.get("RUN") or {}
        _pos = _run_saved.get("clock") or {}
        if "in_epoch" in _pos:
            _in = int(_pos["in_epoch"])
        elif int(restored.epoch) == 0:
            _in = int(restored.step)
        else:
            _in = None
        _wie = int(_c0["windows_in_epoch"])
        if _in is None:
            sysm.warnings.append(
                f"RESUME POSITION UNKNOWN: the checkpoint predates payload['RUN'], so whether step "
                f"{int(restored.step)} of epoch {int(restored.epoch)} was an epoch boundary cannot "
                f"be told. If it was not, the {_wie}-window epoch restarts at window 0 and the "
                f"windows already trained in it are trained again (train/api.py::new_clock).")
        elif _in > 0 and _rp is not None:
            sysm.warnings.append(
                f"MID-EPOCH RESUME CONTINUES: the checkpoint was saved {_in} window(s) into epoch "
                f"{int(restored.epoch)}; the parent's segmentation was rebuilt from its log "
                f"({len(sysm.seg_log['events'])} event(s)) and the clock continues at window {_in} "
                f"of {_rp[1]} (03b S0b).")
        elif _in > 0:
            from spine import derive as _derive, units as _U
            # THE WINDOWS LEFT, THROUGH THE NAMED CONVERSIONS: this epoch replayed whole plus every
            # later one at this epoch's length (later epochs shrink as mints land, so this is an
            # upper estimate), then windows to optimizer steps at the effective batch.
            _left = _derive.run_windows_from_epochs(
                _U.Epochs(int(_c0["epochs_target"]) - int(restored.epoch)), _wie)
            _steps_end = int(sysm.optimizer.opt_step) + int(_derive.opt_steps_from_windows(
                _left, int(opt.d_effective_batch_windows)))
            _run_steps = int(sysm.optimizer.horizon.run_steps)
            sysm.warnings.append(
                f"MID-EPOCH RESUME REPLAYS ITS EPOCH: the checkpoint was saved {_in} window(s) into "
                f"epoch {int(restored.epoch)}, and a resume restarts that epoch at window 0 (the "
                f"declared semantics, train/api.py::new_clock), so those {_in} window(s) are "
                f"trained again and this {_wie}-window epoch rolls {_wie} windows from now rather "
                f"than {max(0, _wie - _in)}. The optimizer resumes at step "
                f"{int(sysm.optimizer.opt_step)} and would end near step {_steps_end} against an OPT "
                f"horizon of {_run_steps}"
                + (f" -- {_steps_end - _run_steps} step(s) past it, at the LR floor."
                   if _steps_end > _run_steps else ", inside it.")
                + " Resume from an epoch-boundary checkpoint to avoid both (Q-RUN-10).")

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
    # ON A RESUME THIS CALL TRAINS NOTHING (Q-SIG-2, 2026-09-24). It ran SIG_WARMUP more steps on
    # the restored encoder at every resume -- moving the signature space away from the DOM and FAB
    # centroids restored beside it (101 of 160 windows changed nearest domain centroid on a
    # 160-window parent) -- and replaced the checkpointed verdict with a pass the parent never
    # made. warm_up now returns the parent's report when SIG.load_state_dict restored the encoder,
    # so the collapsing check below reads the verdict the encoder actually has.
    sysm.stage = "warmup"
    sysm.warmup = sig_api.warm_up(sig, sysm.sig, stream=_signature_stream(sysm, sig),
                                  seen_units=_signature_units(sysm, sig),
                                  opt=sysm.optimizer.encoder)
    # AN OPERATOR WHO SETS SIG_WARMUP ON A RESUME IS TOLD IT IS INERT (2026-09-24). The restored
    # encoder is not re-warmed at any budget (Q-SIG-2), so a resume launched to warm longer -- off a
    # SIG_WARMUP=0 parent, say -- got nothing and heard nothing: driven, CKPT_RESUME=<160-window
    # parent> SIG_WARMUP=1500 skipped the warm-up with no warning naming the lever.
    # SIG decides whether the lever was set (sig.warmup_budget_ignored, the budget asked for); the
    # root only says it, because the root does not read a package's Config.given().
    _ignored = int(getattr(sysm.sig, "counters", {}).get("sig.warmup_budget_ignored", 0) or 0)
    if _ignored:
        sysm.warnings.append(
            f"SIG_WARMUP={_ignored} is INERT on this resume: the checkpoint restored a trained "
            f"encoder, and SIG.warm_up does not re-warm a restored encoder at any budget (Q-SIG-2) "
            f"-- the warm-up report is the parent's. Start a new run to warm with a different "
            f"budget.")
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
    # periods) is keyword-only with no default (train/api.py::new_cadences), so this line was a TypeError on
    # every compose() -- unreachable behind THREE stubs and not one. This is row 37 of
    # ASSEMBLY_ORDER's 42 (36 of 41 until the 'focus' row landed, 2026-09-28, and 35 of 40 until
    # the 'probe' row, 2026-09-27), and rows 31, 34 and 35 each raised NotImplementedError before it:
    # capacity/api.py::startup_refusals, train/api.py::new_clock and
    # train/api.py::RunClock.begin_epoch. Row 31 is the FIRST of the three and was not the reason, so
    # repairing CAP alone did not bring this line into reach -- the run then stopped earlier, at
    # this file's `clock` stage. Measured one stub at a time by re-running
    # compose.compose(environ={}) in a fresh process and reading where the traceback ended:
    # unpatched -> `refuse`, row 31; startup_refusals returning [] -> `clock`, row 34; new_clock
    # also handing back a bare RunClock -> `epoch0`, row 35; the clock stubbed whole -> here.
    # Rows 32, 33 and 36 (OPT.build, OPT.load_state, SIG.warm_up) had bodies and passed through.
    # (The row numbers are the 42-row order's -- the 41-row order's until the 'focus' row,
    # 2026-09-28; this said "Row 29" beside "rows 30, 33 and 34" until
    # Q-EVAL-12's review. THAT STACK IS GONE: all three have bodies, and compose(environ={}) returns
    # a System at stage 'assembled' with no refusal -- measured 2026-09-27 -- so this line runs on
    # every compose().)
    # THIS BLOCKER HAS NOW BEEN NAMED WRONG TWICE, THE SAME WAY BOTH TIMES: one mechanism, stated
    # as the reason, that had stopped being sufficient. Until 2026-09-04 the comment read
    # RUN.process_setup, which is row 1 and HAS A BODY (train/api.py::process_setup returns a
    # Process and stops nothing); the repair then wrote CAP.startup_refusals ALONE, which raises
    # but is not exclusive. An unreachable arm has to name every blocker, because naming one is a
    # claim the next reader disproves by repairing it.
    # The signature was fixed on 2026-08-30 and the call site was not, which is the same shape
    # capacity/api.py::<module> records for derive.pin_tick: a file asserting a repair as done with the
    # call the repair requires never written. Each period comes from the package that DECLARES its
    # kind, as units.Windows; K9 refuses a bare lever read here.
    # AND IT WAS A SECOND CONSTRUCTION WITH FIVE KEYS, WHICH IS THE DEFECT BOTH ROWS ABOVE FORBID
    # IN AS MANY WORDS. This line built its own mapping from the five typed accessors and dropped
    # 'progress' -- so RUN.PROGRESS_WINDOWS had no Cadences.ledger row and no cadence_audit
    # coverage, which is exactly the "0 fires nobody can read" state new_cadences' docstring
    # describes, and K9 could not see it because K9 reads _periods rather than this call. The
    # ROW says "periods is _periods(sysm) -- the EIGHT gates' thresholds" and the audit's row says
    # "the SAME _periods(sysm) mapping new_cadences receives -- the same object, not a second
    # construction, or the audit would describe gates other than the ones evaluated". Both are
    # true of the call now. Found 2026-09-15, writing the three RUN bodies these two rows call.
    sysm.stage = "cadence"
    periods = _periods(sysm)
    sysm.cadences = run_api.new_cadences(run, periods=periods)
    # THE GATES' SCHEDULE CROSSES THE BOUNDARY (2026-09-24, Q-RUN-9). spine/loop.py::_payload
    # writes Cadences.state() under payload['RUN']; without this row every gate re-seeded at the
    # resumed step and first fired a whole period late -- dom.manage at 261 instead of 201 on a
    # 160-window parent, dom.rekey at 361 instead of 201 -- and the ledger restarted at 0 fires. A
    # checkpoint written before then has no 'RUN' key and restores nothing, which is the old
    # behaviour and not a refusal.
    if restored is not None:
        sysm.stage = "restore.run"
        sysm.cadences.restore((saved.get("RUN") or {}).get("cadences"))

    # AND THE AUDIT WAS A ROW NOBODY CALLED. `grep cadence_audit` found it only inside its own row
    # prose: the one statement that makes ISSUES P1-C11 visible -- ten cadence defaults longer than a
    # 937-window run -- was never executed, while K6 credited the row and passed. It STATES, it does
    # not raise, so its lines join the warnings the report must print; an EMPTY list is a real
    # result and must be printed as one.
    # THE BOOK'S LINE IS THE ROOT'S (2026-09-28, Q-DATA-11's review). RUN's sentence for a gate it
    # flags is written for a gate that is its cadence and nothing more, and 'data.trust' is armed by
    # DATA_TRUST and passes beside its cadence at each epoch's end and a stop's tail -- both this
    # file's loop's -- so _trust_audit words that one line and returns the rest as RUN wrote them.
    # AND SO IS THE PROBE'S (2026-09-29, the flip's review; Q-EVAL-12): its arm test is this file's
    # pinned ProbeSet, and an armed probe reads at every phase start, at a resume's start and at R
    # beside its cadence, so RUN's starved sentence was false on every shipped-default run of 506-937
    # windows and its advice named 04-6.2's 1000 as the fault. _retention_audit words that key's line
    # after _trust_audit, and RUN's own DISARMED line stands at EVAL_RETENTION_EVERY=0, where it is
    # true.
    sysm.stage = "audit"
    _rw = _run_windows(sysm)
    sysm.warnings.extend(_retention_audit(
        sysm, _trust_audit(sysm, run_api.cadence_audit(run, run_windows=_rw, periods=periods),
                           run_windows=_rw, periods=periods),
        run_windows=_rw, periods=periods))

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

def _signature_width(lm, vocab, ctx=None):
    """THE ONE SIGNATURE WIDTH, resolved once, here, and never recomputed as the vocabulary grows.

    spine.assemble lists this under "considered and rejected": it cannot be a Coupling because
    bytes_per_token is MEASURED on a corpus the tokenizer has not seen when build() freezes, and a
    Config that can still be written after startup is a Config the report cannot claim the run
    used. So it is derive-and-keep: SIG records the answer on SigState and every later call in that
    package reads it from there. The cost of the alternative is measured -- the old tree resolved
    the same knob in two places, `max(WIN, int(WIN*bpt))` = 614 bytes in training at :5675 and
    `max(1, SIG_WIN)` = ONE BYTE in eval at :3919, so every eval-path routing decision in every
    report was made on a one-byte signature and nothing failed.

    `ctx` IS THE LM_CTX THE LINEAGE'S SIG WAS BUILT AT, System.sig_ctx, AND None MEANS LM.ctx
    (2026-09-28, Q-LM-15, and its review). A widened lineage keeps the width its encoder was trained
    at: that LM_CTX, with the bytes/token build_vocabulary adopted from the parent's file, gives the
    parent's number exactly, and SIG's own restore refuses any other. Until the review the root
    passed the parent's LM_CTX only at the resume that widened, and None at every later one, so a
    widened child's own checkpoint resolved at the child's LM_CTX and was refused.
    """
    from spine import derive
    return derive.signature_width_bytes(int(lm.ctx) if ctx is None else int(ctx),
                                        float(vocab.bytes_per_token))


def _alphabet_size(sig, lm):
    """The encoder embedding's row count: 256 under space="bytes", LM.vocab_slots under "tokens".

    Sized at the SLOT CEILING and not at the live vocab_size, because widening an embedding mid-run
    changes the encoder optimizer's moment shapes -- ISSUES P3-H24 from the other side. SIG records it
    in its checkpoint sidecar and refuses a resume that disagrees.
    """
    return int(lm.vocab_slots) if sig.space == "tokens" else 256


def _widening_notice(sysm):
    """The one sentence a declared context widening owes the operator, before the first window: what
    moved, what did not, and every Windows-unit lever beside the value that would keep the parent's
    spacing in TEXT -- PRINTED, NEVER APPLIED (2026-09-28, register §8 3.6, NEW-13 and N4;
    docs/04_CONTRACT.md Q-LM-15).

    A window is LM_CTX tokens, so after a widening every lever declared in units.Windows -- every
    cadence, horizon and cooldown the tree counts in windows, 27 of them on 2026-09-28 -- spans more
    text than it did under the parent. NEW-13's critic makes that the reason `lm.ctx` stayed EXACT
    until a cadence-rescaling known answer existed; spine/derive.py::windows_at_ctx is that answer,
    and this is where a run reaches it. N4 forbids the other half -- rescaling them at run time is a
    lever reading another lever -- so each is printed with its rescaled value and left as the
    operator set it.

    THE LIST IS READ OFF THE DECLARATIONS, NOT TYPED HERE: every Config's levers whose declared unit
    is units.Windows (Config.lever's read-only view), in env-name order, so a Windows lever added
    later is listed without an edit. A negative value is printed as it stands (DISARMED to RUN's
    Cadences, and windows_at_ctx refuses to rescale one)."""
    from spine import derive, units
    old, new = sysm.ctx_widening
    rows = []
    for pfx in sorted(sysm.configs):
        cfg = sysm.configs[pfx]
        wired = set(cfg.wired())
        for field in cfg.keys():
            if field in wired:
                continue
            view = cfg.lever(field)
            if view.unit is not units.Windows:
                continue
            value = int(getattr(cfg, field))
            rows.append((view.env_name, value,
                         None if value < 0 else
                         int(derive.windows_at_ctx(units.Windows(value), old, new))))
    rows.sort()
    listed = ", ".join(f"{env} {v} -> {r}" if r is not None else f"{env} {v} (negative, DISARMED)"
                       for env, v, r in rows)
    scheme = str(sysm.geometry.pos)
    return (f"LM_CTX_WIDEN=1 WIDENED LM_CTX {old} -> {new} AT THIS RESUME (docs/04_CONTRACT.md "
            f"Q-LM-15; register NEW-13, O17). "
            + (f"The learned position table keeps the parent's {old} rows and appends {new - old} "
               f"at this build's initialisation (lm.ckpt.ctx_widened), so on a window of {old} "
               f"tokens or fewer the model computes what the parent computed. "
               if scheme == "learned" else
               f"LM_POS={scheme!r} builds no position table, so nothing is appended. ")
            + f"SIG keeps the width its encoder was trained at ({int(sysm.sig.width_units)} units, "
              f"from LM_CTX={int(sysm.sig_ctx)}, which this run's checkpoints carry on as "
              f"LOOP.sig_ctx), and a retention probe the parent pinned keeps its windows. EVERY "
              f"WINDOWS-UNIT LEVER NOW COUNTS WINDOWS OF {new} TOKENS WHERE THE PARENT'S COUNTED "
              f"{old}, so each spans more text than it did. The value that keeps the parent's "
              f"spacing in text (spine/derive.py::windows_at_ctx), PRINTED AND NEVER APPLIED (N4) "
              f"-- set the ones you want held: {listed}. The widening is register §8 5.8's route "
              f"(B) on CPU, operation only; it is not a route that has passed (O17).")


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
    resolved ONCE at OPT.build (opt/api.py::Horizon) from epoch 0's length; RunClock.begin_epoch
    re-measures every epoch, and minting shortens every later one. Both are Windows so nothing
    raises. See Q-OPT-5.

    IT RETURNS units.Windows AND USED TO RETURN A BARE INT, which both of its consumers refuse.
    derive.cadences_that_cannot_fire raises UnitError on a non-Windows at both ends (derive.py::cadences_that_cannot_fire)
    and derive.opt_steps_from_windows does the same (derive.py::opt_steps_from_windows), so RUN.cadence_audit would
    have raised on its first call and OPT.build on its first horizon. BOTH ARE REACHED ON EVERY
    compose() TODAY: compose.compose(environ={}) returns a System at stage 'assembled' with no
    refusal (measured 2026-09-27, Q-EVAL-12's review), past OPT.build at row 32 of ASSEMBLY_ORDER's
    42 -- this function is CALLED there, at the `optimizer` stage -- and past RUN.cadence_audit at
    row 39. THE TWO WERE UNREACHABLE FOR DIFFERENT REASONS, AND SAYING SO WAS THE WHOLE VALUE OF THIS
    PARAGRAPH WHILE THEY WERE. capacity/api.py::startup_refusals at row 31 was OPT.build's ONLY
    blocker: with startup_refusals returning an empty list compose() ran straight through OPT.build
    and OPT.load_state and stopped at row 34. RUN.cadence_audit had FOUR blockers above it, not one:
    row 31, then train/api.py::new_clock at row 34, train/api.py::RunClock.begin_epoch at row 35 and
    train/api.py::new_cadences at row 37, each raising NotImplementedError in its turn (one row
    lower each until the 'focus' row landed, 2026-09-28, and two lower until the 'probe' row,
    2026-09-27). So
    "unreachable today only because CAP.startup_refusals", which stood in this paragraph until
    2026-09-04, was true of one consumer and false of the other, and a reader who repaired CAP
    expecting the audit's UnitError to surface would not have seen it. MEASURED ONE STUB AT A TIME,
    by re-running compose.compose(environ={}) in a fresh process and reading where the traceback
    ended: unpatched it stopped at the `refuse` stage, row 31; with startup_refusals returning [] at
    `clock`, row 34; with new_clock also handing back a bare RunClock at `epoch0`, row 35; with the
    clock stubbed whole at `cadence`, row 37; and with new_cadences returning a mapping at `audit`,
    row 39, which is this function's second call site and the audit's first. Rows 33 and 36
    (OPT.load_state, SIG.warm_up) had bodies and passed through. A stack of stubs is this file's
    oldest shape and the reason K7 exists; what it costs is that "unreachable" needs the whole list
    to stay true, and one name is the answer a repair disproves. THE BLOCKER NAMED HERE UNTIL
    2026-09-04 WAS RUN.process_setup, AND THAT WAS FALSE: process_setup is row 1 and it HAS A BODY
    -- train/api.py::process_setup returns a Process -- so it stops nothing. It was the true blocker when the sentence was first written
    and stopped being one when P4 wrote the body; an unreachable arm whose stated reason names a
    mechanism that no longer holds is a false equation, which this file rates worse than printing
    nothing. AND THIS PARAGRAPH MADE THAT FALSE EQUATION AGAIN UNTIL Q-EVAL-12's REVIEW: "measured,
    not inferred", it said compose.compose(environ={}) raised NotImplementedError from the `refuse`
    stage into capacity/api.py::startup_refusals, quoting docs/04_CONTRACT.md's "halts on the 29th
    of the 41 rows" -- of a function that had a body, at a row that was the 30th (the 31st since
    the 'focus' row, 2026-09-28). ISSUES P1-H51 is
    the general case: all 38 Clock-unit levers resolve to bare ints and the typing is real only
    where derive or assemble puts it back, which for this quantity is here, at the one place it is
    computed.

    THE MULTIPLICATION IS EPOCHS -> WINDOWS AND IT WAS WRITTEN INLINE UNTIL 2026-09-04. The body
    read `units.Windows(_windows_in_epoch(sysm) * int(sysm.configs["RUN"].epochs))` -- a
    windows-per-epoch rate times a count of EPOCHS, on bare ints, with the answer's kind put on at
    the end. That is a cross-kind conversion written at its call site, which units.py::Clock.convert
    refuses in as many words and which check_o11_no_unnamed_clock_arithmetic exists to forbid; the
    number was right at every configuration, which is the point of the rule and not an argument
    against it. It is now spine/derive.py::run_windows_from_epochs, which refuses anything but an
    Epochs at the count end and any Clock at the rate end, and the kind is put on HERE -- at the
    call, where P1-H51 says it has to be, because RUN.epochs resolves to a bare int like all 38
    Clock-unit levers.

    WHY O11 DID NOT SEE IT, WHICH MATTERS MORE THAN THE LINE DID. Three independent reasons, each
    sufficient on its own: the check drops `src/spine/` twice over (its `_PKG_DIRS` subtracts
    "spine", and its module loop skips any file under `src/spine/` on the stated ground that derive
    IS the named conversion and must do the arithmetic); its AST half only flags an operand that is
    an ATTRIBUTE named after one of the OWNING package's clock levers, and both operands here are
    Calls; and `epochs` is RUN's lever while this file belongs to a package that has no levers.py
    at all, so the per-package clock set for "spine" is empty. The exemption is deliberate and
    correct for derive.py. What it also exempts is the COMPOSITION ROOT -- the one other place in
    the tree that legitimately holds two packages' clocks at once, and therefore the one other
    place this defect can live.

    NARROWING THE SKIP DOES NOT CLOSE IT, AND THIS PARAGRAPH SAID IT WOULD UNTIL 2026-09-04. The
    sentence here was "Narrowing the skip from `src/spine/` to `src/spine/derive.py` is the
    ownership pass's call", which records a remedy that has since been MEASURED NOT TO WORK. On a
    scratch copy of the tree with the skip narrowed to derive.py alone and the inline multiply put
    back into this function, tests/test_ownership.py reports "PASS O11". Each of the three reasons
    above has to be answered separately, and narrowing answers only the first: four lines below the
    skip the loop reads `mine = clocks.get(pkg, set())` and then `if not mine: continue`, and for
    pkg "spine" that set is empty because no src/spine/levers.py exists (thirteen packages declare
    one; this is not among them), so the file is dropped a second time. Give "spine" the UNION of
    every package's clock levers and the file is finally examined -- and O11 still does not report
    this line, because its AST half tests each operand for being an Attribute and both of these are
    Calls, while its textual half matches `name //`, `name %` or `name *` where the name is a bare
    identifier and the token before the `*` here is a `)`.

    SO THE COMPOSITION ROOT NEEDS THREE CHANGES, NOT ONE, AND THE THIRD IS THE LOAD-BEARING ONE:
    the operand test must look for a clock-lever Attribute ANYWHERE IN THE OPERAND SUBTREE, not
    only at its root, so that `int(sysm.configs["RUN"].epochs)` counts as an `epochs` operand.
    Measured with all three on a scratch copy: with the inline multiply restored O11 FAILS naming
    this exact line, and with the tree as it stands it PASSES. A fourth thing comes with them --
    the narrowed skip must still exempt spine/assemble.py, whose COUPLINGS `compute` lambdas scale
    and combine clock levers BY DESIGN (that is what a declared coupling is); without that
    exemption the same three changes report four findings there, every one of them a correctly
    declared wire. All of this is the ownership pass's call and this file cannot make it -- but
    what it records now is what was measured, not a remedy nobody ran.
    """
    from spine import derive, units
    return derive.run_windows_from_epochs(units.Epochs(sysm.configs["RUN"].epochs),
                                          _windows_in_epoch(sysm))


def _windows_in_epoch(sysm):
    """This epoch's length in WINDOWS: (len(Segmentation.ids) - 1) // LM.ctx.

    THE -1 IS THE TARGET SHIFT, AND IT WAS MISSING UNTIL 2026-09-24 (Q-RUN-12). A window needs
    ctx + 1 ids, because `y` is `x` shifted one token (spine/loop.py::_window_bounds), so window i
    exists only while (i + 1) * ctx + 1 <= len(ids): that is (len - 1) // ctx windows, not
    len // ctx. The two differ exactly when len(ids) is a multiple of ctx -- about one epoch in
    ctx -- and there the old count declared a last window with no final target. The loop skipped
    it, but the clock had already counted it, and when it fell on a flush the clock closed a flush
    with no backward: driven on a 768-id segmentation at ctx=128, 6 flushes against 5 backward
    passes at OPT_BATCH_WINDOWS=1, and at OPT_BATCH_WINDOWS=2 the fifth window was accumulated,
    never flushed, never trained, and not counted in dropped_windows. Everywhere len is not a
    multiple of ctx the two spellings are the same number, so no run that avoided that case moves.

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
    return max(1, (len(sysm.segmentation.ids) - 1) // int(sysm.configs["LM"].ctx))


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
        # ['anchor_uses','anchor_w','arch','compose','ctx','ctx_widen','dropout','heads','layers',
        # 'mask_dead_rows','new_row_init','pos','vocab_slots','width'] (the two amendments of
        # 2026-09-28 among them, Q-LM-15) -- there is no `depth`, and
        # Config.__getattr__ RAISES on an undeclared name rather than returning a default. So the
        # first draft of this line killed every compose() at the gate stage, and the reason nothing
        # caught it is the reason it is worth this comment: RUN.process_setup RAISED
        # NotImplementedError several rows EARLIER, so the crash was unreachable and K2 -- "the
        # composition root imports and fails only at a stub" -- passed on a tree that could not run.
        # Past tense on purpose, and it is the whole point of the comment: process_setup has had a
        # body since P4 wrote one, so NOTHING SHIELDS THIS LINE ANY MORE. _geometry_manifest is
        # reached on every compose() today -- measured by running compose.compose(environ={}), which
        # builds all 21 manifest entries and returns a System at stage 'assembled' (2026-09-27;
        # until Q-EVAL-12's review this said it "only then stops at CAP.startup_refusals, row 29 of
        # ASSEMBLY_ORDER's 40", of a function that had a body, at the 30th of 41 rows). An
        # `lm.depth` written here now would kill the root at once.
        # A defect hidden behind an earlier stub is this project's oldest shape. K7 below is the
        # general form of the check that would have caught it at author time.
        "lm.layers":    (int(lm.layers), "EXACT", "LM_LAYERS", "the layer stack"),
        "lm.heads":     (int(lm.heads), "EXACT", "LM_HEADS", "head partition of width"),
        # EXACT UNLESS A WIDENING IS DECLARED (2026-09-28, register §8 3.6 and NEW-13; Q-LM-15):
        # at LM_CTX_WIDEN=1 a LARGER LM_CTX passes the gate, which lm/api.py::load_state then fits
        # by prefix, and a smaller one is still refused. The rule is read off the lever on each side
        # of the comparison that matters -- this run's -- and a recording's own rule is never read
        # (ckpt/api.py::check_geometry compares values under the LIVE rule).
        "lm.ctx":       (int(lm.ctx), "MAY_WIDEN" if bool(lm.ctx_widen) else "EXACT", "LM_CTX",
                         "positional table extent. EXACT at LM_CTX_WIDEN=0, the shipped value "
                         "(NEW-13); at 1 a larger LM_CTX is admitted at an epoch-boundary resume, "
                         "the learned table keeping the parent's rows (docs/04_CONTRACT.md "
                         "Q-LM-15)"),
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
                         "that FAB.load_state_dict names in its LEVERS READ. Its sidecar did not "
                         "record it until 2026-09-24 (and recorded d_model under the name dk), so "
                         "this field was the only check at either end"),
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
        # EXACT, NOT MAY_WIDEN, SINCE Q-WORLD-8 (b) MADE nmax THE TENSOR EXTENT. preds and keys are
        # allocated at nmax (world/api.py::build), and WORLD.load_into refuses ANY difference
        # between the saved and live allocation, "Both directions are refused". The MAY_WIDEN rule
        # here predates (b), when nmax sized only the fit/mass/alive buffers, and it let a larger
        # WORLD_NMAX through this gate -- listed as a legal widening -- to die at load_into after
        # LM, SIG and FAB were already built (driven 2026-09-24: WORLD_NMAX=8 against a checkpoint
        # at 6). A real prefix widen needs OPT's moments for preds/keys widened with it, which is
        # the same padding OPT.load_state now does for FAB and LM, and is not done here.
        "world.nmax":   (int(world.nmax), "EXACT", "WORLD_NMAX",
                         "preds/keys are allocated at nmax under Q-WORLD-8 (b); WORLD.load_into "
                         "refuses any difference in either direction"),
        "world.feedback": (bool(world.feedback), "EXACT", "WORLD_FEEDBACK", "H22"),
    }
    # LM.resolve is the authority on LM's shapes -- it is the row that refuses width % heads and
    # the ctx/pos_max overflow -- so where LMGeometry carries a field, its value replaces the raw
    # lever read above and pos_max joins the manifest. Two sources for one shape is how the
    # signature width came out 614 on one path and 1 on the other.
    _ctx_why = man["lm.ctx"][3]
    for name in ("width", "layers", "heads", "ctx", "pos_max", "vocab_slots"):
        value = getattr(geom, name, None)
        if value is None:
            continue
        key = "lm." + name
        prior = man.get(key)
        rule = prior[1] if prior else "EXACT"
        env = prior[2] if prior else ("LM_" + name.upper())
        why = "LM.resolve's resolved value, not the raw lever"
        if name in ("ctx", "pos_max"):
            # THE TABLE'S HEIGHT MOVES WITH lm.ctx, UNDER lm.ctx's RULE, AND BOTH CARRY lm.ctx's WHY
            # (2026-09-28, Q-LM-15). pos_max is the local wire from ctx, so at a declared widening
            # the two grow together and an EXACT pos_max would refuse the move lm.ctx admitted; and
            # the why is what CKPT's refusal prints, so it is the sentence that tells an operator
            # LM_CTX_WIDEN exists. pos_max's name is the one lm/api.py::load_state already prints
            # for this field: "LM_POS_MAX", which this line printed, names an environment variable
            # nothing reads (never reached -- the gate compares lm.ctx first, and pos_max cannot
            # move while ctx stands).
            rule, why = man["lm.ctx"][1], f"{_ctx_why}; {why}"
            if name == "pos_max":
                env = "LM_CTX (LM.d_pos_max)"
        man[key] = (value, rule, env, why)
    # THE FIELDS THAT DECIDE WHICH TENSORS EXIST ARE COMPARED FIRST, because check_geometry refuses
    # on the FIRST mismatch it meets and a shape field can move BECAUSE one of these did. LM_LAYERS=0
    # is a sentinel LM.resolve turns into a per-arch depth, so an LM_ARCH change alone (gru ->
    # transformer) also moves the resolved lm.layers, and with lm.layers ahead of lm.arch in this
    # dict the refusal named LM_LAYERS -- "written at lm.layers=1 and this run resolves 4" -- for a
    # lever the operator never touched (driven 2026-09-24). The order changes nothing a passing
    # resume sees: the gate compares every field either way.
    first = ("lm.arch", "lm.compose", "sig.mode")
    return {**{k: man[k] for k in first if k in man},
            **{k: v for k, v in man.items() if k not in first}}


def _sidecar(sysm, restored, prefix):
    """The recorded geometry fields SIG and FAB compare their own state against on a restore.

    They take theirs as a `sidecar` argument rather than through the manifest above because their
    refusals run AFTER their build -- which is exactly why the manifest reports the grown counts as
    UNCHECKED rather than pretending to have checked them. THAT WORD IS FOR THIS DIRECTION ONLY --
    recorded, and absent from the manifest. The reverse (in the manifest, absent from the recording)
    is ckpt/api.py::check_geometry's REFUSAL, and three statements in this file borrowed the word for it.

    IT RETURNED None ON EVERY REAL RESUME AND BOTH REFUSALS WERE THEREFORE DISARMED -- Q-CKPT-2's
    residue, RESOLVED 2026-09-22, and the producer it asked for turned out to exist already.
    This function read `Snapshot.geometry[PFX]`, a NESTED key. The recorded map is CKPT.save's
    `geometry`, which ROW_ARGUMENTS_ELSEWHERE declares to be _geometry_manifest(sysm) -- FLAT, with
    PREFIXED keys, 'sig.d' and 'fab.rank' -- so the lookup could not match at any point in its life.

    WHERE THE SIDECAR ACTUALLY IS: IN THE PACKAGE'S OWN PAYLOAD SLICE, WRITTEN BY THE PACKAGE.
    sig/api.py::state_dict returns a "sidecar" key and so does fabric/api.py::state_dict, and
    docs/04_CONTRACT.md's SIG section has said so in prose the whole time -- "Checkpointed: ... plus
    a sidecar carrying width_units, alphabet_size, space, d, mode". READ OFF A REAL CHECKPOINT
    rather than inferred: payload['SIG']['sidecar'] carries all five of the fields
    SIG.load_state_dict compares, payload['FAB']['sidecar'] all four of FAB's, and the flat
    manifest's sig.* is only ('sig.d', 'sig.space', 'sig.mode') -- three of five, MISSING
    width_units and alphabet_size, which are the two the whole refusal is about.

    SO THE OPEN QUESTION IS ANSWERED BY THE TREE AND NOT BY A DECISION HERE. This docstring used to
    ask whether the two `sidecar` parameters survive at all or whether a prefix SLICE of the flat
    manifest replaces them, and called that cheap "while both are stubs". Both have bodies now, so
    it is no longer cheap -- and the slice is the worse of the two answers anyway, because it cannot
    carry width_units: derive.signature_width_bytes reads Vocabulary.bytes_per_token, which is
    MEASURED over the build sample and so fails the wire predicate. The sidecar travels in the blob.
    Nothing frozen moves; the root hands back what the producer wrote.
    (The paragraph this replaces also said "FAB.state_dict does NOT have to emit a sidecar it never
    claimed to emit". It emits one -- slots, rank, dk, signature_dim -- and it is in the checkpoint.)

    A GUARD THAT CANNOT FIRE IS A DEFECT EVEN WHERE THE CODE AROUND IT IS CORRECT, so the warning
    below stays for the case it now describes: a blob written before the producer existed. With a
    snapshot in hand and a payload for this package but no sidecar in it, that warning is the only
    place a report can learn that the width refusal did not run.
    """
    if restored is None:
        return None
    payload = getattr(restored, "payload", None) or {}
    mine = payload.get(prefix)
    side = mine.get("sidecar") if isinstance(mine, dict) else None
    if side is None:
        # THE OLD LOOKUP, KEPT AS THE FALLBACK AND NOT AS THE RULE. It has never matched a blob this
        # tree wrote; it stays because a recorded geometry that DID carry a nested slice would still
        # be a legitimate thing to honour, and removing it would silently narrow what this function
        # accepts on the one boundary every goal-B number is measured across.
        side = (getattr(restored, "geometry", None) or {}).get(prefix)
    if side is None and sysm is not None and sysm.warnings is not None:
        sysm.warnings.append(
            f"{prefix}.load_state_dict: the snapshot carries no sidecar for {prefix}, so "
            f"sidecar=None and its width/shape refusal DID NOT RUN. {prefix}.state_dict writes a "
            f"'sidecar' key into its own payload slice and this snapshot's slice has none, which "
            f"means it was written before that producer existed. A resume from it cannot be "
            f"refused on a width it disagrees about.")
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
# one: an `improving` EMA pair (FAB already keeps one and a second would be two mechanisms deciding
# the same question); an `owners` rule beyond the one the old tree used; a `plateau` boolean (WORLD
# holds that state); and a scorer of the (ctx, src) arity MEM.judge and EVAL.wrongness_probe
# declare. THREE ABSENCES AND ONE ARITY, and each is one producer some deferral waits on rather than
# the set any of them waits on: `improving` bears on CAP.observe, `plateau` on WORLD.manage, the
# scorer on MEM.judge and EVAL.wrongness_probe. `owners` bears on none of them -- its RULE is
# declared on MEM.write's ROW_ARGUMENTS_ELSEWHERE entry, and what is declined here is inventing a
# BETTER rule, not supplying a missing one. (THIS PARAGRAPH COUNTED A `logits_fn` AMONG THE ABSENCES
# UNTIL 2026-09-27 and argued at length which deferrals waited on it; the history is in git.)
#
# THE logits_fn IS HERE NOW, AS TWO NAMED CLOSURES (2026-09-27, Q-EVAL-12, discharging Q-MEM-10's
# ruling). _logits_fn(sysm, *, use_memory) below is the ONLY place softmax -> MEM.read(promote=False)
# -> MEM.blend -> log is written anywhere in the tree, and NEITHER SIDE'S FROZEN SIGNATURE MOVED FOR
# IT: MEM.blend keeps `model_probs` as probabilities and EVAL keeps `logits_fn`. TWO CLOSURES, TWO
# SYSTEMS, AND EVERY READING NAMES WHICH (`.name`, 'memory-off' / 'memory-on'). use_memory=False is
# the trained path; use_memory=True adds retrieval, which has never entered training. FAB's
# `baseline_logits_fn` MUST ALWAYS BE THE MEMORY-OFF ONE, because fabric/api.py makes it load-bearing
# that the baseline comes from the same callable that produced `baseline_loss`.
# WHAT THE THREE DATA THIS PARAGRAPH SAID A HELD-OUT WINDOW LACKED BECAME, each ruled in Q-EVAL-12:
#   signature   encoded off the width_units bytes BEFORE the window (the pinned prefix), the slice
#               _sample_window takes at a training window's own index -- never off the window being
#               scored, which is the leak Q-FAB-7 closed.
#   domain_id   DOM.nearest, the id DOM.observe WOULD assign, with nothing written; -1 where it would
#               spawn, which bans exactly what a newborn domain's id would.
#   novelty     ZEROS, NAMED: the one datum with no honest source off the training path. A held-out
#               window has no previous flush, and zero says "nothing was surprising yet", as the
#               first flush of every run says it.
# AND ONE MORE, WHICH NO SENTENCE HERE ANTICIPATED: the ROUTING CLOCK. An eval pass runs
# FAB.forward at step_windows = clock.step + 1, the routing state the NEXT training window will use.
# FAB's identity cache hands a same-step pass the keys the training pass computed BEFORE the
# optimizer stepped, so at clock.step the probe read stale keys while a resumed child, whose cache
# is empty, computed fresh ones -- and a start reading could never equal the uninterrupted run's.
# At +1 the keys are recomputed at FAB_EMB_EVERY=1 (the shipped value) and are the next window's
# cached ones at larger values; nothing else FAB.forward reads from the step moves on an eval pass.
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
    targets, which is what LM.lm_loss is (lm/api.py::lm_loss). MEM.write's `contexts` is the same `x`
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
    ENDING AT THE CURSOR, i.e. the material already consumed. Nothing in the frozen surfaces states
    which end, and a run that encodes the units AHEAD of the cursor is encoding text the model has
    not trained on.
    AND THE WINDOW BEING PREDICTED IS AHEAD OF THE CURSOR -- IT HAS NOT BEEN TRAINED ON -- SO THE
    LOOP PASSES THAT WINDOW'S OWN 0-BASED INDEX, and the sample ends at the window's first byte
    (Q-FAB-7). The loop passed index + 1 until 2026-09-24, reading "reached" as "cut", and the
    paragraph above was therefore violated by its only caller: the sample ended at the LAST TARGET's
    first byte and covered the whole window (window 149 of a default run: x bytes [28402, 28599),
    sample [28407, 28599)), so the routing signature and the domain id FAB.forward bans on were both
    read off the text being scored.

    `at_window` IS THE WINDOW ORDINAL AND NOT A TOKEN OFFSET -- _signature_cursor multiplies it by
    LM.ctx. Passing `i * ctx` returns the window `i * ctx` windows in, which is a real window of the
    right width and completely the wrong material, so the error is silent by construction. Said here
    because it was made once while driving this function and cost half an hour.

    IT RETURNS THE FROZEN WIDTH OR IT DOES NOT RETURN -- AND IT RETURNED 173 UNITS AT ORDINAL 1
    UNTIL 2026-09-21, which sig/api.py::encode refuses outright ("no eval variant, no gist
    placeholder and no fallback ... because the alternative measured a whole project's routing on
    one byte"). The arithmetic: the cursor after one window is byte_pos[ctx] = 173 at the shipped
    geometry, width_units is 192, so `start` is -19, the clamp took it to 0, and the first flush of
    every run handed SIG a short window. Measured across 600 ordinals: exactly one is short, and it
    is the first.
    ORDINAL 0 IS CALLED NOW TOO, ON THE FIRST WINDOW OF EVERY EPOCH, AND ITS SAMPLE IS ALL PAD: the
    cursor is byte_pos[0] = 0, so there is no earlier material at all and the answer below applies
    to every one of the width_units units. That is the honest signature for the opening window of a
    text -- a generator starting cold holds exactly as much. IT DOES NOT COST ONLY ONE WINDOW PER
    EPOCH, which is what this sentence said until 2026-09-24: DOM.observe founds the run's first
    domain on that all-pad signature, the domain stays alive, and at a later epoch roll the new
    epoch's partly padded opening window is pulled back into it with boundary=True. Measured at
    DATA_STREAM_BYTES=30000 RUN_EPOCHS=2 DATA_RESAMPLE=1 (315 windows): windows 0 (191 pad units of
    191) and 1 (12) found and hold domain 0; window 158, epoch 1's second window (17 pad units), goes
    back to domain 0 with a boundary and 159 follows; part.n_boundaries 34 and n_created 14, against
    32 and 13 on the tree before Q-FAB-7 (whose window 0 had 12 pad units and whose epoch-1 opening
    stayed in the running domain). Keeping a pad-dominated sample out of DOM.observe would need a
    domain id for a window DOM did not assign, which is the owner's call (Q-FAB-7 (1)).
    THE HEAD IS LEFT-PADDED AND THE TAIL IS NOT, AND THE ASYMMETRY IS THE HONEST ONE. At ordinals
    0 and 1 the stream genuinely HAS no (or too few) earlier units -- the corpus has a beginning -- so this is "a real
    window whose text ran out", which spine/loop.py already distinguishes from "a caller declining
    to measure" at its own tail-padding site, and the pad goes on the side the material is missing
    from. Taking the units AHEAD instead is what this docstring's own paragraph above rules out;
    returning short is what SIG refuses; so padding at the head is the remaining answer and it is
    stated rather than inferred. Under space="tokens" the pad is token id 0, which is a real byte
    id and not a sentinel -- the same choice memory/api.py::_key_windows makes for its left pad
    ("padding with token id 0 is the same choice that tree made and is visible in the stored
    context").
    """
    stream = _signature_stream(sysm, sig)
    end = _signature_cursor(sysm, sig, at_window)
    width = int(sysm.sig.width_units)
    start = end - width
    if start >= 0:
        return stream[start:end]
    head = stream[0:end]
    # THE PAD MATCHES THE STREAM'S OWN TYPE, because the two consumers differ in what they do with
    # it: SIG.encode iterates it and DOM.observe stores it in a reservoir that rekey re-encodes, so
    # a bytes stream must stay concatenable as bytes and a token list as a list.
    n = width - len(head)
    return (bytes(n) + head) if isinstance(head, (bytes, bytearray)) else ([0] * n + list(head))


def _key_fn(sysm):
    """LM.encode bound to (lm, model): MEM.write's and MEM.maintain's `key_fn`.

    THE CALLABLE CLASS OF ARGUMENT HAS NO OTHER PRODUCER. It is an entry point partially applied,
    not a return value, so no `produces` column can hand it over without this file forming it --
    and memory/api.py's whole point is that MEM never imports LM.
    """
    lm = sysm.configs["LM"]
    return lambda x, **kw: lm_api.encode(lm, sysm.model, x, **kw)


def _head(sysm):
    """LM.decode bound to (lm, model) AND TO THE VOCABULARY: the training flush's FAB.forward
    `head`, a ONE-ARGUMENT callable.

    NOT a logits_fn: it decodes a hidden state that the fabric already produced. The logits_fn
    every probe wants is the WHOLE path including FAB.forward, and since 2026-09-27 that is
    _logits_fn below (Q-EVAL-12): the two closures run the flush's path through FAB.forward and hand
    it a head of their own, this same LM.decode at the same live boundary, wrapped to count its
    calls in the probe's book. (This paragraph said the whole path was "not formable today -- see
    DEFERRED_ENTRY_POINTS" until Q-EVAL-12's review; the retention probe formed it and left the
    sentence standing.) FAB.contribution's `head` is the memory-off closure's, not this one
    (2026-09-28, Q-FAB-19): the same LM.decode at the same live boundary, counted in the book its
    baseline's passes are counted in, so the held-out walks decode exactly as the baseline did.
    (The first line said "FAB.forward's and FAB.contribution's `head`" until then.)

    THE VOCABULARY IS BOUND HERE AND READ AT CALL TIME, AND THIS WAS `lambda h, **kw: decode(...)`
    UNTIL 2026-09-24. FAB calls `head(x)` with nothing else, and LM.decode's `live_vocab` and
    `retired_ids` are keyword-only and required, so the first vote would have raised TypeError --
    which nobody saw because nothing passed this closure to FAB.forward (the vote, the society
    blend, the independence loss and hop_sup were all inert for it). Reading sysm.vocab INSIDE the
    lambda, not at bind time, is what keeps one closure right across mints and retirements: the
    boundary is `Vocabulary.size()`, the positional one, for the reason spine/loop.py::_flush gives
    at its own LM.decode call -- the two calls must mask the same rows.
    """
    lm = sysm.configs["LM"]
    return lambda h: lm_api.decode(lm, sysm.model, h, live_vocab=int(sysm.vocab.size()),
                                   retired_ids=tuple(sysm.vocab.retired))


def _sig_encode_fn(sysm):
    """SIG.encode bound to the SigState: DOM.rekey's `encode`.

    domains/api.py::rekey says in as many words that `encode` is SIG.encode passed in. The rekey MUST
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


# ==================================================================================================
# THE RETENTION PROBE'S JOINS (2026-09-27, Proposal 04 SR0 and NEW-03, docs/04_CONTRACT.md Q-EVAL-12)
# ==================================================================================================

# THE ROOT'S EVAL BOOK, THE INTEGER KEYS. Seeded 0 at the 'probe' stage when the probe is armed and
# ABSENT otherwise; the two floats (eval.holdout.seconds, eval.mem.blend_weight_sum) and the
# generation pair are seeded beside them, the pair only where EVAL_GENERATE is on.
#   eval.holdout.calls             holdout_probe calls, every closure and every arm
#   eval.holdout.cadence_reads     readings the 'retention' cadence asked for
#   eval.holdout.phase_reads       readings at the first window of a phase
#   eval.holdout.boundary_reads    readings at R (both closures count)
#   eval.holdout.resume_reads      readings at a resume's start (both closures count)
#   eval.holdout.windows           windows scored
#   eval.holdout.cuts              TOK.tokenize calls the probe made (so MEM's remap count is
#                                  tok.segment_remap minus this)
#   eval.holdout.forwards          closure forwards; eval.holdout.decodes the head calls inside them
#   eval.holdout.sig_calls         SIG.encode calls the closures made -- the READINGS' passes, as R
#                                  reads the package rows; generation's, made after R, are counted
#                                  only as eval.generate.tokens (one forward per token per closure)
#   eval.holdout.areas_unarrived   a GAUGE: areas holding a pinned block the run has not reached, at
#                                  the last reading
#   eval.holdout.shortfall         items the pinned halves were too short to supply
#   eval.holdout.nonfinite         B readings with no finite control mean because a control window
#                                  scored non-finite (or the mean overflowed) -- not forwarded
#   eval.holdout.empty             B readings whose control half scored NO window -- no arrived area
#                                  holds a control item, or each cut to fewer than two ids -- not
#                                  forwarded, and not non-finite: nothing was read to be non-finite
#                                  (2026-09-27, Q-EVAL-12's review; both were booked as nonfinite)
#   eval.holdout.domain_spawn      closure passes DOM.nearest answered -1 for (a window the
#                                  partition would have minted a domain for)
#   eval.mem.reads / blends        the memory-on closure's MEM.read and MEM.blend calls, one each
#                                  per closure pass; eval.mem.empty the reads that hit nothing.
#                                  MEM.encode_queries is called once per read and encodes the pass's
#                                  B*L query rows in ONE key_fn call -- one LM.encode call -- so
#                                  lm.encode.calls moves by eval.holdout.forwards + eval.mem.reads
#   eval.mem.key_encodes           the QUERY ROWS those reads encoded (B*L per read), not calls
#   eval.blowup.fired              the alarm's fires, summed over every series; since_best a GAUGE
_EVAL_BOOK_KEYS = (
    "eval.holdout.calls", "eval.holdout.cadence_reads", "eval.holdout.phase_reads",
    "eval.holdout.boundary_reads", "eval.holdout.resume_reads", "eval.holdout.windows",
    "eval.holdout.cuts", "eval.holdout.forwards", "eval.holdout.decodes",
    "eval.holdout.sig_calls", "eval.holdout.areas_unarrived", "eval.holdout.shortfall",
    "eval.holdout.nonfinite", "eval.holdout.empty", "eval.holdout.domain_spawn",
    "eval.mem.reads", "eval.mem.key_encodes", "eval.mem.empty", "eval.mem.blends",
    "eval.blowup.fired", "eval.blowup.since_best")
# THE BOOK'S TWO GAUGES: readings of the arrived set and of the alarm's series, so a record that
# does not carry those (a probe-off run's, the 'probe' stage) does not carry these either.
_EVAL_BOOK_GAUGES = ("eval.holdout.areas_unarrived", "eval.blowup.since_best")
# FAB.contribution'S INTEGER KEYS IN THE SAME BOOK (2026-09-28, register §8 3.5; Q-FAB-19), seeded 0 at
# the 'probe' stage where it is armed and ABSENT otherwise; the 'probe' stage's comment says what
# each counts. They are the root's, as the probe's are: the passes are the root's, over five
# packages, and FAB's own ledger counts only what FAB did (fab.contrib_*, fab.holdout_applied).
_CONTRIB_BOOK_KEYS = ("eval.contrib.calls", "eval.contrib.empty", "eval.contrib.windows",
                      "eval.contrib.cuts", "eval.contrib.forwards", "eval.contrib.decodes",
                      "eval.contrib.sig_calls", "eval.contrib.sig_windows",
                      "eval.contrib.domain_spawn")


def _probe_armed(sysm):
    """Whether the retention probe can read at all: a pinned ProbeSet holding at least one area.

    EVAL_RETENTION_EVERY > 0 is folded in, because pin_holdout pins nothing at 0. This is the ARM
    TEST the loop makes BEFORE Cadences.due('retention', ...) is asked, so at 0 the gate's ledger
    reads zero checks. AN AREA IN items HOLDS A WINDOW (2026-09-27, Q-EVAL-12's review): until
    pin_holdout left out an area neither of whose halves could hold one, a ProbeSet of blocks too
    short for any window carried every area with two empty halves, and this test counted a probe
    armed that could never read. THE CADENCE AUDIT READS THE SAME TEST (_retention_audit, the flip's
    review): an armed probe's line names the reads beside its cadence, and one that pinned nothing
    is DISARMED whatever its period."""
    ps = sysm.probe_set
    return ps is not None and bool(ps.items)


def _phase_of(phase_bounds, byte):
    """The phase a byte of the epoch's stream falls in: the k with lo <= byte < hi in
    Plan.phase_bounds, the last phase past the final bound. 0 with no bounds."""
    for k, (lo, hi) in enumerate(phase_bounds or ()):
        if int(lo) <= int(byte) < int(hi):
            return k
    return max(0, len(phase_bounds or ()) - 1)


def _phase_windows(sysm):
    """How many of this epoch's windows open in each phase: [count per phase], each window placed
    by its FIRST byte (Segmentation.byte_pos at its first token), the byte the loop's phase-start
    test reads. The startup notice's input, and nothing else."""
    ctx = int(sysm.configs["LM"].ctx)
    bounds = tuple(sysm.plan.phase_bounds)
    counts = [0] * max(1, len(bounds))
    pos = sysm.segmentation.byte_pos
    start = 0
    for _w in range(_windows_in_epoch(sysm)):
        counts[_phase_of(bounds, pos[start])] += 1
        start += ctx
    return counts


def _area_ids(sysm):
    """{area label: area id} over Stream.area_names -- spine/derive.py::area_id of each name, the
    number FAB's area books and MEM's `area` column are keyed by (2026-09-28, register §8 3.1,
    NEW-10 and C37; Q-FAB-18, Q-MEM-16). The stream's names are the labels its bytes carry, so every
    label a Segmentation holds has an id here; DATA refused a collision at open_areas."""
    from spine import derive as _dv
    names = sysm.stream.area_names if sysm.stream is not None else sysm.areas.names
    return {str(n): _dv.area_id(str(n)) for n in names}


def _window_areas(sysm, pairs, ctx):
    """A flush's area ids: (one per window, one per position), or (None, None) when the
    segmentation carries no labels (Q-FAB-18, Q-MEM-16).

    A WINDOW'S AREA IS ITS FIRST TOKEN'S, and a token's is its first byte's (tok/api.py::tokenize,
    "a per-area score and a byte offset always agree") -- the byte the phase-start test and
    _phase_windows place a window by. FAB.observe credits a window's routing mass to that area. A
    POSITION'S AREA IS ITS INPUT TOKEN'S, the token whose byte offset MEM.write's `positions` records
    (Segmentation.byte_pos[a:a + ctx]), so a stored entry's area and its recorded offset name one
    byte. A label with no id (none can occur: the stream's labels are its area names) reads -1,
    "unknown", which both books leave uncredited."""
    labels = sysm.segmentation.labels
    if labels is None:
        return None, None
    ids = _area_ids(sysm)
    per_window = [ids.get(str(labels[a]), -1) for a, _b in pairs]
    per_position = [[ids.get(str(labels[q]), -1) for q in range(a, a + ctx)] for a, _b in pairs]
    return per_window, per_position


def _faded_ids(sysm, byte):
    """FAB.manage's `faded`: the area ids faded in the phase `byte` falls in -- DATA's
    Plan.faded[k], the schedule's -- together with Plan.parent_faded, the areas the resumed
    lineage's streams drew and this run schedules nowhere (2026-09-28, register §8 3.1, NEW-10 and
    C37; Q-FAB-18).
    Plan's indices index Areas.names. A frozenset: FAB asks it membership and nothing iterates it."""
    plan = sysm.plan
    k = _phase_of(sysm.stream.phase_bounds, byte)
    names = list(sysm.areas.names)
    faded = tuple(getattr(plan, "faded", ()) or ())
    phase = tuple(faded[k]) if k < len(faded) else ()
    parent = tuple(getattr(plan, "parent_faded", ()) or ())
    from spine import derive as _dv
    return frozenset(_dv.area_id(str(names[int(i)])) for i in phase + parent)


def _trust_units(sysm, lo, hi):
    """DATA.claims_observe's `units` and `sources` over this epoch's ids[lo:hi] (2026-09-28,
    Proposal 04 SR3; Q-DATA-11): each TOK unit's BYTES, cut out of Stream.bytes at
    Segmentation.byte_pos -- unit p is bytes[byte_pos[p]:byte_pos[p + 1]], the last to the stream's
    end, the definition spine/loop.py::_window_bytes counts with -- and each unit's source name off
    Stream.sources and Stream.source_names: the source run holding its first byte, or None where a
    later run starts inside the unit, whose bytes then come from two sources and which no claim may
    span. A join over TOK's record and DATA's, which O10 forbids either package to form; 04
    section 5's (ids, decode) became bytes here because DATA may not import TOK. It draws nothing
    and writes nothing. A Stream carrying no source table gives every unit None."""
    pos = sysm.segmentation.byte_pos
    data = sysm.stream.bytes
    n = len(data)
    runs = tuple(getattr(sysm.stream, "sources", ()) or ())
    names = tuple(getattr(sysm.stream, "source_names", ()) or ())
    offs = [int(o) for o, _i in runs]
    units, sources = [], []
    r = bisect.bisect_right(offs, int(pos[lo])) - 1 if (runs and hi > lo) else -1
    for p in range(int(lo), int(hi)):
        b0 = int(pos[p])
        b1 = int(pos[p + 1]) if p + 1 < len(pos) else n
        units.append(data[b0:b1])
        while r + 1 < len(offs) and offs[r + 1] <= b0:
            r += 1
        if r < 0:
            sources.append(None)
        elif r + 1 < len(offs) and offs[r + 1] < b1:
            sources.append(None)
        else:
            sources.append(names[int(runs[r][1])])
    return units, sources


def _trust_audit(sysm, lines, *, run_windows, periods):
    """RUN.cadence_audit's `lines`, with the one it writes for 'data.trust' in the root's words
    (2026-09-28, Q-DATA-11's review). -> list of str, every other line RUN's, unchanged.

    RUN'S TWO SENTENCES ARE WRITTEN FOR A GATE THAT IS ITS CADENCE AND NOTHING MORE, and the book's
    is not: DATA_TRUST arms it -- the loop's arm test withholds every pass at 'off' before the gate
    is asked -- and at 'observe' the loop passes it beside its cadence, on the window that rolls
    each epoch and at a stop's tail. So RUN's line was wrong three ways, each driven on the build:
      * at DATA_TRUST='off' DATA.trust_period is 0 whatever DATA_TRUST_EVERY is, and "Set a period
        of 1 or more on the package that owns this threshold" arms nothing -- DATA_TRUST_EVERY=1 at
        'off' printed the same line, and a default run gained it as one more startup warning;
      * at 'observe' with DATA_TRUST_EVERY=0 it said "Whatever it gates does not happen in this
        run", and a 30-window real-source run that printed it then made a tail pass over 3841 units
        that formed 38 claims, the ledger reading (30, 0, None, Windows(0));
      * at 'observe' with a period the run is too short for, the starved sentence said the same.
    The arm test and both passes are spine/loop.py's, so the line for this key is the root's. It
    replaces RUN's, found by the key RUN opens each of its lines with; a run in which the gate can
    fire gets no line, as before, and the mapping RUN audits is the one new_cadences was given --
    this is a rewording of one line, not a second audit. The default run's 'off' line was a warning
    Q-DATA-11 lists among what the default changes, until 04-6.3's flip (2026-09-29): at the shipped
    'observe' a run long enough for one DATA_TRUST_EVERY period gets no line for this key."""
    key = "data.trust"
    tag = f"cadence audit: {key!r} "
    if key not in periods or not any(str(ln).startswith(tag) for ln in lines):
        return list(lines)
    dat = sysm.configs["DATA"]
    n, run_n, every = int(periods[key]), int(run_windows), int(dat.trust_every)
    if str(dat.trust) == "off":
        own = (f"cadence audit: {key!r} is DISARMED by DATA_TRUST='off' (DATA.trust_period is {n} "
               f"windows there) -- no source-reliability book is kept, and the loop's arm test "
               f"withholds every pass before this gate is asked, at any DATA_TRUST_EVERY (this "
               f"run's is {every}) and any run length, so no period reaches it. Nothing the run "
               f"trains on reads the book. DATA_TRUST='observe' arms it: the book then reads the "
               f"units the windows consume, every DATA_TRUST_EVERY windows, on the window that "
               f"rolls each epoch and at a stop's tail, and changes nothing the run trains on.")
    else:
        beside = ("-- but the book is kept, and it is not idle: the loop still passes it on the "
                  "window that rolls each epoch and, where a stop leaves consumed units unread, "
                  "once more at the end, so it reads every unit this run consumes, at those passes "
                  "only.")
        if n <= 0:
            own = (f"cadence audit: {key!r} has a period of {n} windows "
                   f"(DATA_TRUST_EVERY={every}), so the book's PERIODIC pass is DISARMED at any "
                   f"run length {beside} Set DATA_TRUST_EVERY to 1 or more for a pass every that "
                   f"many windows as well.")
        else:
            own = (f"cadence audit: {key!r} has a period of {n} windows and this run is {run_n} "
                   f"windows long, so the book's PERIODIC pass CANNOT FIRE ONCE {beside} Shorten "
                   f"DATA_TRUST_EVERY for a pass every that many windows as well.")
    return [own if str(ln).startswith(tag) else ln for ln in lines]


def _retention_audit(sysm, lines, *, run_windows, periods):
    """RUN.cadence_audit's `lines` (after _trust_audit), with the line for 'retention' in the root's
    words wherever RUN's would be false (2026-09-29, the flip's review; Q-EVAL-12). -> list of str,
    every other line as it was handed in.

    RUN'S TWO SENTENCES ARE WRITTEN FOR A GATE THAT IS ITS CADENCE AND NOTHING MORE, and the probe is
    not: its arm test is the root's (_probe_armed, a pinned ProbeSet) and the loop asks it before
    the gate, and an armed probe reads beside its cadence -- at the first window of every phase, at a
    resume's start and at R through both closures -- and generates after the final save. So RUN's
    line was false two ways once 04-6.2's flip shipped 1000:
      * ARMED, WITH A PERIOD THE RUN IS TOO SHORT FOR -- every shipped-default run of 506-937
        windows -- RUN said the gate "CANNOT FIRE ONCE. Whatever it gates does not happen in this
        run ... Shorten the period", and B1's record at the flip (`run.py --max-windows 80` at
        DATA_STREAM_BYTES=120000) reads eval.holdout.calls 3, one phase-start read and R's two,
        cadence_reads 0, and 16 continuations generated; the advice named 04-6.2's ruled interim
        value as the fault;
      * WITH EVAL_RETENTION_EVERY ABOVE 0 AND NOTHING PINNED -- no area holding a block, or no half
        long enough for a window behind its prefix (B6's 20,000-byte stream) -- the arm test
        withholds every reading, the phase starts' and R's with the cadence's, so RUN's advice to
        shorten the period reaches nothing, and where the period fits the run RUN wrote no line at
        all, or its "every declared gate can fire", for a gate the loop never asks.
    At EVAL_RETENTION_EVERY=0 RUN's DISARMED line is true and stands: nothing is pinned, read or
    generated, and a period of 1 or more is what arms the probe. An armed probe whose period the run
    can reach gets no line, as before. The root's line replaces RUN's, found by the key RUN opens
    each line with; where RUN wrote none -- a positive period over a probe that pinned nothing, the
    one state RUN cannot see -- ONE line is added, at the key's place in the mapping's order, in
    place of RUN's "every declared gate can fire" when that was the whole audit. The mapping RUN
    audits is the one new_cadences was given: this words one key's line, it is not a second audit."""
    key = "retention"
    tag = f"cadence audit: {key!r} "
    if key not in periods:
        return list(lines)
    ev = sysm.configs["EVAL"]
    every, n, run_n = int(ev.retention_every), int(periods[key]), int(run_windows)
    ps = sysm.probe_set
    have = any(str(ln).startswith(tag) for ln in lines)
    if every <= 0:
        return list(lines)
    if _probe_armed(sysm):
        if not have:
            return list(lines)
        gen = ", and it generates after the final save" if bool(ev.generate) else ""
        own = (f"cadence audit: {key!r} has a period of {n} windows and this run is {run_n} windows "
               f"long, so the probe's PERIODIC reading CANNOT FIRE ONCE -- but the probe is armed, "
               f"and it is not idle: it still reads at the first window of every phase, and those "
               f"readings are what CKPT's best-model retention, the blow-up alarm and, at "
               f"OPT_DAMP_SOURCE='probe', OPT's damping read; it reads through both closures at R "
               f"and at a resume's start{gen}. A report of those readings is a report of a "
               f"mechanism that ran. The period is EVAL_RETENTION_EVERY={every}, the cadence alone "
               f"(04-6.2 ships 1000, the interim telemetry value until E6 picks); one at or below "
               f"{run_n} adds a periodic reading as well.")
    else:
        why = (ps.reason if ps is not None and ps.reason else
               "the retention probe pinned no window on this run.")
        own = (f"cadence audit: {key!r} is DISARMED although its period is {n} windows "
               f"(EVAL_RETENTION_EVERY={every}): the probe pinned nothing -- {why} The loop's arm "
               f"test withholds every reading before this gate is asked -- the phase starts', R's "
               f"and a resume's start's with the cadence's -- so no period reaches it: nothing is "
               f"read, generated or handed to CKPT's best-model retention, the blow-up alarm or OPT, "
               f"and a report that says the probe did nothing is reporting a mechanism that was "
               f"never armed.")
    if have:
        return [own if str(ln).startswith(tag) else ln for ln in lines]
    if lines and all(str(ln).startswith("cadence audit: every declared gate can fire")
                     for ln in lines):
        return [own]
    order = list(periods)
    head = "cadence audit: '"
    out, placed = [], False
    for ln in lines:
        s = str(ln)
        k = s[len(head):].split("'", 1)[0] if s.startswith(head) else None
        if not placed and k in order and order.index(k) > order.index(key):
            out.append(own)
            placed = True
        out.append(ln)
    if not placed:
        out.append(own)
    return out


def _probe_notices(sysm, ev):
    """The two startup notices the register asks for, PRINTED AND NEVER APPLIED (04 section 6).

    EVAL_RETENTION_EVERY above 160 is outside the only cadence ever measured (the d3 toy's 160);
    and a phase the cadence would read fewer than five times -- derive.readings_in over the phase's
    windows, plus its phase-start read -- gives a focus signal too thin to act on. Both are said
    before the first window, into System.warnings, and neither changes a number."""
    from spine import derive as _dv, units as _Ud
    every = int(ev.retention_every)
    if every > 160:
        sysm.warnings.append(
            f"EVAL_RETENTION_EVERY={every} is above 160, the only retention cadence ever measured "
            f"(Proposal 04 section 6). The probe runs at it; nothing is changed. The register's "
            f"04-6.2 value is 1000 for telemetry, and every retention arm sets 160.")
    period = eval_api.retention_period(ev)
    thin = []
    for k, n in enumerate(_phase_windows(sysm)):
        reads = _dv.readings_in(_Ud.Windows(int(n)), period) + 1
        if reads < 5:
            thin.append(f"phase {k}: {n} window(s), about {reads} reading(s)")
    if thin:
        sysm.warnings.append(
            f"EVAL_RETENTION_EVERY={every}: {len(thin)} phase(s) of this epoch would be read fewer "
            f"than five times ({'; '.join(thin)} -- the cadence's readings plus the phase-start "
            f"read, derive.readings_in). A reading series that short cannot show a phase's trend; "
            f"nothing is changed.")


def _view_tuple(view):
    """A recorded segmentation view ([size, [retired ids]] in the log) as TOK.tokenize's `view`."""
    return (int(view[0]), tuple(int(x) for x in view[1]))


def _last_cut_view(sysm):
    """The view the stream in force was last cut at: the segmentation log's last event's."""
    return _view_tuple(sysm.seg_log["events"][-1]["view"])


def _holdout_tokenize(sysm, view=None, book="eval.holdout"):
    """EVAL.holdout_probe's `tokenize_fn`: TOK.tokenize bound to the vocabulary AT A RECORDED VIEW.

    THE VIEW IS THE LAST CUT'S, NOT THE TABLE AS IT NOW STANDS (Q-EVAL-12). The model was trained on
    the stream cut at that view, and ids minted since have appeared in no training window, so a
    held-out window cut at the live table would be scored in a segmentation the run never trained
    on -- a reading of the vocabulary's growth, not of retention. A resume's start reading passes
    its PARENT's last-cut view (LOOP.eval), so it reads what the parent's final reading read; where
    the resume's own first cut is at another view, it reads again at that one (spine/loop.py's
    'resume_own', 2026-10-02).

    NO LABELS AND regularize=False, so it draws nothing from the dropout stream, bypasses TOK's
    one-slot cache and counts tok.segment_remap; every cut is booked as eval.holdout.cuts, so
    MEM's remap count is tok.segment_remap minus it. `book` is the book's prefix: FAB.contribution's
    material is cut here too and booked as eval.contrib.cuts (2026-09-28, Q-FAB-19), so the probe's
    count stays the probe's."""
    tok = sysm.configs["TOK"]
    v = _last_cut_view(sysm) if view is None else _view_tuple(view)
    books = sysm.eval_books if sysm.eval_books is not None else {}
    key = f"{book}.cuts"

    def tokenize_fn(data):
        if key in books:
            books[key] += 1
        return tok_api.tokenize(tok, sysm.vocab, bytes(data), view=v)
    return tokenize_fn


def _holdout_units(sysm, arrived, parent=()):
    """EVAL.holdout_probe's `units_by_domain`: the ARRIVED areas' pinned (prefix, window) pairs.

    {area: {"control": [(prefix, window), ...], "report": [...], "seen_by_parent": bool}}. An area
    whose phase this run has not reached is left out: it has trained on nothing, and its reading
    would be a measurement of nothing (eval.holdout.areas_unarrived counts them). `parent` is the
    set the snapshot's parent had reached, so a reader can tell retention of what the parent
    learned from a first look at an area this lineage has just met."""
    ps = sysm.probe_set
    out = {}
    for area in sorted(arrived):
        got = ps.items.get(area) if ps is not None else None
        if not got:
            continue
        out[area] = {"control": [(p, w) for _s, p, w in got["control"]],
                     "report": [(p, w) for _s, p, w in got["report"]],
                     "seen_by_parent": area in set(parent or ())}
    return out


def _gen_prompts(sysm, arrived, view=None):
    """EVAL.generate's `prompts_by_domain`: each arrived area's REPORT-half pinned windows, cut at
    the last-cut view -- {area: [{"prefix": bytes, "prompt": bytes, "ids": [token ids]}]}, `prompt`
    the window's bytes, `ids` their cut and `prefix` the routing prefix before them. Report-half, so
    a prompt is text no consumer has read and the run never trained on; EVAL chooses how many to use.
    THE WINDOW'S BYTES TRAVEL WITH ITS IDS (2026-09-27, Q-EVAL-12's review) so the Sample can record
    the text the model continued: it recorded the prefix under `prompt`, and EVAL cannot decode the
    ids to recover the window, having no vocabulary."""
    ps = sysm.probe_set
    cut = _holdout_tokenize(sysm, view)
    out = {}
    for area in sorted(arrived):
        got = ps.items.get(area) if ps is not None else None
        if not got:
            continue
        out[area] = [{"prefix": p, "prompt": w, "ids": list(cut(w).ids)}
                     for _s, p, w in got["report"]]
    return out


def _contrib_material(sysm, arrived):
    """FAB.contribution's batch (2026-09-28, register §8 3.5; Q-FAB-19): (x, y, prefix_bytes, rows)
    or None where no arrived area holds a control window that cuts to two ids.

    THE PROBE'S CONTROL HALF, AND ONLY THE ITEMS A CADENCE READING SCORES: the first
    (EVAL_RETENTION_N + 1) // 2 pinned control items of every ARRIVED area -- EVAL.holdout_probe's
    own control share, the odd one to control -- in area order and pin order. Held-out text the
    consumers read and the run never trained on, pinned once per run, so every pass measures the
    same windows; the report half stays unread by any consumer. An area whose phase has not begun is
    left out, for _holdout_units' reason: its reading would be of text the run has not met.
    CUT AT THE LAST-CUT VIEW (_holdout_tokenize, booked eval.contrib.cuts) and TRUNCATED TO A COMMON
    LENGTH -- the shortest cut, from the end, so each row's routing prefix still ends at its first
    byte -- because one closure pass scores one (B, L) batch; a window cut to fewer than two ids
    scores nothing and is left out, as the probe leaves it. THE LENGTH IS CAPPED AT LM.ctx + 1 ids as
    well, so x never holds more than LM.ctx: the closure keeps the LAST LM.ctx of a longer x (it owns
    generation's window), and the logits would then no longer line up with y. A window pinned at
    LM.ctx + 1 bytes cuts to at most that many ids, so the cap binds on no pinned window today; it is
    the rule, not a repair. x is ids[:L-1] and y the ids shifted one, on the process device, and
    `rows` is how many windows the batch holds."""
    import torch
    ps = sysm.probe_set
    take = (int(sysm.configs["EVAL"].retention_n) + 1) // 2
    cut = _holdout_tokenize(sysm, book="eval.contrib")
    rows = []
    for area in sorted(arrived):
        got = ps.items.get(area) if ps is not None else None
        if not got:
            continue
        for _s, p, w in list(got["control"])[:take]:
            ids = list(cut(w).ids)
            if len(ids) >= 2:
                rows.append((bytes(p), ids))
    if not rows:
        return None
    n = min(min(len(ids) for _p, ids in rows), int(sysm.configs["LM"].ctx) + 1)
    dev = sysm.process.device
    x = torch.tensor([ids[:n - 1] for _p, ids in rows], dtype=torch.long, device=dev)
    y = torch.tensor([ids[1:n] for _p, ids in rows], dtype=torch.long, device=dev)
    return x, y, [p for p, _ids in rows], len(rows)


def _contrib_baseline(sysm, fn, x, prefix_bytes):
    """FAB.contribution's `baseline_logits_fn`: the memory-off closure bound to the batch, called
    with any autocast the caller holds TURNED OFF (2026-09-28, Q-FAB-19). The root calls
    FAB.contribution inside Process.autocast, because its held-out walks must run FAB.forward and
    the head under the autocast the closure runs them under; and the closure opens that autocast
    itself, around embed..decode only, so SIG.encode and DOM.nearest run outside it. Called under
    the caller's autocast they would run inside it, and on a bf16 device the baseline contribution
    re-forms would not be the one the root scored. On the shipped fp32 arms Process.autocast is a
    null context and so is this."""
    import torch

    def baseline():
        off = (torch.autocast(device_type="cuda", enabled=False)
               if sysm.process.amp_state == "active" else contextlib.nullcontext())
        with off:
            return fn(x, prefix_bytes=prefix_bytes)
    return baseline


def _eval_modules(sysm):
    """Every torch module a probe pass runs through -- the LM, FAB's module dict, WORLD's parts and
    SIG's encoder -- so the closure can put each in eval mode and restore each submodule's own
    flag afterwards. A part that is not a module (a bare parameter, the bigram table) has no mode."""
    import torch
    tops = [sysm.model, getattr(sysm.fabric, "modules", None)]
    for name in ("encoder", "qproj", "world_proj", "preds", "keys"):
        tops.append(getattr(sysm.world, name, None))
    tops.append(getattr(sysm.sig, "encoder", None))
    return [m for m in tops if isinstance(m, torch.nn.Module)]


@contextlib.contextmanager
def _eval_mode(sysm):
    """Every module _eval_modules names in eval mode for the body, and each SUBMODULE's own flag put
    back after it, raise or not. The closure's own mode handling since 2026-09-27 (Q-EVAL-12),
    lifted into one place on 2026-09-28 (Q-FAB-19) because FAB.contribution's held-out walks run
    OUTSIDE the closure -- FAB.forward and the head, between two closure calls -- and must run in
    the modes the closure's pass ran in: LM.decode's readout dropout is a training-mode draw, and a
    walk that took it would score a different function from its baseline and move torch's global
    stream (frozen_rng refuses that)."""
    tops = _eval_modules(sysm)
    modes = [(m, m.training) for t in tops for m in t.modules()]
    try:
        for t in tops:
            t.eval()
        yield
    finally:
        for m, was in modes:
            m.training = was


def _prefix_units(sysm, prefix, view, books, book="eval.holdout"):
    """SIG's units for one row: the width_units units ENDING at the row's first byte, the slice
    _sample_window takes at a training window's own index (Q-FAB-7), cut from the pinned prefix and
    LEFT-PADDED where the prefix is shorter, as _sample_window pads the opening windows of a stream.
    Under space='tokens' the prefix is cut at `view` first (a cut, booked) and padded with id 0; a
    prefix of width_units BYTES then yields fewer tokens than width_units, so the tokens-space
    signature is more padded than a training window's -- recorded in Q-EVAL-12, on an arm the
    tree does not ship."""
    width = int(sysm.sig.width_units)
    if sysm.configs["SIG"].space == "tokens":
        ids = []
        if prefix:
            if f"{book}.cuts" in books:
                books[f"{book}.cuts"] += 1
            ids = list(tok_api.tokenize(sysm.configs["TOK"], sysm.vocab, bytes(prefix),
                                        view=view).ids)
        ids = ids[len(ids) - width:] if len(ids) > width else ids
        return [0] * (width - len(ids)) + ids
    units = bytes(prefix)[max(0, len(prefix) - width):]
    return bytes(width - len(units)) + units


def _logits_fn(sysm, *, use_memory, view=None, live_domains=None, live_vocab=None,
               book="eval.holdout"):
    """THE PATH THE RUN TRAINED, as a closure: fn(x, *, prefix_bytes) -> (B, L, V) logits.

    ONE CLOSURE PER SCORED SYSTEM (eval/api.py::<module>'s ONE LOGITS PATH; Q-MEM-10, Q-EVAL-12).
    use_memory=False is the trained path and is named 'memory-off'; use_memory=True adds retrieval
    -- softmax -> MEM.encode_queries -> MEM.read(promote=False) -> MEM.blend -> log, written here and
    nowhere else -- and is named 'memory-on'. Every reading records the name. At MEM_BLEND_MAX=0
    blend returns the model's distribution itself, and the memory-on closure then returns the
    memory-off logits unchanged rather than their log-softmax, so the two agree to the bit there.

    THE PATH, IN THE FLUSH'S ORDER: SIG.encode on each row's prefix units (_prefix_units), then
    DOM.nearest on row 0's signature (the domain the window WOULD be routed to, with nothing
    written; -1 where DOM would spawn, which bans what a newborn id would), then under
    Process.autocast LM.embed, WORLD.forecast, LM.encode(extra=), FAB.forward(training=False) with
    the head (LM.decode at the live vocabulary boundary, wrapped to count decodes), targets=None,
    step_windows=clock.step + 1 (the NEXT window's routing clock -- see the paragraph above these
    joins), the nearest domain, the live-domain count the next training window will use and
    novelty ZEROS; then the vote's logits, or LM.decode of the routed hidden where nothing voted.
    ALL UNDER no_grad, every module in eval mode, each submodule's own mode put back after -- so a
    closure pass trains nothing, drops nothing and draws nothing (EVAL.holdout_probe refuses a
    reading that moved a global stream).

    THE CLOSURE OWNS GENERATION'S WINDOW AND PREFIX: handed more than LM.ctx tokens it keeps the
    last LM.ctx and appends the dropped ids' bytes (TOK.Vocabulary.decode) to the row's prefix, so
    a continuation is routed on the text before its window exactly as a training window is.

    `view` (the cut the tokens-space prefix is taken at) and `live_domains` default to the live
    run's -- the last-cut view and System.live_domains; a resume's start reading passes its parent's
    recorded ones.

    `live_vocab` IS GENERATION'S AND ONLY GENERATION'S: the ids at and above it (TOK.Vocabulary.size(),
    the positional boundary LM.decode's own live_vocab takes) are set to -inf after the whole path,
    the memory blend included -- the frozen tree's `vlim`, "never sample untrained ids"
    (self_organize.py:3857-3867). At the shipped LM_MASK_DEAD_ROWS=0 the head spans LM_VOCAB_SLOTS and
    a never-minted row keeps some mass, and a sampled one has no bytes: driven 2026-09-27, a 30-window
    run's generation drew one and TOK.Vocabulary.decode raised IndexError after the final save,
    taking the report with it. A READING never passes it: the held-out bits/byte are scored on
    the distribution the run trains on, dead rows and all.

    FAB.contribution'S BASELINE IS THIS CLOSURE (2026-09-28, register §8 3.5; Q-FAB-19), memory-off,
    bound to a batch of the probe's control items, and three things serve it and change no
    reading: `book` is the prefix the closure's passes are booked under -- 'eval.holdout' for the
    probe, 'eval.contrib' for contribution's, so each instrument's passes stand in its own keys --
    `fn.head` is the counted head the closure decodes with, and `fn(x, prefix_bytes=..., route={})`
    fills the dict with the FAB.forward inputs the pass used (h, signature, novelty, domain_id,
    live_domains, step_windows): the inputs contribution's held-out walks must be handed for its
    baseline and its counterfactuals to be ONE FUNCTION of the same inputs. EVAL never passes
    `route`, and a call without it is the call it always was."""
    import torch
    from spine import units as _Ul
    cfg = sysm.configs
    lm, fab, sig, world, dom, mem = (cfg["LM"], cfg["FAB"], cfg["SIG"], cfg["WORLD"], cfg["DOM"],
                                     cfg["MEM"])
    ctx = int(lm.ctx)
    books = sysm.eval_books if sysm.eval_books is not None else {}
    vw = _last_cut_view(sysm) if view is None else _view_tuple(view)
    key_fn = _key_fn(sysm)

    def _book(k, n=1):
        if k in books:
            books[k] += n

    def head(h):
        _book(f"{book}.decodes")
        return lm_api.decode(lm, sysm.model, h, live_vocab=int(sysm.vocab.size()),
                             retired_ids=tuple(sysm.vocab.retired))

    def fn(x, *, prefix_bytes, route=None):
        dev = sysm.process.device
        x = x.to(device=dev, dtype=torch.long)
        pref = [bytes(p) for p in prefix_bytes]
        n_tok = int(x.shape[1])
        if n_tok > ctx:
            drop = x[:, :n_tok - ctx].tolist()
            x = x[:, n_tok - ctx:]
            pref = [pref[b] + sysm.vocab.decode([int(t) for t in drop[b]]) for b in range(len(pref))]
        B = int(x.shape[0])
        with _eval_mode(sysm):
            with torch.no_grad():
                units = [_prefix_units(sysm, p, vw, books, book) for p in pref]
                sig_vec = sig_api.encode(sig, sysm.sig, units)
                _book(f"{book}.sig_calls")
                # THE ROWS THAT ENCODE ENCODED, where the book keeps them: eval.contrib's batch is
                # many rows a pass, so sig.encode_windows moves by this and not by the calls
                # (Q-FAB-19). The probe's passes are one row each and its book has no such key.
                _book(f"{book}.sig_windows", len(units))
                if sig_vec.device != x.device:
                    sig_vec = sig_vec.to(x.device)
                did = dom_api.nearest(dom, sysm.partition, signature=sig_vec[0])
                if did < 0:
                    _book(f"{book}.domain_spawn")
                n_live = int(live_domains if live_domains is not None else (sysm.live_domains or 1))
                nov = torch.zeros(B, device=x.device)
                at = _Ul.Windows(int(sysm.clock.step) + 1)
                with sysm.process.autocast():
                    obs_emb = lm_api.embed(lm, sysm.model, x)
                    h = lm_api.encode(lm, sysm.model, x,
                                      extra=world_api.forecast(world, sysm.world, obs_emb))
                    out = fab_api.forward(
                        fab, sysm.fabric, h=h, signature=sig_vec, novelty=nov, head=head,
                        targets=None, step_windows=at, domain_id=did, live_domains=n_live,
                        training=False)
                    logits = out.logits if out.logits is not None else head(out.hidden)
                if route is not None:
                    route.update(h=h, signature=sig_vec, novelty=nov, domain_id=did,
                                 live_domains=n_live, step_windows=at)
                _book(f"{book}.forwards")
                if use_memory:
                    V = int(logits.shape[-1])
                    probs = torch.softmax(logits.float(), dim=-1).reshape(-1, V)
                    queries = mem_api.encode_queries(mem, contexts=x, key_fn=key_fn)
                    _book("eval.mem.key_encodes", int(queries.shape[0]))
                    got = mem_api.read(mem, sysm.store, queries=queries, promote=False)
                    _book("eval.mem.reads")
                    if not bool((got.hits >= 0).any()):
                        _book("eval.mem.empty")
                    mixed = mem_api.blend(mem, probs, got)
                    _book("eval.mem.blends")
                    if "eval.mem.blend_weight_sum" in books:
                        books["eval.mem.blend_weight_sum"] += float(got.blend.float().sum())
                    # AT MEM_BLEND_MAX=0 blend HANDS BACK THE MODEL'S OWN DISTRIBUTION, the same
                    # object, and the memory-on prediction IS the memory-off one: it is returned as
                    # those logits, not as log(softmax(logits)), whose rounding would part two
                    # closures that agree in law at the last bit -- and a generation drawing on
                    # that bit by inverse CDF at one boundary uniform.
                    if mixed is not probs:
                        logits = torch.log(mixed).reshape(B, -1, V)
                if live_vocab is not None and int(live_vocab) < int(logits.shape[-1]):
                    logits = logits.clone()
                    logits[..., int(live_vocab):] = float("-inf")
        return logits

    fn.name = "memory-on" if use_memory else "memory-off"
    fn.head = head
    return fn


def _periods(sysm):
    """{gate key: units.Windows} -- the periods RUN.new_cadences and RUN.cadence_audit take.

    ASSEMBLED HERE BECAUSE NO PACKAGE CAN. Each period belongs to the package that DECLARES its kind
    and arrives through that package's typed accessor -- EVAL.curve_period, DOM.manage_period,
    FAB.manage_period, MEM.rekey_period, CKPT.save_period, since 2026-09-27 (Q-EVAL-12)
    EVAL.retention_period and, since 2026-09-28 (Q-DATA-11), DATA.trust_period -- and a mapping
    spanning seven packages is exactly the object O10 forbids any one of them to build (EVAL was
    already in it, so the seventh key added no package; the eighth, 'data.trust', added DATA). RUN
    evaluates gates, and RUN owns no threshold THAT DECIDES ANYTHING THE MODEL COMPUTES -- which is
    the sentence new_cadences means, and the one 'progress' entry is the exception that has to be
    stated rather than smuggled.

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
    many of these eight are which.

    THE ACCESSORS EXIST BECAUSE Cadences.due REFUSES A BARE INT. Three of the five gates were handed
    cfg.manage_every directly until 2026-08-30, and Config hands back a bare int for all 38 levers
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
        # THE RETENTION PROBE'S CADENCE (2026-09-27, Q-EVAL-12): EVAL_RETENTION_EVERY, 0 the probe
        # off. The audit's line for this key is _retention_audit's wherever the probe is armed or
        # pinned nothing, since the reads beside the cadence and the arm test are this file's (the
        # flip's review, 2026-09-29).
        "retention": eval_api.retention_period(r["EVAL"]),
        # THE SOURCE-RELIABILITY BOOK'S CADENCE (2026-09-28, Q-DATA-11): DATA_TRUST_EVERY at
        # DATA_TRUST='observe', and 0 -- disarmed, which the audit says -- at 'off'. The audit's
        # line for this key is _trust_audit's, naming DATA_TRUST='observe' as what arms it (the
        # review).
        "data.trust": data_api.trust_period(r["DATA"]),
        "progress": run_api.PROGRESS_WINDOWS,
    }


def _n_params(sysm):
    """RUN.bench_summary's `n_params`: BOTH param groups, never just the base list.

    _base_parameters is the 'base' group alone; SIG's encoder is a second group and summing only
    the first undercounts by the whole encoder -- which is the same shape as the throughput number
    train/api.py::bench_summary records as wrong because it was sourced from the wrong place.
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
