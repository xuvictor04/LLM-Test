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
orphans go to be forgotten.

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
RNG_SUBSYSTEMS = ("lm", "sig", "fabric", "memory", "domains", "tok.dropout",
                  "data.synth", "data.holdout", "eval")


# ==================================================================================================
# THE ORDER, AS DATA
#
# Every row is (stage, PREFIX, entry point, what it receives that is not its own Config). It is a
# table rather than a comment so that docs/04_CONTRACT.md and tests/test_contract.py read the SAME
# statement the code executes -- the old tree's report path and audit path printing different
# numbers for one quantity is the failure that rule exists to end.
#
# ORDER IS LOAD-BEARING HERE, unlike in assemble.COUPLINGS. A Config can be resolved in any order
# because no coupling reads another coupling's output; an OBJECT graph cannot, because the
# tokenizer must have measured bytes/token before SIG can be given its width, and DATA cannot be
# planned before that measurement exists. Each row below names what forces its position.
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
#   2. tests/test_contract.py:879 reads the tables BY NAME -- it walks the assignments whose target
#      id is "ASSEMBLY_ORDER" or "LOOP_ORDER" and nothing else. A third table would be invisible to
#      the one check that exists because these rows were missing, so its rows would still report as
#      orphans. A level with a table of its own that no check can see is still an orphan.
# ==================================================================================================

