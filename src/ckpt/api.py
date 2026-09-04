"""CKPT -- the frozen public surface. Signatures only; P4 writes the bodies.

CKPT owns the run's persistent state, and in this system A RESUME IS NOT A CONVENIENCE, IT IS THE
EXPERIMENT: self_organize.py:3232 says outright that "RESUME is how continual learning is supposed
to work here", and every forgetting number in the project is a measurement ACROSS a resume
boundary. So CKPT serves goal B directly -- `dir` and `resume` decide whether the boundary exists,
`every` decides whether a multi-day run survives to reach one. It serves goal A through
best_keep/best_keep_tol: the model the report generates from is the LIVE model at the end of
training, which in every arm so far was 1.1-1.3 b/B worse than the model around step 6000, so the
.best snapshots are the only copies of the good model that exist.

THIS PACKAGE DOES NOT KNOW WHAT A FABRIC OR A MEMORY STORE IS. `payload` is an opaque mapping the
composition root assembles from every package's own state_dict; `geometry` is a manifest of
(value, rule, env_name, why) records each package produced. CKPT compares recorded against live and
prints the arithmetic; it never learns what a "rank" is.

RECORD TYPES RETURNED (P4 defines them):
  Snapshot         payload, geometry, step, epoch, best_state, resume
  GeometryField    value, rule (EXACT | MAY_WIDEN | MAY_NARROW), env_name, why
  GeometryReport   checked, unchecked, refused, both values per field
  Saves            periodic, sigusr1, best, best_keep_by_slot, final, refused_off
  Resume           attempted, loaded, step_restored, epoch_restored, best_restored
  Retention        the best-model policy object; BestAction(save_best, rotate_slot)
"""
import dataclasses
import os

import torch

from spine.lever import Config
from spine.gate import Gate
from spine import units as U


# ==================================================================================================
# THE RECORDS THIS PACKAGE RETURNS
# ==================================================================================================

# THE SIX SPELLINGS OF OFF, IN ONE PLACE. The old tree normalised these at :5329, hundreds of lines
# BELOW the first consumer at :1010, so the tokenizer save path was computed from the raw string and
# would have named a file "0.dyntok.json"; a second copy of the same test at :1010 existed to work
# around that. Before the normalisation existed at all, `if not ck: return` never fired for "0",
# os.makedirs("0") ran, and the run wrote its checkpoint into a directory literally named `0` in the
# repository root. One tuple, one predicate, one call site per question.
_OFF = ("0", "", "off", "no", "none", "false")


@dataclasses.dataclass(frozen=True)
class Snapshot:
    """One checkpoint as read from disk. `payload` is OPAQUE to this package.

    CKPT never learns what a "rank" is: payload is a mapping the composition root assembles from
    every package's own state_dict and hands back whole, and geometry is a manifest of records each
    package produced. This package compares recorded against live and prints the arithmetic.

    `resume` CARRIES THE Resume RECORD THIS LOAD PRODUCED (attempted=True, loaded=True, plus the
    step/epoch/best_state this snapshot holds) -- load()'s own DID IT FIRE line has always claimed
    Resume as its surface and nothing before this field ever built one, so a report reading a
    successful resume had no artifact to print beside "loaded from ckpt.pt" (round1/round2 finding
    on ckpt.load). It is carried ON Snapshot rather than as a second return value because load()'s
    signature is read directly by spine/compose.py (`restored = ckpt_api.load(ckpt)`) and a tuple
    return would be a breaking change to a call site outside this package.
    """
    payload: dict
    geometry: dict
    step: int
    epoch: int
    best_state: object
    resume: "Resume"


