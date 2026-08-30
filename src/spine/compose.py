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
# ==================================================================================================

ASSEMBLY_ORDER = (
    ("process",   "RUN",   "process_setup",   "() -- first, before any tensor: tf32 and autocast "
                                              "are process-wide and a package built before them "
                                              "would be built under different arithmetic"),
    ("process",   "RUN",   "mode",            "() -- decides whether the eval battery runs at all"),
    ("process",   "RUN",   "streams",         "(RNG_SUBSYSTEMS) -- every package's stream is minted "
                                              "here so rng.issued() has one register"),
    ("refuse",    "RUN",   "startup_refusals","(disk_stream=DATA.resample) -- a TWO-PACKAGE guard "
                                              "that can live in neither levers.py"),
    ("refuse",    "WORLD", "startup_refusals","(ctx_tokens=LM.ctx)"),
    ("geometry",  "LM",    "resolve",         "() -- refuses width % heads and the ctx/pos_max "
                                              "overflow BEFORE a tensor is allocated"),
    ("corpus",    "DATA",  "open_areas",      "(seed) -- reads disk; nothing above this touched it"),
    ("vocab",     "TOK",   "build_vocabulary","(area_heads=Areas heads, seed, soft_cap=CAP's start) "
                                              "-- MEASURES bytes/token, which three later rows need"),
    ("plan",      "DATA",  "data_plan",       "(epochs=RUN.epochs, win_tokens=LM.ctx, "
                                              "bytes_per_token=Vocabulary.bytes_per_token) -- the "
                                              "exposure gates, before a single step runs"),
    ("model",     "LM",    "build_model",     "(geom, device, seed)"),
    ("signature", "SIG",   "build",           "(width_units=derive.signature_width_bytes(LM.ctx, "
                                              "bytes_per_token), alphabet_size, device, generator) "
                                              "-- the ONE width, resolved once, here"),
    ("fabric",    "FAB",   "build",           "(d_model=LM.width, signature_dim=SIG.d, device, "
                                              "generator)"),
    ("world",     "WORLD", "build",           "(d_model=LM.width, device, ctx_tokens=LM.ctx, rng)"),
    ("store",     "MEM",   "open_store",      "(key_dim=LM.width, vocab_slots=LM.vocab_slots, "
                                              "device, rng, lm_kind=LM.arch, restored)"),
    ("partition", "DOM",   "open_partition",  "(sig_dim=SIG.d, vocab_slots=LM.vocab_slots, device, "
                                              "rng, restored)"),
    ("valve",     "CAP",   "new_valve",       "(restored) -- both hard ceilings arrive as wires"),
    ("refuse",    "CAP",   "startup_refusals","(live_experts=Population.n_live)"),
    ("optimizer", "OPT",   "build",           "(param_groups={'base': LM+FAB+WORLD+MEM params, "
                                              "'encoder': SIG.encoder_parameters()}, run_windows, "
                                              "resume) -- OPT never walks a module tree"),
    ("clock",     "RUN",   "new_clock",       "(batch_windows=OPT.batch_windows, accum=OPT.accum, "
                                              "resume_step, resume_epoch)"),
    ("cadence",   "RUN",   "new_cadences",    "() -- every period below is an argument"),
    ("retention", "CKPT",  "new_retention",   "(restored=Snapshot.best_state)"),
    ("signal",    "CKPT",  "install_save_signal", "() -- SIGUSR1; not a lever and needs none"),
)