ASSEMBLY_ORDER = (
    ("process",   "RUN",   "process_setup",   "() -- first, before any tensor: tf32 and autocast "
                                              "are process-wide and a package built before them "
                                              "would be built under different arithmetic"),
    ("process",   "RUN",   "mode",            "() -- decides whether the eval battery runs at all"),
    ("process",   "RUN",   "streams",         "(RNG_SUBSYSTEMS) -- every package's stream is minted "
                                              "here so rng.issued() has one register"),

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
                                              "live inside this package even if O10 allowed it"),

    ("refuse",    "RUN",   "startup_refusals","(disk_stream=DATA.resample) -- a TWO-PACKAGE guard "
                                              "that can live in neither levers.py"),
    ("refuse",    "WORLD", "startup_refusals","(ctx_tokens=LM.ctx)"),
    ("geometry",  "LM",    "resolve",         "() -- refuses width % heads and the ctx/pos_max "
                                              "overflow BEFORE a tensor is allocated"),
    ("corpus",    "DATA",  "open_areas",      "(seed) -- reads disk; nothing above this touched it"),
    ("restore",   "DATA",  "restore_stream_state", "(areas, Snapshot.payload['DATA']) -- AFTER "
                                              "open_areas because it refuses on the holdout offsets "
                                              "open_areas just produced, and BEFORE data_plan so "
                                              "the plan is computed against the restored split"),
    ("vocab",     "TOK",   "build_vocabulary","(area_heads=Areas heads, seed, soft_cap=CAP's start) "
                                              "-- MEASURES bytes/token, which three later rows need"),
    ("restore",   "TOK",   "restore_vocab",   "(Snapshot.payload['TOK'], vocab) -- AFTER "
                                              "build_vocabulary has replayed the parent's merges "
                                              "from d_vocab_read_path: the refusal it owns compares "
                                              "the state's merge count against the vocabulary that "
                                              "was just built, so it has nothing to compare before"),
    ("gate",      "CKPT",  "check_geometry",  "(Snapshot, manifest) -- THE LAST ROW BEFORE ANY "
                                              "PARAMETER EXISTS. build_model below is the first "
                                              "allocation, and the old gate at :4413-4468 fired "
                                              "only after the tokenizer had resolved and the corpus "
                                              "had been pulled. The manifest is assembled by "
                                              "_geometry_manifest() from LM.resolve's LMGeometry and "
                                              "the EXACT fields readable off the frozen Configs; the "
                                              "GROWN population counts cannot be in it (they need a "
                                              "built object) and are reported UNCHECKED, then "
                                              "re-refused by WORLD.load_into and FAB.load_state_dict"),
    ("plan",      "DATA",  "data_plan",       "(epochs=RUN.epochs, win_tokens=LM.ctx, "
                                              "bytes_per_token=Vocabulary.bytes_per_token) -- the "
                                              "exposure gates, before a single step runs"),
    ("stream",    "DATA",  "draw_stream",     "(areas, plan, epoch=0, seed=RUN.seed) -- EPOCH 0's "
                                              "draw, and it is here rather than only at stage E "
                                              "because two rows below need the material: OPT.build "
                                              "needs run_windows MEASURED from the segmentation "
                                              "(opt/api.py:78) and SIG.warm_up takes the stream. The "
                                              "old tree has the same duplication -- :4104 and :6513 "
                                              "both call _resample()"),
    ("segment",   "TOK",   "tokenize",        "(vocab, Stream.bytes, Stream.labels, "
                                              "regularize=True, seed) -- the epoch-0 segmentation. "
                                              "It is the ONLY producer of a window count: "
                                              "len(Segmentation.ids) // LM.ctx, never "
                                              "stream_bytes // ctx, which divides a BYTE budget by a "
                                              "TOKEN window and overstates it by the compression "
                                              "ratio"),
    ("model",     "LM",    "build_model",     "(geom, device, seed)"),
    ("restore",   "LM",    "load_state",      "(model, geom, Snapshot.payload['LM']) -> LoadReport"),
    ("signature", "SIG",   "build",           "(width_units=derive.signature_width_bytes(LM.ctx, "
                                              "bytes_per_token), alphabet_size, device, generator) "
                                              "-- the ONE width, resolved once, here"),
    ("restore",   "SIG",   "load_state_dict", "(st, Snapshot.payload['SIG'], sidecar=Snapshot's "
                                              "recorded width_units/alphabet_size/space/d/mode)"),
    ("fabric",    "FAB",   "build",           "(d_model=LM.width, signature_dim=SIG.d, device, "
                                              "generator)"),
    ("restore",   "FAB",   "load_state_dict", "(pop, Snapshot.payload['FAB'], sidecar=recorded "
                                              "slots/rank/dk) -- slots MAY_WIDEN, rank and dk EXACT"),
    ("world",     "WORLD", "build",           "(d_model=LM.width, device, ctx_tokens=LM.ctx, rng)"),
    ("restore",   "WORLD", "load_into",       "(w, Snapshot.payload['WORLD']) -- STRICTLY BEFORE "
                                              "OPT.build. WORLD.manage mints parameters mid-run "
                                              "through add_param_group, so a checkpoint taken after "
                                              "growth has more groups than a freshly built "
                                              "optimizer; replaying the population first is what "
                                              "lets OPT be built with the SAME group structure, and "
                                              "without it OPT's param_group_shape refusal fires on "
                                              "every resume of a run that ever grew (:4580-4599)"),
    ("store",     "MEM",   "open_store",      "(key_dim=LM.width, vocab_slots=LM.vocab_slots, "
                                              "device, rng, lm_kind=LM.arch, restored)"),
    ("partition", "DOM",   "open_partition",  "(sig_dim=SIG.d, vocab_slots=LM.vocab_slots, device, "
                                              "rng, restored)"),
    ("valve",     "CAP",   "new_valve",       "(restored) -- both hard ceilings arrive as wires"),
    ("restore",   "CAP",   "restore",         "(valve, Snapshot.payload['CAP']) -- new_valve's "
                                              "`restored` is the LIFTED CAP ALONE, because "
                                              "Valve.origin has to record where the STARTING cap "
                                              "came from; this row puts back what that one argument "
                                              "cannot carry -- the two pin clocks and the high-water "
                                              "marks, which is the other half of M38 -- and it "
                                              "precedes the refusal below so the refusal is taken "
                                              "against the restored ceiling"),
    ("refuse",    "CAP",   "startup_refusals","(live_experts=Population.n_live)"),
    ("optimizer", "OPT",   "build",           "(param_groups={'base': LM+FAB+WORLD+MEM params, "
                                              "'encoder': SIG.encoder_parameters()}, run_windows, "
                                              "resume) -- OPT never walks a module tree"),
    ("restore",   "OPT",   "load_state",      "(st, Snapshot.payload['OPT']) -- AFTER build because "
                                              "the param_group_shape refusal (ISSUES L50) compares "
                                              "the saved shape against the LIVE groups, which do not "
                                              "exist until build returns. It is the entry point that "
                                              "carries opt.ckpt.loaded/refused; build's undocumented "
                                              "`resume` parameter overlaps it -- see Q-OPT-4"),
    ("clock",     "RUN",   "new_clock",       "(batch_windows=OPT.batch_windows, accum=OPT.accum, "
                                              "resume_step, resume_epoch)"),
    ("epoch0",    "RUN",   "RunClock.begin_epoch", "(windows_in_epoch=len(Segmentation.ids)//LM.ctx) "
                                              "-- epoch 0's length, MEASURED on the stream that "
                                              "actually exists. It is here and not only at stage E "
                                              "because the first epoch is never rolled into, and it "
                                              "needs the clock the row above builds"),
    ("warmup",    "SIG",   "warm_up",         "(stream=the epoch-0 unit stream in SIG's alphabet, "
                                              "seen_units=the WHOLE stream, opt=OPT's ENCODER "
                                              "optimizer) -- pre-loop by definition (sig/api.py:143) "
                                              "and therefore after BOTH the stream rows and the "
                                              "optimizer row; its budget is units.Steps on its own "
                                              "local counter and is never compared to a Windows "
                                              "cadence. Its verdict 'collapsing' is a RUN-LEVEL "
                                              "FAILURE, not a warning. OptState is declared as "
                                              "'both AdamW instances' and NAMES NEITHER, so what is "
                                              "handed over today is the OptState -- Q-OPT-7"),
    ("cadence",   "RUN",   "new_cadences",    "() -- every period below is an argument"),
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
LOOP_ORDER = (
    ("E", "DATA",  "draw_stream",     "(areas, plan, epoch=clock.epoch, seed=RUN.seed) -- THE FIRST "
                                      "STATEMENT OF EVERY EPOCH, called UNCONDITIONALLY: dat.resample "
                                      "is read INSIDE (data/api.py:128), so 'every epoch is a "
                                      "byte-identical replay' is a state this package REPORTS rather "
                                      "than a branch the caller takes. The root also stamps "
                                      "clock.opt_steps here as the shift_at that OPT.maybe_step's B "
                                      "row consumes -- a resample is a SELF-INFLICTED shift and the "
                                      "old tree carried that fact in a closure variable (:6518-6521)"),
    ("E", "TOK",   "tokenize",        "(vocab, Stream.bytes, Stream.labels, regularize=True) -- "
                                      "between the draw and begin_epoch, because the window count "
                                      "the next row needs is len(Segmentation.ids)//LM.ctx and that "
                                      "cannot be known until this call returns"),
    ("E", "RUN",   "RunClock.begin_epoch", "(windows_in_epoch=len(Segmentation.ids)//LM.ctx) -- a "
                                      "MEASUREMENT, re-taken every epoch because a resampling stream "
                                      "is a different length each time and minting shortens every "
                                      "later one. THE LENGTH ARRIVES AS A COUNT OF WINDOWS. The "
                                      "partial batch was already dropped by the advance that rolled"),
    ("A", "EVAL",  "curve_probe",     "Cadences.due('curve', EVAL.curve_period(ev), clock)"),
    ("A", "CKPT",  "Retention.consider", "EVENT-DRIVEN: only when curve_probe returned a value. Its "
                                      "BestAction(save_best, rotate_slot) is the A-level route into "
                                      "the C block, with reason='best'/'bestN' and the matching "
                                      "suffix -- without it Saves.best can never be non-zero and the "
                                      "only copies of the good model are never written"),
    ("A", "MEM",   "census",          "THE MANAGEMENT PASS OPENS HERE. Cadences.due('dom.manage', "
                                      "DOM.manage_every, clock) is asked ONCE and the next three "
                                      "rows run inside that one answer: due() RECORDS the fire and "
                                      "returns True, so asking a second time under the same key "
                                      "CONSUMES the event -- the defect that made minting never "
                                      "fire when probation shared its key. reconcile=True, and it "
                                      "is before DOM.manage because manage's memory_counts and "
                                      "mem_floor_entries are REQUIRED arguments with no other "
                                      "producer -- a hole in a row that already existed"),
    ("A", "DOM",   "manage",          "inside that one pass, not a second Cadences.due; the Plan it "
                                      "returns is handed straight on as "
                                      "MEM.apply_domain_plan(plan=Plan, live_sources=DOM.census's "
                                      "`live`) -- written as the CALL it is, because K6 credits a "
                                      "note only when it names arguments"),
    ("A", "DOM",   "census",          "the SAME management pass, IMMEDIATELY AFTER manage: its "
                                      "`live` list is what MEM.apply_domain_plan takes as "
                                      "live_sources, which replaces the attribute reach at :6699"),
    ("A", "MEM",   "judge",           "EVENT-DRIVEN on that same management pass, after the plan is "
                                      "applied -- 'the management cadence the spine already imposes; "
                                      "no new lever' (memory/api.py:253). It rides the dom.manage "
                                      "gate as an event and invents no key, so the detector is "
                                      "CADENCED rather than run once from the report over a store "
                                      "whose every write had reset selfcon to -1. Which management "
                                      "pass is the owner's call: Q-MEM-8"),
    ("A", "FAB",   "manage",          "Cadences.due('fab.manage', FAB.manage_every, clock)"),
    ("A", "WORLD", "manage",          "the SAME Windows cadence, NEVER FAB.d_manage_period, which "
                                      "is Flushes -- a 16x error at BATCH_W=16"),
    ("A", "SIG",   "cadence_due",     "SIG's OWN two-arm shift gate, not Cadences.due: it selects "
                                      "between train_every and train_every_idle on dense_window, "
                                      "and Cadences.due takes ONE period. All three are Windows and "
                                      "the clock is Windows. windows_since_boundary is "
                                      "clock.step - the last boundary DOM.observe reported; SIG does "
                                      "not reach for it. Because it cannot go through the ledger, "
                                      "SIG.counters at stage R is its ONLY did-it-fire surface"),
    ("A", "SIG",   "train_step",      "EVENT-DRIVEN on cadence_due, and BEFORE encode -- the old "
                                      "order is :6649 then :6651, and it is what makes the lookahead "
                                      "sound: the batching interval is the span over which the "
                                      "encoder is provably frozen. opt is OPT's ENCODER optimizer, "
                                      "handed in; SIG never names a learning rate. WITHOUT THIS ROW "
                                      "the run routes every window through a randomly initialised "
                                      "encoder while an AdamW steps it on zero gradients"),
    ("A", "SIG",   "encode",          "one signature per window, at st.width_units, always"),
    ("A", "DOM",   "observe",         "once per window, above the early-out: `sustain` is Windows"),
    ("A", "DOM",   "rekey",           "Cadences.due('dom.rekey', MEM.rekey_every, clock) -- the "
                                      "period is MEM's and the arm test is SIG.mode == 'learned', so "
                                      "BOTH are evaluated HERE and delivered as an event; the old "
                                      "line made two foreign reads at :6688-6689. AFTER observe, so "
                                      "the window that just triggered a boundary is inside the "
                                      "sample its own radius is measured from. It is the ONLY site "
                                      "that measures a radius, and DOM.accept_rule defaults to "
                                      "'radius' -- without it every domain runs on the bootstrap "
                                      "forever and n_bootstrap_radius is 100% by construction"),
    ("A", "TOK",   "on_window",       "the ONE place TOK's four cadences are asked, once each"),
    ("A", "RUN",   "RunClock.advance","appends to the accumulator; if not full, continue. Tick.rolled "
                                      "re-enters the E rows; Tick.finished leaves for R"),
    ("B", "LM",    "encode/decode/lm_loss", "extra=WORLD.forecast(...) when feedback is on"),
    ("B", "FAB",   "forward",         "head=LM.decode as a plain callable -- not an import"),
    ("B", "WORLD", "loss_terms",      "obs_emb = LM's embedding of the batch"),
    ("B", "LM",    "anchor_term",     "token_seen: the loop's per-token appearance counter"),
    ("B", "OPT",   "scaled_backward", "scaling and counting in ONE function, never 128 lines apart"),
    ("B", "RUN",   "RunClock.note_backward", "derive.accum_due on a Backwards clock"),
    ("B", "OPT",   "maybe_step",      "best_bpb from EVAL (with its seed count), shift_at from the "
                                      "root; returns StepOutcome.lr as a RETURN VALUE. Its step 2 IS "
                                      "OPT.lr_at(st, st.opt_step) -- the schedule is PURE and is "
                                      "read from inside this one function, which is why it has no "
                                      "row of its own"),
    ("B", "FAB",   "own_lr_scale",    "applied_lr=StepOutcome.lr; the two endpoints are wires"),
    ("B", "CAP",   "observe",         "elapsed_windows from RunClock, seeded at the RESUMED step"),
    ("B", "CAP",   "caps",            "-> FAB.grow_check(soft_cap=...) and TOK.lift_vocab_cap(to=...)"),
    ("B", "FAB",   "observe/grow_check/contribution", "per_window_loss from LM.lm_loss"),
    ("B", "MEM",   "write/maintain",  "key_fn=LM.encode; positions are TRUE BYTE OFFSETS. maintain's "
                                      "job 1 is MEM.read(promote=True) on the probe_every cadence -- "
                                      "the retrieval that moves use/last/prob, without which "
                                      "evict='lru' and evict='usage' are write-order FIFO whatever "
                                      "they say and probation can never promote. That it is this "
                                      "package's own read rather than a second retrieval is the "
                                      "reading Q-MEM-9 asks the owner to confirm"),
    ("B", "TOK",   "mint_burst",      "-> LM.on_mint(sig_emb=SIG.encoder_embedding(...)) and, if "
                                      "Due.retok, TOK.tokenize -> a RetokEvent the root distributes "
                                      "to SIG, MEM (resegment), DOM.on_retokenize(event=RetokEvent) "
                                      "and FAB -- the DOM leg written as a call for the reason above"),
    ("B", "TOK",   "judge_probation", "EVENT-DRIVEN on Due.probation, which TOK.on_window already "
                                      "asked at A under its OWN cadence key -- asking again here "
                                      "would CONSUME the event, which is how a shared key made "
                                      "minting never fire. It is at B and not A because two of its "
                                      "three inputs are flush-side: `appearances` is the per-token "
                                      "counter this flush's batch just updated, and residual_ratio "
                                      "is read off live model tensors. Its Judgement.retired feeds "
                                      "LM.decode(retired_ids=...)"),
    ("B", "DOM",   "note_competence", "bits from the per-window loss; the rate is the d_comp_ema wire"),
    ("B", "CKPT",  "save",            "Cadences.due('ckpt', CKPT.save_period(ck), clock), or the "
                                      "SIGUSR1 flag -- the B-level route INTO the C block, with "
                                      "reason='periodic' or 'sigusr1'"),

    # -- C: the checkpoint fan-out. The payload rows are in EXACTLY the order ASSEMBLY_ORDER built
    # the objects -- DATA, TOK, LM, SIG, FAB, WORLD, MEM, DOM, CAP, OPT -- so a reader comparing the
    # save against the build reads one sequence and not two, and a package that has been added to
    # one and not the other is visible by inspection.
    ("C", "DATA",  "stream_state",    "(areas) -> payload['DATA'] -- the per-area cursors, without "
                                      "which a resume re-reads the head of every area under "
                                      "seg_contig and trains a second time on the parent's material"),
    ("C", "TOK",   "vocab_state",     "(vocab) -> payload['TOK'] -- retirements and probation, which "
                                      "a save/load round trip currently UNDOES (D-T3)"),
    ("C", "LM",    "state_dict",      "(model, geom) -> payload['LM']"),
    ("C", "SIG",   "state_dict",      "(st) -> payload['SIG'], and the sidecar the restore row "
                                      "above compares against"),
    ("C", "FAB",   "state_dict",      "(pop) -> payload['FAB'] -- `cent` is a BUFFER for this "
                                      "reason: as a plain attribute it was absent from state_dict "
                                      "and the centroids that ARE the routing function were never "
                                      "saved"),
    ("C", "WORLD", "state_dict",      "(w) -> payload['WORLD'], carrying the loop-side plateau EMA"),
    ("C", "WORLD", "geometry",        "(w) -> the manifest RECORDED INTO the snapshot, which is what "
                                      "the child's check_geometry compares against. It is on the "
                                      "SAVE side and not beside that gate because it needs the "
                                      "GROWN population, and the gate must fire before anything is "
                                      "built. It is the only geometry() in the tree -- see Q-CKPT-1"),
    ("C", "MEM",   "state_dict",      "(store) -> payload['MEM'] -- including prob, recon, nsrc_max "
                                      "and gate_theta, four omissions that each disarmed a live "
                                      "mechanism at the run boundary"),
    ("C", "DOM",   "state_dict",      "(part) -> payload['DOM'] -- including the RESERVOIRS, which "
                                      "are the uncensored sample the measured radius needs"),
    ("C", "CAP",   "state",           "(valve) -> payload['CAP'] -- the lifted caps AND the pin "
                                      "clocks: saving the ceiling without the clock is M38"),
    ("C", "OPT",   "state_dict",      "(st) -> payload['OPT'] -- both optimizers AND lr_prev, "
                                      "restart_amp, cycle_index and the horizon"),
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
    ("R", "MEM",   "read",            "(queries, promote=False) -- the read that MUST NOT MOVE THE "
                                      "STORE, because an instrument that mutates use/prob/last is "
                                      "editing what it measures (L49). NOT in the flush body: the "
                                      "four blend sites in the old tree are all report-side, and "
                                      "moving retrieval into the training distribution is a "
                                      "behaviour change nobody has measured"),
    ("R", "MEM",   "blend",           "(model_probs, retrieval) -- at the weight `read` ALREADY "
                                      "computed, never recomputed here; that recomputation is the "
                                      "ungated 50/50 mix still live in prompt.py. model_probs are "
                                      "PROBABILITIES while every scoring hook in the tree takes a "
                                      "logits_fn, and the join between them is Q-MEM-10"),
    ("R", "DOM",   "prior",           "(did) -- the per-domain token prior AND its weight, together. "
                                      "The old read site is the report (:8147-8192) while the "
                                      "accumulation is per window, and the accumulated/read PAIR is "
                                      "the whole finding that the histogram was paid for every "
                                      "window and never read"),
    ("R", "MEM",   "census",          "(reconcile=True) -- the store's did-it-fire surface, re-taken "
                                      "at the end so the report's numbers are the settled ones"),
    ("R", "DOM",   "census",          "() -- the partition's did-it-fire surface, and the domain "
                                      "sizes every verdict is keyed by"),
    ("R", "LM",    "counters",        "(model)"),
    ("R", "SIG",   "counters",        "(st) -- the ONLY place the encoder's cadence is visible, "
                                      "because its gate cannot go through Cadences.ledger"),
    ("R", "FAB",   "counters",        "(pop)"),
    ("R", "OPT",   "counters",        "(st) -- it ASSERTS backward // accum == step, which is the "
                                      "only thing that proves ISSUES H29 is dead"),
    ("R", "CAP",   "counters",        "(valve) -- including the BLOCK-REASON histogram, without "
                                      "which '0 lifts' cannot say which condition refused"),
    ("R", "RUN",   "RunClock.counters", "() -- the five typed counters; flushes == 0 with step > 0 "
                                      "means the batch never filled"),
    ("R", "RUN",   "Cadences.ledger", "() -> {key: (checks, fires, last_fired_step, period)}. A key "
                                      "with checks > 0 and fires == 0 is armed-but-inert WITH ITS "
                                      "ARITHMETIC; a key that is absent was never asked"),
    ("R", "CKPT",  "Retention.counters", "() -- probes_seen, new_bests, rotations, slots_used and "
                                      "inert_reason, which is the one surface that can say 'no curve "
                                      "value has ever arrived' instead of 'zero local lows'"),
    ("R", "RUN",   "bench_summary",   "(clock, elapsed_s, bytes_per_window=LM.ctx x "
                                      "Segmentation.bytes_per_token FROM THE LAST TOK.tokenize, "
                                      "n_params, timing) -- printed INSTEAD of the battery when "
                                      "RUN.mode says bench. The live bytes/window is the L42 repair: "
                                      "the old number was initialised at the SEED vocabulary and "
                                      "refreshed only inside an instrument's tick"),
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
# ONLY EVAL IS IN IT, and only the seven instruments eval/api.py:12-19 itself assigns to a later
# phase. Note that the phases are NOT all P6, which a summary of this table got wrong: the file says
# curve_probe / holdout_probe / null_excess are P5 and the five instruments at the bottom are P6.
# curve_probe is already reached by a LOOP_ORDER row, so a later phase is plainly not by itself a
# reason to defer; the reason is recorded per entry below and is about the ARGUMENTS, which have no
# producer among the 117 entry points yet.
DEFERRED_ENTRY_POINTS = {
    "EVAL.holdout_probe":
        "P5 (eval). The R matrix -- goal B's only cross-boundary number -- and the row that calls "
        "it belongs at stage R and at every save site. It is deferred rather than rowed because it "
        "needs units_by_domain drawn in BYTE coordinates from Areas.holdout together with a "
        "logits_fn, and the root has no join that produces that pair; writing a row now would name "
        "a call whose arguments nothing supplies. P5 lands the pair and the row together.",
    "EVAL.null_excess":
        "P5 (eval). The permutation null every 2-sigma verdict is judged against; its `real` and "
        "`permute` arguments are produced by the verdict machinery, which is P6's.",
    "EVAL.generate":
        "P6 (eval). The generation battery. `prompts_by_domain` has no producer among the 117 "
        "entry points: DOM.census returns domain sizes and radii, not prompts.",
    "EVAL.coherence":
        "P6 (eval). Runs on its OWN seeded Sample, which the P6 report assembler draws; no entry "
        "point in the tree returns a Sample today.",
    "EVAL.verdicts":
        "P6 (eval). Three of its four arguments -- silhouettes, affiliation, coherence_reading -- "
        "have no producer in the tree; the fourth, domain_sizes, comes from DOM.census, which the "
        "R stage above already collects.",
    "EVAL.wrongness_probe":
        "P6 (eval). Takes a COPY of the store so the instrument cannot edit what it measures; "
        "nothing in MEM's surface produces a copy, and inventing one is a signature change.",
    "EVAL.verification_fit":
        "P6 (eval). Post hoc, on a store copy, with an inner loop in genuine units.Steps that must "
        "never be compared against curve_every -- same missing copy, same phase.",
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
                 "resume_src", "manifest", "saving", "stream", "segmentation")

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
                                sidecar=_sidecar(restored, "SIG"))

    sysm.stage = "fabric"
    sysm.fabric = fab_api.build(
        fab, d_model=int(lm.width), signature_dim=int(sig.d),
        device=sysm.process.device, generator=sysm.streams["fabric"])
    if "FAB" in saved:
        sysm.stage = "restore.fab"
        fab_api.load_state_dict(fab, sysm.fabric, saved["FAB"],
                                sidecar=_sidecar(restored, "FAB"))

    sysm.stage = "world"
    sysm.world = world_api.build(
        world, d_model=int(lm.width), device=sysm.process.device,
        ctx_tokens=int(lm.ctx), rng=sysm.streams.get("world"))
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
    sysm.optimizer = opt_api.build(
        opt,
        param_groups={"base": _base_parameters(sysm),
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

    sysm.stage = "cadence"
    sysm.cadences = run_api.new_cadences(run)

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
    WORLD.manage as a callable for exactly that reason.
    """
    out = []
    for obj in (sysm.model, sysm.fabric, sysm.world):
        params = getattr(obj, "parameters", None)
        if callable(params):
            out.extend(params())
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
    """
    return _windows_in_epoch(sysm) * int(sysm.configs["RUN"].epochs)


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


def _sidecar(restored, prefix):
    """The recorded geometry fields SIG and FAB compare their own state against on a restore.

    They take theirs as a `sidecar` argument rather than through the manifest above because their
    refusals run AFTER their build -- which is exactly why the manifest reports the grown counts as
    UNCHECKED rather than pretending to have checked them.
    """
    if restored is None:
        return None
    recorded = getattr(restored, "geometry", None) or {}
    return recorded.get(prefix)


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