@dataclasses.dataclass(frozen=True)
class Resume:
    """The three-state DID IT FIRE for the resume path.

    `attempted` without `loaded` is the state the old tree could not report: a RESUME that named a
    path nothing could be read from fell through to a cold start with nothing in the log saying the
    continual-learning boundary the run was launched to measure had not happened.

    THAT STATE IS STILL UNREACHABLE IN THIS TREE, AND SAYING SO IS THIS PARAGRAPH'S WHOLE JOB. The
    only place in this package that constructs a Resume is ckpt/api.py::load, and it constructs one
    shape: `attempted=True, loaded=True`, both literal. The branch that would produce the other
    combination -- a resume source that names a file which is not there -- RAISES instead of
    returning, so the run does not survive to carry a record at all. `attempted` and `loaded` are
    therefore two-valued fields that can today hold exactly one value each, and the sentence above
    describes the state this record was SHAPED for rather than one it can currently hold.

    NEITHER FIELD IS DELETED AND THE RECORD IS NOT NARROWED TO THREE, because closing the gap is a
    decision and not a body fix: it means turning ckpt/api.py::load's FileNotFoundError into a
    printed state, which reverses the already-settled refusal that put the raise there (a cold
    start where a resume was asked for is a DIFFERENT EXPERIMENT, not a slower run). That referral
    is written out in full at ckpt/api.py::load. Round 1's audit item on this is closed on its FIX
    NOTE -- build the record on the surviving path -- and NOT on its title, which asked for the
    attempted-without-loaded state to become reachable; this paragraph exists so the ledger cannot
    be read as having closed both.
    """
    attempted: bool
    loaded: bool
    step_restored: int
    epoch_restored: int
    best_restored: bool


def saving_on(ckpt: Config):
    """Is this run persisting anything? ONE PREDICATE, ONE PLACE.

    The old tree normalised ("0", "", "off", "no", "none", "false") -> off at :5329, HUNDREDS OF
    LINES BELOW the first consumer at :1010, so the tokenizer save path was computed from the raw
    string and would have named a file "0.dyntok.json"; `_ck0` at :1010 re-implements the same
    six-spelling test to work around it. Before the normalisation existed, `if not ck: return`
    never fired, os.makedirs("0") ran, and the run wrote ckpt.pt and source.bin into a directory
    literally named `0` in the repo root -- which .gitignore covers neither, so it got committed.

    `choices=` cannot express "any path, or one of six spellings of off" and Lever.coerce for a str
    default is str(raw) with no per-lever hook, so the honest repair is this function -- called by
    every site, never re-typed at a call site. The rename SAVE_CKPT -> CKPT_DIR is the other half:
    a name that says DIR cannot be typed as a flag by reflex.

    LEVERS READ: dir
    WIRES READ: none
    DID IT FIRE: the returned bool is recorded once; every save records refused_off when it is False
    """
    ckpt = ckpt.owned_by("CKPT")
    return str(ckpt.dir).strip().lower() not in _OFF