# What the loop does with the assembled system, in the order RUN's clock imposes. NOT EXECUTED HERE
# -- the loop is RUN mechanism. This is the reading order for whoever writes it, and it is data for
# the same reason ASSEMBLY_ORDER is: the contract document and the code must not drift.
#
# A = per WINDOW, above the batch accumulator. B = per FLUSH. Every gate goes through
# Cadences.due(key, period, clock) with a period its OWNING package supplied, so the modulo form
# that fired zero times at every BATCH_W > 1 is not writable at a call site.
LOOP_ORDER = (
    ("A", "EVAL",  "curve_probe",     "Cadences.due('curve', EVAL.curve_period(ev), clock)"),
    ("A", "CKPT",  "Retention.consider", "EVENT-DRIVEN: only when curve_probe returned a value"),
    ("A", "DOM",   "manage",          "Cadences.due('dom.manage', DOM.manage_every, clock); the "
                                      "Plan it returns goes to MEM.apply_domain_plan"),
    ("A", "FAB",   "manage",          "Cadences.due('fab.manage', FAB.manage_every, clock)"),
    ("A", "WORLD", "manage",          "the SAME Windows cadence, NEVER FAB.d_manage_period, which "
                                      "is Flushes -- a 16x error at BATCH_W=16"),
    ("A", "SIG",   "encode",          "one signature per window, at st.width_units, always"),
    ("A", "DOM",   "observe",         "once per window, above the early-out: `sustain` is Windows"),
    ("A", "TOK",   "on_window",       "the ONE place TOK's four cadences are asked, once each"),
    ("A", "RUN",   "RunClock.advance","appends to the accumulator; if not full, continue"),
    ("B", "LM",    "encode/decode/lm_loss", "extra=WORLD.forecast(...) when feedback is on"),
    ("B", "FAB",   "forward",         "head=LM.decode as a plain callable -- not an import"),
    ("B", "WORLD", "loss_terms",      "obs_emb = LM's embedding of the batch"),
    ("B", "LM",    "anchor_term",     "token_seen: the loop's per-token appearance counter"),
    ("B", "OPT",   "scaled_backward", "scaling and counting in ONE function, never 128 lines apart"),
    ("B", "RUN",   "RunClock.note_backward", "derive.accum_due on a Backwards clock"),
    ("B", "OPT",   "maybe_step",      "best_bpb from EVAL (with its seed count), shift_at from the "
                                      "root; returns StepOutcome.lr as a RETURN VALUE"),
    ("B", "FAB",   "own_lr_scale",    "applied_lr=StepOutcome.lr; the two endpoints are wires"),
    ("B", "CAP",   "observe",         "elapsed_windows from RunClock, seeded at the RESUMED step"),
    ("B", "CAP",   "caps",            "-> FAB.grow_check(soft_cap=...) and TOK.lift_vocab_cap(to=...)"),
    ("B", "FAB",   "observe/grow_check/contribution", "per_window_loss from LM.lm_loss"),
    ("B", "MEM",   "write/maintain",  "key_fn=LM.encode; positions are TRUE BYTE OFFSETS"),
    ("B", "TOK",   "mint_burst",      "-> LM.on_mint(sig_emb=SIG.encoder_embedding(...)) and, if "
                                      "Due.retok, TOK.tokenize -> a RetokEvent the root distributes "
                                      "to SIG, MEM (resegment), DOM (on_retokenize) and FAB"),
    ("B", "DOM",   "note_competence", "bits from the per-window loss; the rate is the d_comp_ema wire"),
    ("B", "CKPT",  "save",            "Cadences.due('ckpt', CKPT.save_period(ck), clock), or SIGUSR1"),
)