def save_period(ckpt: Config):
    """The periodic-save cadence, AS units.Windows. Handed to RUN's Cadences.due.

    UNIT: Windows, and the census says Flushes. STATED, NOT SETTLED QUIETLY. `_due(_k, _n)` compares
    `step - _fired[_k]` (:5283-5285) and `step` advances once per WINDOW (:6796, :7708), so the
    number an operator types is a count of WINDOWS. The census answered "which clock is the gate
    EVALUATED on"; the unit answers "which clock is the THRESHOLD COMPARED against". Declaring
    Flushes while comparing against a window counter is the pin_tick defect exactly.
    longrun.sh:521 ships CKPT_EVERY=4000 at BATCH_W=12; reading one as the other is a 12x error in
    how often a long run is killable. Because Cadences.due is elapsed-since-last-fire, evaluating
    it at the flush tail costs nothing and needs no conversion -- THERE IS NO WINDOWS->FLUSHES CALL
    ANYWHERE IN THIS PACKAGE.

    THE DECLARED GATE IS BUILT HERE AND RIDES ON THE RETURNED PERIOD (ruled 2026-09-03). This line
    has claimed a Gate since the surface was frozen and the body produced none, so the condition it
    names -- CKPT_DIR set with CKPT_EVERY == 0, i.e. "the only saves are the final one plus
    SIGUSR1" -- was stated nowhere. IT CANNOT BE RECOVERED FROM WHAT THE RUN ALREADY PRINTS, and
    that was checked rather than assumed. spine/derive.py::cadences_that_cannot_fire does report a
    period of zero, and its own comment names this file while doing it -- but it never reads `dir`,
    so it returns the SAME answer on two configurations that are not the same run. Measured through
    spine.assemble.build on the resolved defaults, with the run length held at sixty thousand
    windows:

        CKPT_DIR         CKPT_EVERY   saving_on   cadences_that_cannot_fire
        "" (shipped)              0       False   [("ckpt", 0, 0)]
        runs/x                    0        True   [("ckpt", 0, 0)]
        "" (shipped)           4000       False   []
        runs/x                 4000        True   []

    Two pairs of genuinely different states, rendered identically. At the SHIPPED DEFAULTS the
    honest answer is the third state and not the second: CKPT_DIR is empty, so an operator who
    reads "the ckpt gate cannot fire" and raises CKPT_EVERY still saves nothing. Collapsing
    armed-but-zero into unreachable is exactly what spine/gate.py::Gate exists to refuse, so the
    three arms are spelled here: UNREACHABLE when saving is off at all, armed-and-not-fired at
    every == 0 with the final-plus-SIGUSR1 sentence as its reason, FIRED otherwise.

    WHY IT RIDES ON THE RETURNED Windows RATHER THAN CHANGING THE SHAPE OR MINTING AN ACCESSOR.
    Three alternatives, each priced by running it rather than by preference:
      (a) return (Windows, Gate), or a small record. REFUSED: this value is read UNWRAPPED into the
          `periods` mapping at two sites in spine/compose.py, which this package does not own, and
          both train/api.py::Cadences.due and spine/derive.py::cadences_that_cannot_fire refuse
          anything whose type is not exactly Windows -- a SUBCLASS raises too, which was checked
          (`cadences_that_cannot_fire` on a Windows subclass raises UnitError).
      (b) a new public gates()/periodic_gate() accessor, which is what FAB, CAP, MEM and TOK all
          effectively have. REFUSED HERE AS A BODY FIX, WITH THE COST MEASURED: adding one to this
          file was tried, and the suite answers K1 (a public surface docs/04_CONTRACT.md does not
          declare), K6 (named by no row in ASSEMBLY_ORDER or LOOP_ORDER and not deferred) and K13
          (the entry-point total, written in seven present-tense claims across six locations in
          docs/04_CONTRACT.md). Every one of those repairs lands in docs/04_CONTRACT.md or
          spine/compose.py. It is the right shape if CKPT is ever to have a package-wide DID IT
          FIRE surface, and it is a REFERRED EDIT, not something a body-writer may take
          unilaterally.
      (c) delete the claim from this line and leave the condition unsaid. REFUSED: that is the
          quiet narrowing, and it would put the sentence nowhere at all.
    So the Gate goes where the four packages that already produce one put theirs -- on the object
    the entry point returns, under the name `.gates` (fabric/api.py::build's pop.gates,
    capacity/api.py::new_valve's valve.gates, memory/api.py::open_store's store.gates,
    tok/api.py::build_vocabulary's vocab.gates; sig/api.py is the fifth producer and uses `.gates`
    as a DICT keyed by gate name rather than a tuple, so a renderer will meet two shapes -- named
    here because this paragraph is where the convention is claimed).

    THREE COSTS, STATED SO NONE OF THEM IS DISCOVERED.

    (1) A Clock is a value object whose arithmetic returns a FRESH instance, so `period +
    Windows(0)` or a re-wrap `Windows(period)` drops the tuple -- checked: `period - Windows(1)`
    comes back with no `.gates` at all. Nothing in the tree does either today (both consumers read
    `.n` off the object they are handed) and whoever writes Cadences.due must not normalise its
    argument.

    (2) THE ATTACHMENT ITSELF WORKS BY AN OMISSION, NOT BY A DECLARED AFFORDANCE.
    spine/units.py::Clock declares `__slots__ = ('n',)`; spine/units.py::Windows and its five kinds
    declare a docstring and a KIND and NO `__slots__` OF THEIR OWN, so every subclass instance
    carries an implicit `__dict__` and `period.gates = (gate,)` lands in it. Measured:
    `'__slots__' in units.Windows.__dict__` is False, and after the assignment `period.__dict__`
    is `{'gates': (...)}`. Adding `__slots__ = ()` to those six subclasses -- the ordinary tidy-up
    for a subclass of a slotted class, and a plausible future edit by someone who has never read
    this line -- turns this function's last-but-one statement into an AttributeError, and does the
    same to the four sibling producers named above. What is NOT at risk was checked rather than
    assumed: with the tuple attached, `int`/`__index__`/`bool`/`str`/`repr` are unchanged, `hash`
    is still `hash((kind name, n))` so a gated Windows hashes and compares equal to a bare one,
    and units.py's one reason for existing is intact -- `Steps(1) >= period` still raises UnitError
    and `period == 0` still raises rather than silently comparing.

    (3) NOTHING RENDERS IT YET, so the condition this Gate states reaches an OBJECT GRAPH and not
    an operator. `grep -rn "[.]line()" src/` returns exactly one call site, in opt/api.py, over
    OPT's own local list; `grep -rn "[.]gates" src/` finds five producers and NO consumer, compose
    included. The path from here to a printed line exists -- spine/compose.py holds the same
    `periods` mapping it passes to RUN.new_cadences and RUN.cadence_audit -- but both of those are
    still `raise NotImplementedError` stubs, so the round-1 complaint that "the condition is stated
    nowhere" is answered in the graph and NOT YET in any output. That is the universal P3 state
    rather than a defect this ruling introduced, and it is written here so the audit item is not
    read as fully retired.

    LEVERS READ: every, dir (through saving_on, for the gate's reachability arm)
    WIRES READ: none
    DID IT FIRE: Cadences.ledger()["ckpt"] counts the fires; the `.gates` tuple on the returned
                 period CARRIES (not yet renders -- see cost 3) ckpt.periodic_armed, which is the
                 :5619-5621 warning replaced by a gate with its own condition -- dir set and
                 every == 0 is armed-and-not-fired with "the only saves are the final one plus
                 SIGUSR1" as its reason, and dir off is UNREACHABLE instead of a zero the ledger
                 cannot explain. The word an operator sees is owed by RUN.cadence_audit, which is
                 a stub; until it has a body this Gate is readable only from the returned object
    """
    ckpt = ckpt.owned_by("CKPT")
    # NOT A STUB, AND THE FOUR SIBLINGS ARE NOT EITHER -- EVAL.curve_period, DOM.manage_period,
    # FAB.manage_period and MEM.rekey_period, each verified stub-free by reading it: every one of
    # the four ends in a bare `return U.Windows(int(<its own lever>))` and raises nothing. This
    # comment said THREE, which is the same off-by-one docs/04_CONTRACT.md corrected in its own
    # sentence about these five accessors on 2026-09-03 and eval/api.py::curve_period corrected in
    # its copy of this comment, and it survived here for the reason that document gave: the number
    # is spelled as a WORD, tests/test_contract.py's K13 reads digits, and K13's own output lists
    # "a number written in words" under NOT SEARCHED FOR -- so no check in the suite can see a
    # miscount written this way, and only a reader can. A period accessor is one
    # construction over its declared levers, and its whole job is that Cadences.due REFUSES a
    # bare int while Config hands one back for all 35 levers that declare a Clock unit
    # (ISSUES P1-H51). Leaving it a stub kept spine.compose._periods -- and therefore
    # RUN.cadence_audit, the one statement that makes ISSUES P1-C11 visible -- unreachable
    # until P4, for no reason but symmetry with entry points that have real work to do.
    every = int(ckpt.every)
    period = U.Windows(every)
    # ONE PREDICATE, NOT A SECOND COPY OF THE SIX SPELLINGS OF OFF. saving_on is this package's own
    # answer to "is this run persisting anything", and re-typing its test here is the defect that
    # wrote a directory literally named `0` into the repository root.
    if not saving_on(ckpt):
        gate = Gate("ckpt.periodic_armed", False, every, 1, reachable=False,
                    reason=f"CKPT_DIR={str(ckpt.dir)!r} is off, so nothing is saved at all and "
                           f"periodic saving has no state to be in. Reported UNREACHABLE rather "
                           f"than as an unmet condition, which would send an operator to raise "
                           f"CKPT_EVERY and change nothing observable.")
    elif every > 0:
        gate = Gate("ckpt.periodic_armed", True, every, 1)
    else:
        gate = Gate("ckpt.periodic_armed", False, every, 1,
                    reason="CKPT_EVERY=0 with CKPT_DIR set: the only saves this run makes are the "
                           "FINAL one and any SIGUSR1. A legitimate configuration, and one the "
                           "report must SAY -- without this line it is indistinguishable from a "
                           "run that is not saving at all.")
    period.gates = (gate,)
    return period


def save(ckpt: Config, *, payload, geometry, step, epoch, reason, suffix=""):
    """Write one checkpoint generation ATOMICALLY (.tmp + os.replace, one previous generation kept).
    Returns True iff a file was written -- the caller used to assume success and printed "saved to
    None.best".

    `reason` is one of "periodic" | "sigusr1" | "best" | "bestN" | "final" and is RECORDED, so the
    log can name the route that fired rather than describing the mechanism that did nothing.

    THE SUFFIX APPLIES TO THE WHOLE SNAPSHOT, NOT ONLY TO ckpt.pt. ISSUES P1-M46: `ck = ck + suffix`
    (:5335-5337) suffixed the checkpoint while `TOK.save(_TOK_SAVE)` (:5344-5348) ALWAYS wrote the
    BASE vocabulary path, so every later save overwrote the file a .bestN snapshot records as its
    own; by the end of a run a .best checkpoint's recorded merge count no longer matches the file
    it names and resuming from it trips the VOCABULARY MISMATCH refusal at :4380-4408. best_keep
    multiplies that defect n times over. A SNAPSHOT'S VOCABULARY IS PART OF THE SNAPSHOT -- BUT NOT
    IN `payload`, AND THIS SENTENCE USED TO SAY OTHERWISE (corrected 2026-09-02, Q-TOK-10). The
    merges live in the FILE at d_vocab_save_path: build_vocabulary REPLAYS them from
    d_vocab_read_path on a resume (tok/api.py::build_vocabulary), and TOK.vocab_state carries "everything a
    resume needs THAT THE MERGE LIST ALONE DOES NOT CARRY", i.e. explicitly not the merges. Two
    frozen docstrings disagreed about where a snapshot's vocabulary lives; the repair is that
    TOK.save_vocabulary now takes the SAME `suffix` this call takes, so the tokenizer file travels
    under the snapshot's suffix instead of being overwritten by the next base save.

    LEVERS READ: dir (through saving_on and the artifact path set)
    WIRES READ: none
    DID IT FIRE: Saves(periodic, sigusr1, best, best_keep_by_slot, final, refused_off) -- SIX
                 counters, because "0 saves" cannot distinguish "never due" from "saving is off"
    """
    ckpt = ckpt.owned_by("CKPT")
    raise NotImplementedError(
        "CKPT.save: P4 (ckpt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CKPT.")