class System:
    """Everything the loop needs, assembled. A plain record; it holds no logic and no levers.

    Attributes are set by compose() as each stage completes, so a NotImplementedError from a stub
    leaves a PARTIALLY BUILT System naming exactly how far the assembly got -- which is the
    difference between "P4 has not landed" and "the composition root is wrong".
    """

    __slots__ = ("configs", "wires", "warnings", "process", "mode", "streams", "refusals",
                 "geometry", "areas", "vocab", "plan", "model", "sig", "fabric", "world",
                 "store", "partition", "valve", "optimizer", "clock", "cadences", "retention",
                 "save_flag", "snapshot", "stage")

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
    """
    return ASSEMBLY_ORDER, LOOP_ORDER


def compose(environ=None, *, restored=None):
    """Resolve every Config, then build every object, handing each package what it needs.

    Returns a System. Raises NotImplementedError from the first unimplemented stub, with
    System.stage on the partially built record naming how far it got -- so the failure says which
    package owes what rather than "something is missing".

    `environ` is passed straight to spine.assemble.build. Pass the process environment: build()
    warns when it is None because the typo net then has nothing to scan, and this file may not name
    os.environ (check O1). `restored` is a CKPT Snapshot or None.

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

    # -- 2. refusals that need two packages' numbers ---------------------------------------------
    # RUN's EPOCHS>1 guard needs DATA's resample flag; WORLD's horizon ceiling needs LM's ctx.
    # Neither can live in a levers.py, and both must fire BEFORE anything is allocated.
    sysm.stage = "refuse"
    sysm.refusals = list(run_api.startup_refusals(run, disk_stream=bool(data.resample)))
    sysm.refusals += list(world_api.startup_refusals(world, ctx_tokens=int(lm.ctx)))

    # -- 3. geometry, then the corpus -------------------------------------------------------------
    sysm.stage = "geometry"
    sysm.geometry = lm_api.resolve(lm)

    sysm.stage = "corpus"
    sysm.areas = data_api.open_areas(data, seed=int(run.seed))

    # -- 4. the vocabulary, which MEASURES bytes/token --------------------------------------------
    # Ordered here and not earlier because build_vocabulary needs the corpus, and ordered before
    # DATA.data_plan and SIG.build because both need the measurement. derive.bytes_per_token is the
    # only estimator in the tree; the mean-over-vocabulary-entries form it replaces had an error
    # that changes SIGN with vocabulary size, and the signature width 614 was chosen off it.
    sysm.stage = "vocab"
    sysm.vocab = tok_api.build_vocabulary(
        tok, area_heads=sysm.areas.bodies, seed=int(run.seed), soft_cap=None)

    sysm.stage = "plan"
    sysm.plan = data_api.data_plan(
        data, sysm.areas, epochs=int(run.epochs), win_tokens=int(lm.ctx),
        bytes_per_token=float(sysm.vocab.bytes_per_token))

    # -- 5. the model, the signature space, and the two populations -------------------------------
    sysm.stage = "model"
    sysm.model = lm_api.build_model(
        lm, sysm.geometry, device=sysm.process.device, seed=int(run.seed))

    sysm.stage = "signature"
    sysm.sig = sig_api.build(
        sig, width_units=_signature_width(lm, sysm.vocab), alphabet_size=_alphabet_size(sig, lm),
        device=sysm.process.device, generator=sysm.streams["sig"])

    sysm.stage = "fabric"
    sysm.fabric = fab_api.build(
        fab, d_model=int(lm.width), signature_dim=int(sig.d),
        device=sysm.process.device, generator=sysm.streams["fabric"])

    sysm.stage = "world"
    sysm.world = world_api.build(
        world, d_model=int(lm.width), device=sysm.process.device,
        ctx_tokens=int(lm.ctx), rng=sysm.streams.get("world"))

    sysm.stage = "store"
    sysm.store = mem_api.open_store(
        mem, key_dim=int(lm.width), vocab_slots=int(lm.vocab_slots),
        device=sysm.process.device, rng=sysm.streams["memory"], lm_kind=lm.arch,
        restored=None if restored is None else restored.payload.get("MEM"))

    sysm.stage = "partition"
    sysm.partition = dom_api.open_partition(
        dom, sig_dim=int(sig.d), vocab_slots=int(lm.vocab_slots), device=sysm.process.device,
        rng=sysm.streams["domains"],
        restored=None if restored is None else restored.payload.get("DOM"))

    # -- 6. the capacity valve, and the refusal that needs the population -------------------------
    sysm.stage = "valve"
    sysm.valve = cap_api.new_valve(
        cap, restored=None if restored is None else restored.payload.get("CAP"))
    sysm.refusals += list(cap_api.startup_refusals(
        cap, sysm.valve, live_experts=sysm.fabric.n_live))

    # -- 7. the optimizer. OPT NEVER WALKS A MODULE TREE ------------------------------------------
    # The old tree assembled `_base` by reaching into six modules at :4700-4707. Here every package
    # that has parameters hands over a plain list and the root concatenates them, so a package
    # cannot be silently left out of the optimizer by an ablation flag about something else.
    sysm.stage = "optimizer"
    sysm.optimizer = opt_api.build(
        opt,
        param_groups={"base": _base_parameters(sysm),
                      "encoder": list(sig_api.encoder_parameters(sig, sysm.sig))},
        run_windows=_run_windows(sysm),
        resume=None if restored is None else restored.payload.get("OPT"))

    # -- 8. the clocks, the cadence ledger, the retention policy and the save signal ---------------
    sysm.stage = "clock"
    sysm.clock = run_api.new_clock(
        run, batch_windows=int(opt.batch_windows), accum=int(opt.accum),
        resume_step=0 if restored is None else restored.step,
        resume_epoch=0 if restored is None else restored.epoch)
    sysm.cadences = run_api.new_cadences(run)

    sysm.stage = "retention"
    sysm.retention = ckpt_api.new_retention(
        ckpt, restored=None if restored is None else restored.best_state)
    sysm.save_flag = ckpt_api.install_save_signal()
    sysm.snapshot = restored

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
    """
    plan = sysm.plan
    return int(plan.run_windows) * int(sysm.configs["RUN"].epochs)