def install_save_signal():
    """Arm `kill -USR1 <pid>`: sets a flag the loop drains beside the periodic save. Returns a Flag
    object with .take() (read-and-clear).

    NOT A LEVER AND IT NEEDS NONE (:7709); recorded here so that "the only saves are the final one
    plus the cadence" is not read as complete. NEVER torch.save inside a handler -- reentrancy
    (:5457-5462).

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: Saves.sigusr1
    """
    raise NotImplementedError(
        "CKPT.install_save_signal: P4 (ckpt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CKPT.")


def resume_source(ckpt: Config):
    """The checkpoint this run continues, normalised (a run directory or a .pt file), or None.

    ONE SPELLING OF UNSET: RESUME and SAVE_CKPT were read as None in some places and "" in others
    (:73).

    LEVERS READ: resume
    WIRES READ: none
    DID IT FIRE: Resume.attempted
    """
    ckpt = ckpt.owned_by("CKPT")
    raw = str(ckpt.resume).strip()
    if raw.lower() in _OFF:
        return None
    # BOTH SUPPORTED FORMS NORMALISE TO THE FILE. `RESUME=runs/x/` and `RESUME=runs/x/ckpt.pt` are
    # both documented, and the sibling-vocabulary guess broke on the second because it appended
    # `.dyntok.json` to a path that already ended in `.pt` (ISSUES P1-M19). Normalising here means
    # every later consumer -- the vocabulary read path among them -- sees one shape.
    return os.path.join(raw, "ckpt.pt") if raw.endswith(("/", os.sep)) or os.path.isdir(raw) else raw


def load(ckpt: Config):
    """Read the resume source. Returns Snapshot(payload, geometry, step, epoch, best_state, resume)
    or None.

    `best_state` IS IN THE CHECKPOINT -- ISSUES P1-M45: `_best_bpb` starts cold on every process
    (:4243) and nothing carried it, so the first post-resume probe satisfied "no best yet" and
    OVERWROTE THE PARENT'S best-by-held-out snapshot with the Adam re-warm bump. That is this
    package's own bug, not a coupling: the best-so-far is checkpoint state.

    THE Resume RECORD IS BUILT HERE, ON THE PATH THAT SURVIVES. Before this fix nothing in the
    package ever constructed a Resume: the class existed, this docstring's own DID IT FIRE line
    named it, and no call site anywhere returned one -- so step_restored/epoch_restored/
    best_restored were unreachable even on a SUCCESSFUL resume, the case the finding's own fix note
    calls "the record ... the report prints after the run survives". Fixed by attaching
    Resume(attempted=True, loaded=True, step_restored=step, epoch_restored=epoch,
    best_restored=(best_state is not None)) to the returned Snapshot as `resume`, rather than as a
    second return value: this function's return is read directly at one call site
    (spine/compose.py's `restored = ckpt_api.load(ckpt)`), and a tuple return would change that
    call's shape outside this package.
    THE attempted-WITHOUT-loaded STATE STAYS UNREACHABLE FROM HERE, ON PURPOSE, AND THAT IS NOT
    THIS FINDING. The missing-file branch below RAISES rather than returning: the docstring's own
    reasoning for that raise -- "a cold start where a resume was asked for is not a slower run, it
    is a different experiment" -- means the run does not survive to print a report line at all, and
    a Resume record has nowhere to attach when this function never returns. Rendering
    "attempted=True, loaded=False" as a printed state INSTEAD of a crash would reverse an already
    -settled refusal for a different, narrower defect (M19/the old silent fallback); that is a
    call for whoever owns the raise decision, not a body fix. `resume_source`'s own "DID IT FIRE:
    Resume.attempted" is already answerable without this function: `sysm.resume_src =
    ckpt_api.resume_source(ckpt)` in spine/compose.py is `is not None` exactly when a resume was
    attempted, before this function is ever called.

    LEVERS READ: resume
    WIRES READ: none
    DID IT FIRE: Resume(attempted, loaded, step_restored, epoch_restored, best_restored) -- on the
                 SURVIVING (successful-load) path only; see the note above for the raise path
    """
    ckpt = ckpt.owned_by("CKPT")
    src = resume_source(ckpt)
    if src is None:
        return None
    if not os.path.isfile(src):
        # NAMED, NOT SILENT. A RESUME pointing at nothing used to fall through to a cold start, and
        # in this system a cold start where a resume was asked for is not a slower run -- it is a
        # different experiment, because every forgetting number is a measurement ACROSS the
        # boundary this path creates.
        raise FileNotFoundError(
            f"CKPT_RESUME={str(ckpt.resume)!r} resolves to {src!r}, which does not exist. A resume "
            f"is the experiment here, not a convenience: continuing without one silently would "
            f"report a cold run as a continual-learning run.")
    # weights_only=False: the payload carries this project's own record objects, not just tensors,
    # and the file is one this run's own operator named.
    blob = torch.load(src, map_location="cpu", weights_only=False)

    # `best_state` IS IN THE CHECKPOINT (ISSUES P1-M45). `_best_bpb` started cold on every process,
    # so the first post-resume probe satisfied "no best yet" and overwrote the PARENT's
    # best-by-held-out snapshot with the Adam re-warm bump. Reading it back is the whole repair.
    step, epoch = int(blob.get("step", 0)), int(blob.get("epoch", 0))
    best_state = blob.get("best_state")
    # THE Resume RECORD, BUILT ON THE PATH THAT SURVIVES. attempted=True and loaded=True are both
    # certain here -- resume_source already returned a non-None source and the file has just been
    # read without raising -- so the only real numbers to report are the three the checkpoint
    # carried: step, epoch and whether a best-so-far snapshot rode along.
    resume = Resume(attempted=True, loaded=True, step_restored=step, epoch_restored=epoch,
                    best_restored=best_state is not None)
    return Snapshot(payload=blob.get("payload") or {},
                    geometry=blob.get("geometry") or {},
                    step=step, epoch=epoch, best_state=best_state, resume=resume)


def check_geometry(ckpt: Config, snapshot, geometry):
    """Refuse a checkpoint that cannot load into this run's shapes, NAMING THE KNOB. Raises
    GeometryRefusal; returns a GeometryReport when it passes.

    `geometry` is {field: GeometryField(value, rule, env_name, why)} assembled by the composition
    root -- BY IT AND NOT BY A FAN-IN OF PACKAGE CALLS, and this sentence said the opposite until
    2026-09-02 (Q-CKPT-1, RESOLVED). It is built from the frozen Configs and LM.resolve's
    LMGeometry, in _geometry_manifest, BEFORE THE FIRST ALLOCATION -- which is the whole point of
    the gate, and is also why it cannot be assembled the way this line used to describe: a
    package's geometry() needs a built object, and the build is the thing this refusal exists to
    happen before. There is exactly one geometry() in the tree, WORLD's, and it is correctly
    placed on the SAVE side, where the object exists; what it contributes is the GROWN population
    count, which is recorded and reported UNCHECKED here rather than compared. RULES ARE THE
    OWNER'S, because the direction
    differs per field: FAB's slots is MAY_WIDEN (the tensors are preallocated and growth only
    advances n_live, so a smaller-cap checkpoint IS a prefix -- and refusing to widen would mean a
    resume can never add capacity for the area it is adding, which is the whole exercise); FAB's
    rank and dk are EXACT (inner dimensions, no prefix is valid); WORLD's n0 needs BOTH directions,
    because the replay `while world_fwd.n() < _want2` (:4591) handles only growth and FEWER
    predictors than this run builds falls through to load_state_dict as "Missing key(s)
    preds.N.*" (M43).

    A MISSING FIELD IS A REFUSAL, NOT A SKIP. The fabric's three branches were each guarded on
    `_ck_cap and ...`, so a checkpoint with no "cap" slid through all three and reached
    load_state_dict as the five-shape dump the gate exists to replace (:4432-4441). The comparison
    is driven off the manifest's KEY SET rather than off truthiness, so `if recorded and recorded
    != live` -- the untrippable-guard shape -- is not writable here.

    LEVERS READ: none (this is mechanism)
    WIRES READ: none
    DID IT FIRE: GeometryReport lists every field checked, its rule, and BOTH values. A field
                 present in the checkpoint and ABSENT from `geometry` is reported as UNCHECKED,
                 which is the H22 state made visible: :5365-5366 records six world fields and
                 :4590 reads exactly one.
    """
    ckpt = ckpt.owned_by("CKPT")
    raise NotImplementedError(
        "CKPT.check_geometry: P4 (ckpt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CKPT.")


def new_retention(ckpt: Config, *, restored=None):
    """The best-model policy. Returns Retention.

    LEVERS READ: best_keep, best_keep_tol
    WIRES READ: none
    DID IT FIRE: Retention.counters() -> (probes_seen, new_bests, rotations, slots_used,
                 inert_reason). `inert_reason` is populated when best_keep > 0 and saving is off,
                 and when NO CURVE VALUE HAS EVER ARRIVED -- which at P3 is always, and must read
                 as armed-but-inert rather than as zero local lows.
    """
    ckpt = ckpt.owned_by("CKPT")
    raise NotImplementedError(
        "CKPT.new_retention: P4 (ckpt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CKPT.")


class Retention:
    """The best-model policy object. Constructed by new_retention()."""

    def consider(self, curve_bpb, step):
        """One held-out probe arrives. Returns BestAction(save_best, rotate_slot).

        curve_bpb IS AN ARGUMENT, NOT A WIRE. eval/levers.py::<module> declares an outgoing d_curve_bpb
        and ckpt/levers.py expects it, but a Config freezes when build() returns and this number is
        produced thousands of windows into the run -- so it cannot be a Coupling row. Recorded
        because "declared as a wire and never made" reads as "not ported yet" long after it has
        become "ported, and wired to a name nobody owns".

        THE RULE IS "DESCENT INTO A GOOD REGION", NOT "LOCAL MINIMUM": `_cm < _prev_probe - 1e-6
        and _cm <= _best * (1.0 + tol)` (:6478-6479). A true local minimum can only be confirmed
        one probe later, by which time the weights have moved past it, so this is a DELIBERATE
        SUPERSET. The tolerance is MULTIPLICATIVE and a reader will assume otherwise: at a best of
        2.175 b/B the default 0.02 admits up to 2.219, a window of 0.043 bits/byte.

        EVENT-DRIVEN, NOT A SCAN. It is called only when a curve probe returned a value on this
        window. ISSUES P1-L43: `_cs = [b for st, _p, b, _a in _CURVE if st == step]` ran once per
        window over a list that grows by len(VALC) entries every RATE_EVERY steps, returning empty
        on all but 1-in-RATE_EVERY of them.

        THE BLOW-UP ALARM DOES NOT LIVE HERE. It was nested inside `if BEST_TRACK and _CURVE:`
        (:6432, :6458-6472), so a run that was not SAVING got no warning it had stayed elevated --
        the recorded case lost 4.6 b/B and then spent ~520,000 further steps never getting back,
        with nothing said until a report that called it PLATEAUED. It is an EVAL Reading over the
        curve (derive.blowup_stale), and gating an instrument on a checkpoint flag is what this
        rebuild exists to end.
        """
        raise NotImplementedError("CKPT.Retention.consider: P4 (ckpt) fills this in.")

    def state(self):
        """The retention state for the checkpoint: (best_bpb, best_step, best_saved, prev_probe,
        rotation ring). Restored by new_retention(restored=...). This is the M45 fix."""
        raise NotImplementedError("CKPT.Retention.state: P4 (ckpt) fills this in.")

    def counters(self):
        """(probes_seen, new_bests, rotations, slots_used, inert_reason) -- the DID IT FIRE surface
        for the retention half of this package."""
        raise NotImplementedError("CKPT.Retention.counters: P4 (ckpt) fills this in.")
