"""The LOOP DRIVER: the one thing that takes a System and runs windows through it.

IT IS NOT A PACKAGE AND IT HAS NO LEVERS. spine/compose.py assembles the system and stops; this
file is its sibling and does the only job compose.py cannot -- walk the windows. It owns exactly
two things no entry point can own, both named once here because LOOP_ORDER says so:

  * THE CUT. `x`, `y` and the per-window token slice come from Segmentation.ids and NO ENTRY POINT
    RETURNS THEM -- RunClock.advance appends to the accumulator and hands back a Tick, which is a
    clock, not a batch. spine/compose.py::<module> names the cut `_window_bounds` / `_flush_bounds`
    in the paragraph immediately above LOOP_ORDER, and says "the rows that consume it say so,
    rather than each restating a slice nobody wrote down". Those two functions are here.
    (The citation was `compose.py::LOOP_ORDER` in this file's first draft and O13 refused it on the
    first run: the sentence is in the COMMENT above the table, not inside it. A quotation
    attributed to the wrong symbol is the defect class this tree rates worst, and it took a new
    file eleven minutes to produce one.)
  * THE PROGRESS LINE, which is why RUN.PROGRESS_WINDOWS is a module constant with no lever and no
    LOOP_ORDER row: rows are entry-point calls and no entry point prints it.

EVERY PERIODIC GATE GOES THROUGH Cadences.due(key, period, clock). The modulo form is not writable
here: `step % N == 0` below a batch early-out fired 999 times at BATCH_W=1 and ZERO times at every
other width, and CKPT_EVERY sat in that block. The keys are the root's, from compose.py::_periods.

WHAT THIS DRIVER SKIPS, AND WHY IT SAYS SO OUT LOUD -- IN TWO LISTS, NOT ONE
============================================================================
`RunResult.skipped` names every LOOP_ORDER B row this driver has NO CALL SITE FOR. It has been
empty since the edit that wired the last of the then twenty-one, and stays empty at twenty-two
(WORLD.forecast, Q-WORLD-10, arrived WITH its call site); an empty list is exactly the state that
made the FIRST version of this report wrong: it filtered the B row through "is the body a stub" and
printed "0 MECHANISM(S) NOT CALLED" on a run that invoked six of twenty-one. The list is derived
from the table and cross-checked against `_CALLS` in both directions, so a row this driver drops
cannot vanish from the report and a `_CALLS` entry the table does not list raises.

`RunResult.gated` IS THE SECOND LIST AND IT EXISTS BECAUSE A CALL SITE IS NOT A CALL. Three rows
stand behind events (Due.mint, Due.probation) and one behind "the optimizer actually stepped"; at
the shipped TOK_PROBATION_USES=0 the probation cadence is never even asked, so two of the
twenty-two have a call site that CANNOT RUN. Reporting only the first list would say this run
judged probation when nothing did -- the same overstatement, one layer in. `_gate_report` reads the
three states (fired N / armed but 0 / unreachable) off the counter each owning package keeps,
rather than re-deriving a verdict here from levers this file does not own.

WHAT A RUN ON THIS DRIVER MEASURES TODAY: goal A's core -- a language model, routed through the
fabric, trained by the optimizer -- AND the mechanisms goal B is made of. The fabric grows, memory
is written and maintained, the vocabulary mints and LM.on_mint initialises each new row from its
parents. WHAT IS STILL MISSING, all of it for a named reason a reader can check: DOM.observe is a
stub so every window is domain 0; MEM.read is a stub so the store is write-only and its eviction
rules are write-order FIFO whatever they say; MEM.census is a stub so growth's memory-pressure leg
is unreachable. ALL THREE OF THOSE SENTENCES WERE TRUE UNTIL 2026-09-21 AND ARE NOW FALSE: observe,
read and census have bodies, this driver calls all three, the partition assigns real ids, the probe
retrieves and promotes, and pressure has a producer. The next sentence was true until FAB.manage and
SIG.train_step got bodies and this driver began asking their cadences, and is false now: "FAB.manage
and SIG.train_step are stubs, so no expert is ever culled and the signature encoder never learns".
Both are called on their cadences (fab.manage every FAB_MANAGE_EVERY windows, which a default
run reaches twice at 200 kB). What remains: the retok is DEFERRED TO THE EPOCH ROLL rather than
performed mid-epoch, which at RUN_EPOCHS=1 means never (Q-RUN-8).

STAGE E IS DRIVEN AS OF 2026-09-22 and it is what makes a second epoch a second epoch: the stream
is redrawn, the segmentation is REBUILT AT THE CURRENT VOCABULARY -- the only route by which a
token this run minted can appear in this run's own training data -- the clock is told the new
length, an epoch resample is stamped as a self-inflicted shift (the first thing in the tree ever to
supply FAB.grow_check's `shift_at`), and MEM is told its contexts are stale.
"""
import dataclasses
import math
import time

import torch

from spine import units as U
from spine import gate as _gate
from train import api as run_api
from data import api as data_api
from tok import api as tok_api
from lm import api as lm_api
from sig import api as sig_api
from fabric import api as fab_api
from opt import api as opt_api
from capacity import api as cap_api
from spine.compose import _sample_window as _c_sample_window
from spine.compose import RefusedRun as _c_RefusedRun
from spine.compose import _key_fn as _c_key_fn
from spine.compose import _sig_encode_fn as _c_sig_encode_fn
from spine.compose import _head as _c_head
from spine.compose import _signature_stream as _c_signature_stream
from spine.compose import _signature_cursor as _c_signature_cursor
from ckpt import api as ckpt_api
from domains import api as dom_api
from memory import api as mem_api
from world import api as world_api


# THE ELEVEN, READ OFF THE TREE RATHER THAN TYPED. A hand-written list would rot the first time a
# body landed, and it would rot SILENTLY -- the run would keep announcing a skip that no longer
# happens. `_is_stub` asks the module.
def _is_stub(fn):
    """True when this entry point is still a P4 stub.

    ASKED OF THE LIVE FUNCTION, not of a list. It calls nothing: a stub raises NotImplementedError
    from its body, so the only safe question is about the code object, and `__doc__` plus the
    module's own source would be a second parser. This reads the bytecode's constants for the
    marker string every stub in this tree carries -- "P4 (" -- which is exactly the shape
    tests/test_census.py counts and therefore cannot drift from it without the census noticing.
    """
    try:
        consts = fn.__code__.co_consts
    except AttributeError:
        return False
    return any(isinstance(c, str) and "P4 (" in c and "fills this in" in c for c in consts)



# THE ENTRY POINTS `_flush` AND `run` ACTUALLY INVOKE. Adding a call above means adding its name
# here, in the same edit, and the cross-check below turns a forgotten one into a raise rather than
# into a report that overstates what the run did.
# KEYED BY STAGE, AND IT WAS ONE FLAT SET UNTIL 2026-09-22. `uncalled` is computed as
# `rows[stage] - _CALLS`, so a flat set credits an entry point at EVERY stage the table lists it
# at, as soon as the driver calls it at ONE of them. MEM.census and DOM.census are stage-A rows
# this driver calls on the dom.manage cadence AND stage-R rows -- "(reconcile=True) ... re-taken at
# the end so the report's numbers are the settled ones" -- and the R calls did not exist. The run printed
# "uncalled=0" anyway, every time, because the A call had already spent their names. A per-stage
# split is what made them visible, and it found nothing else: those two, and the ordering defect
# beside them.
# CKPT.save IS IN THREE STAGES ON PURPOSE. LOOP_ORDER lists it at B (the cadence), at C (the
# fan-out it heads) and at R (reason='final'), and one entry point reached by three routes is what
# that means -- not one call credited three times.
_CALLS = {
    # ---- stage E, the epoch roll (reachable only at RUN_EPOCHS > 1)
    "E": frozenset({"DATA.draw_stream", "TOK.tokenize", "RUN.RunClock.begin_epoch",
                    "DOM.on_retokenize"}),
    # ---- stage A: the cadenced maintenance block, then the per-window pair
    "A": frozenset({
        "MEM.census", "DOM.manage", "DOM.census", "DOM.rekey",
        "SIG.cadence_due", "SIG.train_step", "FAB.manage",
        "RUN.RunClock.advance", "SIG.encode", "DOM.observe", "TOK.on_window"}),
    # ---- stage B, per flush: all twenty-three
    "B": frozenset({
        "LM.embed", "WORLD.forecast", "LM.encode", "FAB.forward", "LM.decode", "LM.lm_loss",
        "WORLD.loss_terms", "LM.anchor_term", "OPT.remap_rows", "OPT.scaled_backward",
        "RUN.RunClock.note_backward",
        "OPT.maybe_step", "FAB.own_lr_scale", "CAP.caps", "FAB.observe", "FAB.grow_check",
        "MEM.write", "MEM.maintain", "TOK.mint_burst", "LM.residual_ratios", "TOK.judge_probation",
        "DOM.note_competence", "CKPT.save"}),
    # ---- stage C, the checkpoint fan-out, through _payload and _save
    "C": frozenset({
        "DATA.stream_state", "TOK.vocab_state", "LM.state_dict", "SIG.state_dict", "FAB.state_dict",
        "WORLD.state_dict", "WORLD.geometry", "MEM.state_dict", "DOM.state_dict", "CAP.state",
        "OPT.state_dict", "RUN.Cadences.state", "RUN.RunClock.counters", "CKPT.Retention.state",
        "TOK.save_vocabulary", "CKPT.save"}),
    # ---- stage R, the report, through _report and run's own tail
    "R": frozenset({
        "DOM.prior", "MEM.census", "DOM.census",
        "LM.counters", "SIG.counters", "FAB.counters", "OPT.counters", "CAP.counters",
        "RUN.RunClock.counters", "RUN.Cadences.ledger", "CKPT.Retention.counters",
        "RUN.bench_summary", "CKPT.save"}),
}
_CALLS_FLAT = frozenset().union(*_CALLS.values())

# CALLS THIS DRIVER MAKES THAT LOOP_ORDER DOES NOT GIVE A ROW OF THEIR OWN. Two, and both are named
# inside ANOTHER row's text rather than carrying a row, which is the only thing that puts a name
# here. LM.on_mint is named in TOK.mint_burst's B-row text ("-> LM.on_mint(sig_emb=
# SIG.encoder_embedding(...))"). MEM.apply_domain_plan is named in DOM.manage's A-row text, as the
# call it is and with its arguments -- "the Plan it returns is handed straight on as
# MEM.apply_domain_plan(plan=Plan, live_sources=DOM.census's `live`)" -- which is the form K6
# credits, and DOM.census's row names the other end of the same wire. TOK.lift_vocab_cap is named
# in CAP.caps's B-row text the same way ("-> FAB.grow_check(soft_cap=...) and
# TOK.lift_vocab_cap(to=...)"). None of the three is an excuse for a missing row: a row would say
# WHEN, and all three are pinned to another row's moment -- the first two to that row's flush or
# pass, and the third to the moment the number that row produces CHANGES, which is the one thing a
# row naming a wire cannot express and which its own docstring rules ("AN EVENT, NOT A PERIOD").
# THIS SET USED TO CARRY FOUR NAMES AND TWO OF THEM WERE WRONG IN OPPOSITE DIRECTIONS.
# RUN.RunClock.advance and RUN.RunClock.note_backward are ON the table -- A and B respectively --
# and belong in _CALLS, which is where they are now. DOM.observe was in here, and this set does two
# things at once: it excuses a name from the cross-check AND asserts the driver calls it. The driver
# does NOT call DOM.observe -- the comment at that call site says so at length -- so listing it here
# subtracted it from the uncalled list and hid it. It was invisible while the report only ever read
# the B row, because DOM.observe is a row-A entry point and the subtraction was a no-op; the moment
# the report covered every stage it would have started lying. Two wrongs cancelling is not a test
# passing.
_OFF_TABLE = frozenset({"LM.on_mint", "MEM.apply_domain_plan", "TOK.lift_vocab_cap"})

# WHY EACH UNCALLED MECHANISM'S ABSENCE MATTERS, in the consequence a reader needs rather than the
# name they already have. Missing keys fall back to a plain sentence; nothing here is load-bearing
# for correctness, only for legibility.
_WHY = {
    # ---- stage E: the epoch driver. Not a gap in the wiring -- a statement about this driver.
    "DATA.draw_stream": "compose() draws epoch 0's stream and this driver runs a single pass, so "
                        "no second epoch is ever drawn and DATA's phase schedule never advances",
    "TOK.tokenize": "the stream is segmented ONCE, before the first window; nothing re-segments "
                    "it, which is why a minted id can never appear in the run that minted it",
    "RUN.RunClock.begin_epoch": "compose() begins epoch 0; a roll stops this driver rather than "
                                "starting the next epoch",
    # ---- stage A: the cadenced maintenance stage, and the six stubs in it
    "DOM.observe": "EVERY WINDOW IS DOMAIN 0 -- the partition never assigns, so the fabric's "
                   "per-domain books, its breadth ban and MEM's per-source floor all see ONE source",
    "DOM.manage": "no domain is ever culled, merged or spared; the 'dom.manage' cadence key reads "
                  "checks=0, which is the ledger saying the gate was never EVALUATED",
    "DOM.rekey": "domain centroids are never re-encoded, so the partition and the live signature "
                 "drift into two spaces that do not compare; 'dom.rekey' also reads checks=0",
    "DOM.census": "the partition has no did-it-fire surface and the R stage lists it as having no "
                  "producer",
    "FAB.manage": "NO EXPERT IS EVER CULLED OR SPARED. Growth runs and pruning does not, so the "
                  "population only ever rises. Its cadence is NOT ASKED rather than asked-and-"
                  "ignored: Cadences.due RECORDS the step when it answers True, so an asked gate "
                  "with no body behind it would show 'fab.manage' firing on a run where nothing "
                  "was ever culled. checks=0 is the honest reading and this line is its sentence",
    "MEM.census": "the store has no did-it-fire surface, and FAB.grow_check's memory_pressure has "
                  "no producer, so grow_on_mem_pressure is UNREACHABLE rather than off",
    "SIG.cadence_due": "SIG's own training cadence is NOT ASKED, deliberately: it gates "
                       "SIG.train_step, which is a stub, and Cadences-style gates RECORD the step "
                       "when they answer True -- so asking it and doing nothing would throw the "
                       "fire away and report a cadence that fired on a run where the encoder never "
                       "trained",
    "SIG.train_step": "THE SIGNATURE ENCODER NEVER LEARNS -- sig.train_steps reads 0, so every "
                      "routing and domain decision is taken on the warm-up encoder for the whole run",
    # ---- stage B is complete; these remain for the gated-call-site report's wording
    "CAP.caps": "no operating ceiling is read, so growth has no budget to be refused by",
    "WORLD.loss_terms": "no world-model loss term enters the objective",
    "LM.anchor_term": "minted tokens are not held near their byte composite",
    "LM.residual_ratios": "no residual-ratio reading is produced",
    "FAB.own_lr_scale": "every expert trains at the base learning rate",
    "FAB.observe": "per-expert usage and competence are never recorded",
    "FAB.grow_check": "THE FABRIC DOES NOT GROW -- no expert is ever born",
    "MEM.write": "NOTHING IS EVER WRITTEN TO MEMORY",
    "MEM.maintain": "no eviction, decay or rekey runs",
    "TOK.mint_burst": "THE VOCABULARY NEVER MINTS A TOKEN",
    "TOK.judge_probation": "no minted token is ever confirmed or retired",
    "DOM.note_competence": "per-domain competence is never updated",
    "CKPT.save": "no checkpoint is written by the loop",
}


# THE CALL SITES THAT ARE GATED, AND THE COUNTER THAT SAYS WHETHER THE GATE OPENED.
# A DRIVER THAT CALLS AN ENTRY POINT ONLY WHEN AN EVENT FIRES HAS NOT CALLED IT ON A RUN WHERE THE
# EVENT DID NOT, AND A REPORT THAT SAYS "0 NOT CALLED" IS THE SAME OVERSTATEMENT `skipped` EXISTS
# TO PREVENT, ONE LAYER IN. Three B rows stand behind gates that are UNREACHABLE at the shipped
# defaults (TOK_PROBATION_USES=0 turns the whole probation family off, and its cadence is never
# even asked), so printing "0 with no call site" and stopping there would say a run judged
# probation when nothing did.
# THE THREE STATES ARE THE TREE'S OWN, read off the counter dicts by the convention every package
# in it states: an ABSENT key means the mechanism was UNREACHABLE on the arm this run took, a key
# PRESENT AND 0 means it was armed and did not fire, and a positive value is a fire count. So this
# table names the gate in words and the counter to ask, and the reading is the counter's -- not a
# second opinion computed here from levers this file does not own.
# THE TOK ROWS READ A PER-CALL COUNT AND NOT THE CADENCE'S (2026-09-24). They read tok.due_mint and
# tok.due_probation, which TOK.on_window bumps once per WINDOW whose Due fired -- and the root ORs a
# batch of those into ONE call, so at OPT_BATCH_WINDOWS=4 TOK_GROW_EVERY=2 the report printed
# "TOK.mint_burst: fired 19 time(s)" for 10 calls. tok.mint_bursts and tok.probation_calls are
# bumped inside the two entry points and seeded by on_window on exactly the arm whose cadence can
# raise them, so the three states still come from the package. `tok.due_mint - tok.due_merged` was
# refused: due_merged counts a merge on ANY key, so the difference under-counts and can go negative.
# THE `why` TEXT IS STATIC, SO IT MAY NOT STATE A LEVER'S VALUE. It read "(TOK_PROBATION_USES=0 makes
# it unreachable)" and was printed verbatim on runs with TOK_PROBATION_USES=3; it now names the
# conditions and leaves the arm this run took to the counter.
_GATED = {
    "TOK.mint_burst": ("Due.mint, TOK's grow_every cadence asked at row A (armed only at "
                       "TOK_MODE=online with TOK_GROW_EVERY > 0), acted on once per flush",
                       "tok.mint_bursts"),
    "LM.residual_ratios": ("Due.probation, TOK's probation_deadline cadence (armed only at "
                           "TOK_MODE=online with TOK_PROBATION_USES > 0), acted on once per flush. "
                           "A CALL IS NOT A READING: it returns None at LM_COMPOSE=0, the only arm "
                           "that builds, and TOK(vocab.gates)'s tok.probation_embed says when no "
                           "ratio was supplied; the count here is TOK's calls",
                           "tok.probation_calls"),
    "TOK.judge_probation": ("Due.probation, TOK's probation_deadline cadence (armed only at "
                            "TOK_MODE=online with TOK_PROBATION_USES > 0), acted on once per "
                            "flush. A CALL IS NOT A JUDGEMENT: tok.probation_judged counts those, "
                            "and TOK(vocab.gates)'s tok.probation_embed says when none could run",
                            "tok.probation_calls"),
    "FAB.own_lr_scale": ("a flush on which the optimizer actually stepped", "fab.lr_calls"),
}
# CKPT.save IS GATED TOO AND IS NOT IN THAT TABLE, because its count is not in a counters dict this
# file can index -- CKPT keeps its books on the Retention record and in its own _SAVES ledger --
# and because the driver itself holds the fact: `_save` returns whether a file was written, and the
# three routes into it (the cadence, SIGUSR1, the final save) are all this function's. Its line is
# appended by `run` from that count, which is a measurement rather than a lookup.


def _gate_report(sysm):
    """One line per gated call site: fired N / armed but 0 / unreachable. A tuple of strings.

    THE COUNTER IS ASKED, NOT RE-DERIVED. Each row names a key in the package's own did-it-fire
    dict -- vocab.counters for tok.*, Population.counters for fab.* -- and the three states come
    from whether that key is absent, zero or positive, which is the convention
    tok/api.py::Vocabulary and fabric/api.py::_bump both state in full. Computing the answer here
    from levers would be a second verdict about a question the package that owns the threshold has
    already answered.
    """
    books = {"tok.": getattr(sysm.vocab, "counters", {}) or {},
             "fab.": getattr(sysm.fabric, "counters", {}) or {}}
    out = []
    for name in sorted(_GATED):
        why, key = _GATED[name]
        book = None
        for pre, d in books.items():
            if key.startswith(pre):
                book = d
        if book is None:
            raise RuntimeError(
                f"spine/loop.py::_gate_report: {name} names the counter {key!r} and no package's "
                f"book in this function owns that prefix. A gated call site whose did-it-fire key "
                f"cannot be read is a call site whose three states collapse back into one, which "
                f"is what this function exists to prevent.")
        if key not in book:
            out.append(f"{name}: UNREACHABLE -- gated on {why}, and {key} is ABSENT, which in this "
                       f"tree means the mechanism was never armed on the arm this run took")
        elif not book[key]:
            out.append(f"{name}: ARMED BUT 0 -- gated on {why}; {key} is present and 0, so the gate "
                       f"was evaluated and never came due in this run's length")
        else:
            out.append(f"{name}: fired {book[key]} time(s) -- gated on {why}")
    return tuple(out)


def _rows_by_stage():
    """{stage: {"PKG.name"}} for ALL of LOOP_ORDER, splitting rows that name two in one column.

    `FAB.observe/grow_check` and `MEM.write/maintain` are ONE ROW EACH and TWO ENTRY POINTS EACH.
    A count that does not split them is short by four, which is exactly the error the orchestrator
    made when it reported the B row as 10/17 rather than 10/21.

    THIS FUNCTION READ ONLY THE B ROW UNTIL 2026-09-21, AND THAT IS THE THIRD TIME THIS REPORT HAS
    OVERSTATED WHAT THE RUN DID. The first version asked "is the body a stub" instead of "does the
    driver call it" and printed 0 while calling six of twenty-one. The second answered that
    correctly and said nothing about call sites standing behind gates that cannot open, which
    `gated` now covers. This one restricted the whole question to ONE STAGE of five: every B row
    acquired a call site, the report said "0 MECHANISM(S) ... HAVE NO CALL SITE AT ALL", and stage
    A had SEVEN entry points this driver has never called -- six of them stubs, and three of them
    (FAB.manage, DOM.manage, DOM.rekey) holding cadence keys in the root's own ledger that read
    `checks=0` on every run ever taken, which is the ledger saying the gate was never EVALUATED.
    A report scoped to the stage where the work happened to be finished is a report that gets more
    confident as it covers less.
    """
    from spine import compose as _c
    out = {}
    for row in _c.LOOP_ORDER:
        for part in str(row[2]).split("/"):
            part = part.strip()
            if part:
                out.setdefault(row[0], set()).add(f"{row[1]}.{part}")
    return out


def _entry(key):
    """The live function behind "PKG.name", so `_is_stub` can be asked about it."""
    import importlib
    pkg, _, name = key.partition(".")
    mod = importlib.import_module(f"{_PKG_DIR[pkg]}.api")
    obj = mod
    for part in name.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


_PKG_DIR = {"CAP": "capacity", "CKPT": "ckpt", "DATA": "data", "DOM": "domains", "EVAL": "eval",
            "FAB": "fabric", "LM": "lm", "MEM": "memory", "OPT": "opt", "RUN": "train",
            "SIG": "sig", "TOK": "tok", "WORLD": "world"}


@dataclasses.dataclass(frozen=True)
class RunResult:
    """What one run did. FROZEN, for the reason train/api.py freezes Tick: a caller that can write
    to this can change what the run reported.

    `skipped` IS NOT DECORATION AND IT IS THE FIRST FIELD A READER SHOULD LOOK AT. It names every
    mechanism LOOP_ORDER lists that this driver could not call, so "0 experts born" is readable as
    "growth was never invoked" rather than as "growth was invoked and declined".

    RUN TOTALS AND THIS PROCESS'S, NAMED APART (2026-09-24, Q-RUN-10). `windows` and `opt_steps`
    are the RUN's totals -- the clock resumes both from the checkpoint -- while `flushes` and
    `windows_here` count THIS process only; on a fresh run windows == windows_here. run.py prints
    the two apart on a resumed run, because a throughput or a window count quoted from the total
    on a resume is a number about a process that did not run here.
    """
    windows: int
    windows_here: int
    opt_steps: int
    flushes: int
    epochs: int
    loss_first: float
    loss_last: float
    loss_curve: tuple
    elapsed_s: float
    skipped: tuple
    gated: tuple
    report: dict
    cadence_ledger: dict
    warnings: tuple
    # WINDOWS THIS PROCESS COUNTED THAT NEVER REACHED A BACKWARD PASS (2026-09-24): partial batches
    # dropped at epoch rolls (RunClock dropped_windows, the finishing roll's included) plus one
    # left by a max_windows stop. 0 at OPT_BATCH_WINDOWS=1. run.py prints it when it is not 0.
    never_backward: int = 0


def _payload(sysm):
    """Every package's checkpoint state, in one dict, through its OWN declared entry point.

    THE ROOT NEVER REACHES INTO A PACKAGE'S OBJECT TO BUILD THIS. Each value comes from the entry
    point that package declares for the purpose -- LM.state_dict, FAB.state_dict, CAP.state and so
    on -- because each of them knows what is derivable and must NOT be saved (LM's byte-index
    tables, SIG's lookahead queue) and what is earned and must be (DOM's reservoir, MEM's
    gate_theta, the two pin clocks on the valve). A root that assembled tensors itself would be a
    second opinion about what a resume needs, and the resume would believe whichever it read first.

    `payload` IS OPAQUE TO CKPT, which is why this is here and not there: ckpt/api.py::Snapshot
    declares it as such, and the package that writes the file has no business knowing what is in it.
    """
    cfg = sysm.configs
    _pos = sysm.clock.counters()
    return {
        "LM": lm_api.state_dict(cfg["LM"], sysm.model, sysm.geometry),
        "SIG": sig_api.state_dict(cfg["SIG"], sysm.sig),
        "FAB": fab_api.state_dict(cfg["FAB"], sysm.fabric),
        "WORLD": world_api.state_dict(cfg["WORLD"], sysm.world),
        "MEM": mem_api.state_dict(cfg["MEM"], sysm.store),
        "DOM": dom_api.state_dict(cfg["DOM"], sysm.partition),
        "CAP": cap_api.state(sysm.valve),
        "OPT": opt_api.state_dict(cfg["OPT"], sysm.optimizer),
        "DATA": data_api.stream_state(cfg["DATA"], sysm.areas),
        "TOK": tok_api.vocab_state(cfg["TOK"], sysm.vocab),
        # THE ROOT'S OWN STATE, UNDER A KEY NO PACKAGE OWNS, AND THE ONE EXCEPTION TO THE PARAGRAPH
        # ABOVE. System.token_seen is the per-token appearance counter the loop allocates and
        # advances (LM.anchor_term's `token_seen`, TOK.judge_probation's `appearances`); no package
        # owns it, so no package's state_dict can carry it, and until 2026-09-24 nothing did: every
        # resumed process started it at None, so LM.anchor_term held every minted row at full
        # weight again and judge_probation counted only post-resume appearances. The root is the
        # only thing that knows it exists, which is why the root writes it here and
        # spine/compose.py::compose puts it back.
        "LOOP": {"token_seen": (None if sysm.token_seen is None
                                else sysm.token_seen.detach().cpu().clone()),
                 # WHETHER THE MATCH TABLE MOVED SINCE THE LAST SEGMENTATION (2026-09-24): a
                 # resume re-segments at the saved table, so when this is True DOM's restored
                 # histograms were counted under a table the child's stream is not cut at, and
                 # the child's first roll must tell DOM (spine/compose.py, System.rev_at_last_seg).
                 "seg_table_moved": (sysm.rev_at_last_seg is not None
                                     and int(sysm.vocab.rev) != int(sysm.rev_at_last_seg))},
        # RUN'S STATE, THROUGH RUN'S OWN ENTRY POINTS (2026-09-24, Q-RUN-9 and Q-RUN-10). Nothing of
        # RUN crossed the boundary except the two numbers CKPT.save records itself (step, epoch), so
        # every cadenced gate re-seeded at the resumed step and fired a period late, and a resume
        # could not tell a boundary save from a mid-epoch one. `cadences` is Cadences.state() and
        # spine/compose.py puts it back through Cadences.restore; `clock` is the epoch position off
        # RunClock.counters(), which compose reads to warn about a mid-epoch replay.
        "RUN": {"cadences": sysm.cadences.state(),
                "clock": {"in_epoch": _pos["in_epoch"],
                          "windows_in_epoch": _pos["windows_in_epoch"]}},
    }


# DISAGREEMENTS BETWEEN THE TWO GEOMETRY PRODUCERS, COLLECTED ACROSS THE RUN AND SURFACED ONCE.
# Module level rather than per-call because _save runs on a cadence and a reader needs the fact
# once, not once per checkpoint; `run` drains it into RunResult.warnings.
_disagree = []
# CKPT.save's NON-FINITE REFUSALS, collected and drained into RunResult.warnings the same way
# (2026-09-24, Q-RUN-14). A refused save is not a stop: the run's own loss guard stops a nan
# loss, and a refusal here -- AdamW moments overflowed to inf by a huge-but-finite loss, say --
# leaves training running with the refusal said and the previous generation on disk untouched.
_save_refused = []


def _save(sysm, clock, reason, suffix=""):
    """One checkpoint, plus the tokenizer file that belongs to the SAME snapshot.

    THE VOCABULARY TRAVELS WITH THE SUFFIX OR THE SNAPSHOT CANNOT BE RESUMED FROM. P1-M46: a
    reason="bestN" save used to write runs/x.best3/ckpt.pt while the tokenizer always went to the
    BASE path, so the snapshot's recorded merge count stopped matching the file it names -- and
    resuming from it resolves d_vocab_read_path to a file nothing ever wrote, build_vocabulary
    falls through to "build", and the restored embedding table is indexed by a different
    vocabulary. TOK.save_vocabulary takes the same suffix for exactly this reason, so the two go
    out together, here, and cannot drift apart.
    """
    # THE RECORDED MANIFEST IS THE LIVE ONE PLUS WORLD'S GROWN COUNT, AND THE OVERLAY WAS MISSING.
    # compose.py's C row for WORLD.geometry: "IT IS THE OVERLAY, NOT THE RECORD ... the one thing
    # it genuinely adds is `n`, THE GROWN POPULATION -- the only quantity in this whole gate that
    # cannot be computed from frozen Configs ... this row supplies world.n on TOP of it,
    # recorded-only, reported UNCHECKED by the child's gate and re-refused in both directions by
    # WORLD.load_into (M43)."
    # RECORDING MORE THAN THE GATE CAN CHECK IS THE DESIGN AND NOT AN ACCIDENT.
    # compose.py::_geometry_manifest says the grown counts are absent from the LIVE manifest "for a
    # reason that cannot be engineered away here: WORLD.geometry(world, w) needs a BUILT world, and
    # the only build that could supply it is the one this gate exists to happen before", and that
    # check_geometry's contract "covers that case -- a field present in the checkpoint and absent
    # from the manifest is reported UNCHECKED, not skipped". So the asymmetry is deliberate: the
    # SAVE side records world.n, the GATE side cannot compute it and says UNCHECKED, and WORLD's own
    # loader re-refuses it. Until this line the save side did not record it either, so there was
    # nothing for the child to report as unchecked and nothing for M43 to be re-refused against.
    # `world.n` ONLY, WHICH IS WHAT THE ROW SAYS AND IS NOT THE SAME AS "the record it returns".
    # The C row: WORLD.geometry "returns SIX fields, five of which (lat, hid, route_d, nmax,
    # feedback) the live manifest already carries as world.*, so the one thing it genuinely adds is
    # `n`, THE GROWN POPULATION -- the only quantity in this whole gate that cannot be computed from
    # frozen Configs ... this row supplies world.n on TOP of it".
    # THE FIRST DRAFT OVERLAID ALL SIX AND THE RESUME REFUSED ITSELF ON THE NEXT RUN, which is how
    # the disagreement below was found. Two producers for `world.hid` returned 32 and 128 at the
    # shipped defaults, because world/api.py::geometry read it off `preds`, which is (n, lat, lat)
    # and carries no hid axis -- WORLD_HID is the ENCODER's width. That is fixed at the source now;
    # what stays here is the cross-check, because THE ROOT IS THE ONLY THING THAT SEES BOTH
    # PRODUCERS. A field with two producers and no comparison is the shape this whole tree is
    # organised against, and it stayed invisible for as long as one of the two was never called.
    wg = world_api.geometry(sysm.configs["WORLD"], sysm.world)
    recorded = dict(sysm.manifest)
    for _k, _v in wg.items():
        if _k not in recorded:
            recorded[_k] = _v
        elif recorded[_k][0] != _v[0]:
            _disagree.append(
                f"{_k}: the live manifest (spine/compose.py::_geometry_manifest, off the frozen "
                f"Config) says {recorded[_k][0]!r} and world/api.py::geometry (off the built "
                f"tensors) says {_v[0]!r}. Two producers for one recorded geometry field, "
                f"disagreeing, inside the instrument that decides whether a resume is allowed. The "
                f"manifest's value is the one recorded -- the gate compares against it and it is "
                f"the one an operator typed -- and this line is the only place the disagreement is "
                f"visible at all.")
    # THE RETENTION STATE TRAVELS WITH THE SNAPSHOT OR EVERY RESUME OVERWRITES ITS PARENT'S BEST.
    # ckpt/api.py::load reads `blob.get("best_state")` and CKPT.save did not put the key in the
    # blob, so Snapshot.best_state was None on every checkpoint this tree has ever written,
    # new_retention(restored=None) started cold, and the first post-resume probe satisfied "no best
    # yet". That is ISSUES P1-M45 exactly, live, and spine/compose.py's own C row for
    # CKPT.Retention.state names the consequence in advance. CKPT.save gained a DEFAULTED
    # `best_state` keyword for it, with a counter pair, because a defaulted argument is invisible
    # to K10.
    try:
        wrote = ckpt_api.save(sysm.configs["CKPT"], payload=_payload(sysm),
                              geometry=recorded, step=int(clock.step),
                              epoch=int(clock.epoch), reason=reason,
                              best_state=(None if sysm.retention is None
                                          else sysm.retention.state()),
                              suffix=suffix)
    except _gate.NonFinite as e:
        _save_refused.append(str(e))
        return False
    if wrote:
        tok_api.save_vocabulary(sysm.configs["TOK"], sysm.vocab, suffix=suffix)
    return wrote


def _window_bounds(ids, i, ctx):
    """The ONE cut, named once, as LOOP_ORDER requires. Window i is ids[i*ctx : (i+1)*ctx].

    THE +1 IS THE LANGUAGE MODEL'S AND IS WHY THIS RETURNS A PAIR: `y` is `x` shifted by one token,
    so a window needs ctx+1 ids to yield ctx inputs and ctx targets. A driver that cut ctx and then
    shifted inside the step would train the last token of every window against the first of the
    next, across a window boundary that DATA never promised was contiguous.
    """
    a = i * ctx
    b = a + ctx + 1
    if b > len(ids):
        return None
    return a, b


def _flush_bounds(batch):
    """The flush's (x, y) out of the accumulated window slices. ONE NAME, as the table says.

    The accumulator is a list of (a, b) pairs the driver appended per window; this is where they
    become tensors, and it is the only place they do.
    """
    return batch


def run(sysm, *, max_windows=None, progress=True):
    """Run the system. Returns RunResult.

    `max_windows` IS A DRIVER ARGUMENT AND NOT A LEVER, deliberately: RUN owns the shape of the run
    through epochs and DATA owns its length through the corpus, and a knob here that could cut a
    run short would be a second answer to "how long is this run" that no report reads. It exists so
    a smoke test can be a smoke test, and a run that stops because of it SAYS SO in warnings.
    IT COUNTS THE WINDOWS THIS CALL TRAINS, NOT THE CLOCK'S RUN TOTAL (2026-09-24, Q-RUN-10). It was
    compared against the absolute `tick.step`, which a resume restores, so every resumed run given
    --max-windows N <= its restored step trained exactly ONE window and stopped (driven: a 60-window
    parent resumed with --max-windows 40 printed '61 windows, 1 flushes'). A driver argument is
    about the process it is handed to. It is tested BEFORE the epoch roll, so a stop that lands on
    an epoch boundary stops there instead of drawing the next epoch and training one window of it.

    A CLOCK THAT HAS ALREADY FINISHED IS REFUSED BEFORE THE FIRST advance(). The first advance is a
    window of training; spine/compose.py refuses a resume of a finished run for that reason, and
    this is the same predicate (RunClock.counters' epoch against epochs_target) for a caller that
    hands this function a System by another route.

    A System CARRYING REFUSALS IS NOT RUN. Until 2026-09-24 run.py's read of System.refusals was
    the only stop, and a driver that called compose() and then this function trained through
    every refusal. compose() now raises spine/compose.py::RefusedRun itself, so a System it
    returns carries none; this guard is the same stop for a System that reaches here by another
    route (the `restored=` override, a test that appends a refusal), and it raises the same type.
    """
    if getattr(sysm, "refusals", None):
        raise _c_RefusedRun(sysm, f"loop.run (System built to stage {sysm.stage!r})")
    cfg = sysm.configs
    run_cfg, lm_cfg, tok_cfg = cfg["RUN"], cfg["LM"], cfg["TOK"]
    fab_cfg, sig_cfg, dat_cfg, opt_cfg = cfg["FAB"], cfg["SIG"], cfg["DATA"], cfg["OPT"]
    tok_cfg = cfg["TOK"]
    dom_cfg = cfg["DOM"]
    dom_cfg = cfg["DOM"]

    # WHAT CANNOT BE CALLED, DETERMINED ONCE, BEFORE THE FIRST WINDOW. Deciding per-flush would put
    # a branch on a stub check inside the hot loop and would let the answer change mid-run, which
    # is not a state any report could describe.
    # WHAT THIS DRIVER CALLS, WRITTEN DOWN, BECAUSE THE DRIVER IS THE ONLY THING THAT KNOWS.
    # THIS BLOCK ASKED THE WRONG QUESTION UNTIL 2026-09-17 AND THE ANSWER WENT FROM MISLEADING TO
    # FALSE THE DAY THE BODIES LANDED. It filtered LOOP_ORDER's B row through `_is_stub(fn)` --
    # "does this body raise NotImplementedError" -- and used it to answer "will this run invoke
    # it". The two agree only while every unwired mechanism happens also to be unwritten. P4 wrote
    # all eleven, `skipped` emptied, and the run printed "0 MECHANISM(S) ON LOOP_ORDER WERE NOT
    # CALLED" while `_flush` called exactly six entry points and not one of the eleven. Three
    # independent skeptics reported it within the hour, which is the correct outcome and not a
    # consolation: the report was WRONG, in the direction of claiming work that did not happen.
    #
    # THE FACT IS ABOUT THE DRIVER, SO IT IS STATED IN THE DRIVER. `_CALLS` is the set `_flush` and
    # `run` actually invoke; it is a literal because there is nothing to derive it from -- an AST
    # walk of this file would be a second parser answering a question the author of the call site
    # already knows. It is checked against the B row below, so a row this driver never calls cannot
    # be silently dropped from the report, and an entry in `_CALLS` that LOOP_ORDER does not list
    # raises rather than passing.
    rows = _rows_by_stage()
    every = set().union(*rows.values())
    # THE CROSS-CHECK RUNS IN BOTH DIRECTIONS AND OVER EVERY STAGE. A row this driver never calls
    # cannot be silently dropped from the report, and a name in `_CALLS` that LOOP_ORDER does not
    # list raises rather than passing -- which is what caught SIG.encode being filed as a B row on
    # this guard's very first run.
    stray = sorted(_CALLS_FLAT - every - _OFF_TABLE)
    if stray:
        raise RuntimeError(
            f"spine/loop.py::_CALLS names {stray}, which LOOP_ORDER does not list at any stage and "
            f"_OFF_TABLE does not excuse. One of the three is wrong, and a driver whose own record "
            f"of what it calls disagrees with the table is a driver whose report cannot be read.")
    # AND IN THE SAME DIRECTION PER STAGE, which the flat check cannot ask: a name this driver
    # claims to call AT A STAGE the table does not list it at is the mirror of the stray above and
    # is how a stage key drifts from the row it was copied from.
    misfiled = sorted(f"[{st}] {k}" for st in _CALLS for k in _CALLS[st] - rows.get(st, set()))
    if misfiled:
        raise RuntimeError(
            f"spine/loop.py::_CALLS files {misfiled} under a stage LOOP_ORDER does not list them "
            f"at. The stage is the WHEN, so a name under the wrong one credits a call that never "
            f"happens at that point in the loop -- which is the defect the per-stage split exists "
            f"to end.")
    # PER STAGE, BECAUSE A TOTAL HIDES WHICH PART OF THE LOOP IS MISSING. Stage E uncalled means
    # this driver runs one pass; stage A uncalled means the cadenced maintenance never happens;
    # stage C uncalled would mean the checkpoint is short a package. Those are three different
    # runs and one number cannot say which.
    uncalled = {st: sorted(rows[st] - _CALLS.get(st, frozenset()))
                for st in sorted(rows) if rows[st] - _CALLS.get(st, frozenset())}
    skipped = tuple(
        f"[{st}] {k}: {_WHY.get(k, 'not called by this driver')}"
        + ("" if not _is_stub(_entry(k)) else "  [and the body is still a P4 stub]")
        for st in sorted(uncalled) for k in uncalled[st])

    warnings = list(sysm.warnings)
    clock, cadences = sysm.clock, sysm.cadences
    _c_start = clock.counters()
    if int(_c_start["epoch"]) >= int(_c_start["epochs_target"]):
        raise RuntimeError(
            f"loop.run: the clock has already completed epoch {int(_c_start['epoch'])} of "
            f"epochs_target={int(_c_start['epochs_target'])} (step {int(_c_start['step'])}). The "
            f"first act of this loop is clock.advance(), which is a window of training the run was "
            f"not asked for; spine/compose.py refuses a resume of a finished run for the same "
            f"reason. Raise RUN_EPOCHS to continue from it.")
    # WHERE THIS CALL STARTED, so max_windows counts this call's windows (see the docstring).
    start_step = int(_c_start["step"])
    periods = {k: v for k, v in _periods_of(sysm).items()}
    model, pop, st = sysm.model, sysm.fabric, sysm.sig
    ctx = int(lm_cfg.ctx)
    vocab = sysm.vocab

    # THE PER-TOKEN APPEARANCE COUNTER, ALLOCATED ONCE AND CARRIED ON THE SYSTEM. compose.py's row
    # says it: "token_seen is the per-token appearance counter, carried on System.token_seen
    # because it is written every window and read at the flush. It is the SAME object
    # TOK.judge_probation takes as `appearances` -- one counter, two spellings, and C5 is the
    # record of what one counter under two names cost the last time."
    # COUNTING APPEARANCES AND NOT STEPS is what makes the anchor independent of re-segmentation:
    # `seen` only advances when a token turns up in a training batch, so a retok cannot move it.
    if sysm.token_seen is None:
        sysm.token_seen = torch.zeros(int(lm_cfg.vocab_slots), dtype=torch.float32,
                                      device=sysm.process.device)

    # THE ROOT'S ONE BOUND ENCODER, FORMED ONCE. compose.py::_key_fn says why it cannot arrive as
    # a return: "It is an entry point partially applied, not a return value, so no `produces` column
    # can hand it over without this file forming it -- and memory/api.py's whole point is that MEM
    # never imports LM." Formed here rather than per flush because a fresh lambda each time is a
    # fresh identity for a callable two entry points are required to share.
    key_fn = _c_key_fn(sysm)

    curve, t0 = [], time.time()
    saves = 0
    # THE EPOCH-LOCAL WINDOW INDEX. Zero at the start of every epoch, which is what makes the cut
    # and the signature slice index the segmentation that is currently loaded rather than the run's
    # cumulative window count. See the paragraph at the cut.
    win_in_epoch = 0
    # HOW MANY TOKENS WERE MINTED BY THE TIME OF THE LAST RE-SEGMENTATION. The segmentation this
    # loop starts on was cut by compose at the vocabulary as it stood then, so the mark starts at
    # the MINT COUNT THE RUN ENTERED WITH, not at 0 (2026-09-24). On a fresh run those are the same
    # number; on a resume tok.mint is the parent's count, carried by TOK's restore, and every one of
    # those tokens is in this stream -- driven: 6 parent mints, 1707 occurrences of their ids in the
    # resumed segmentation, and the end-of-run warning said all 6 "cannot appear". The roll below
    # moves the mark forward.
    _mint_at_last_roll = int(vocab.counters.get("tok.mint", 0))
    # THE MATCH TABLE'S REVISION AT THE LAST SEGMENTATION, which decides whether an epoch roll's
    # re-segmentation is a RETOK for DOM (see the DOM.on_retokenize call at the roll). `vocab.rev`
    # is the monotone counter Vocabulary._add, _retire and _reinstate all bump -- tokenize's own
    # staleness stamp reads it for the same question -- and it starts at the value compose's
    # segmentation was cut under, a resume's included.
    # ON A RESUME IT STARTS FROM WHAT THE CHECKPOINT SAID (2026-09-24): -1 when the parent's table
    # had moved since its last segmentation, so DOM's restored histograms are under a different
    # table from this stream's and the first roll must tell it; -2 when the checkpoint predates
    # that record, which starts from the live revision like a fresh run but is said at the roll.
    _seg_unknown = sysm.rev_at_last_seg == -2
    _rev_at_last_seg = (int(vocab.rev) if sysm.rev_at_last_seg in (None, -2)
                        else int(sysm.rev_at_last_seg))
    sysm.rev_at_last_seg = _rev_at_last_seg
    # THE PENDING-RETOK COUNT, AN int AND NOT A FLAG (2026-09-24). See where _flush raises it.
    if not sysm.retok_pending:
        sysm.retok_pending = 0
    # `did` IS SEEDED AT 0 AND IS NO LONGER A CONSTANT. It is overwritten by DOM.observe on every
    # window; the seed only covers the impossible case of a flush with no window in it.
    did = 0
    # THE PER-WINDOW ACCUMULATORS THE A STAGE FILLS AND THE FLUSH DRAINS. They are parallel to
    # `batch` and cleared with it, because a signature or a domain id that outlived its window
    # would be attributed to the next one -- the same hazard `batch = []` already guards.
    sigs, dids, samples = [], [], []
    # THE PREVIOUS FLUSH'S BATCH, CARRIED FOR MEM.maintain'S READ PROBE. It crosses backwards, like
    # System.novelty, and for the same reason: a `produces` column reads forwards only. It is a
    # LOCAL rather than a System slot because nothing outside this driver reads it and nothing
    # resumes from it -- a probe that started cold after a resume loses one flush of measurement
    # and no state.
    probe_prev = None
    # MEM'S PRESSURE VERDICT, None UNTIL THE FIRST CADENCED CENSUS. None is the honest seed and not
    # False: fabric/api.py::grow_check prints UNREACHABLE for None and "armed, did not fire" for
    # False, and before any census has run there is no measurement to call False.
    mem_pressure = None
    # DOM'S LIVE DOMAIN COUNT, CARRIED FROM THE dom.manage PASS'S CENSUS TO EVERY FLUSH -- FAB.forward's
    # `live_domains`, which the flush passed as the literal 1 until 2026-09-24. The same cadenced-
    # producer / per-flush-consumer shape as mem_pressure above, and LOOP_ORDER's DOM.census row
    # declares the staleness ("a B row takes live_domains every flush and this one runs on a cadence
    # that may never fire"). 1 UNTIL THAT PASS FIRST FIRES, which is the value max(1, ...) inside
    # FAB's breadth cap already floors to; fab.breadth_cap's gate prints the count it was handed, so
    # a run that never reached a census says so on that line (Q-FAB-9).
    live_domains = 1
    # THE DRIVER'S OWN DID-IT-FIRE BOOK, for the two facts no package can see because they are
    # about how THIS FILE joined a flush: loop.flush_mixed_domain (a flush whose windows span more
    # than one domain -- FAB.forward's breadth ban is batch-wide and is computed on dids[0], so
    # these are the flushes where it was another window's domain for some rows) and
    # loop.owners_from_domain (the control arms' MEM owner, see _flush). Each is SEEDED here, only
    # on the arm that can reach it and before any flush decides: flush_mixed_domain when
    # batch_windows > 1, owners_from_domain on FAB_ON=0 or FAB_NORM_ONLY=1. Printed at R.
    books = {}
    if int(opt_cfg.batch_windows) > 1:
        books["loop.flush_mixed_domain"] = 0
    if (not bool(fab_cfg.on)) or bool(fab_cfg.norm_only):
        books["loop.owners_from_domain"] = 0
    # THE PENDING RESEGMENTATION EVENT, set by the epoch roll and consumed by the next flush. None
    # on every other flush, which is what makes store.n_resegment_events a count of ROLLS.
    resegment = None
    # THE ROOT'S ONE BOUND SIG.encode, formed once: DOM.rekey's `encode`. domains/api.py::rekey
    # requires the SAME callable the live path used, or the partition drifts into two signature
    # spaces that do not compare.
    sig_encode = _c_sig_encode_fn(sysm)
    # SIG'S OWN ALPHABET STREAM, RESOLVED ONCE. _signature_stream returns Stream.bytes under
    # space="bytes" and Segmentation.ids under "tokens"; it is re-resolved at the epoch roll
    # because the roll replaces both of those objects.
    sig_stream = _c_signature_stream(sysm, st)
    # WINDOWS SINCE THE LAST DOMAIN BOUNDARY, which SIG.cadence_due takes to choose its dense arm.
    # Seeded at 0: before the first window there has been no boundary and no windows since one, and
    # the dense arm firing on the opening windows of a run is the intended reading.
    since_boundary = 0
    first_loss = last_loss = float("nan")
    # THE FLUSH LOSSES SINCE THE LAST FAB.manage PASS, whose mean is what that pass's depth plateau
    # test compares (see the manage call below for why a single flush cannot be).
    manage_losses = []
    batch = []
    ids = sysm.segmentation.ids
    stopped_early = False
    # WHICH EXIT ENDED THE LOOP, for the unflushed-batch accounting after it (F33, 2026-09-24).
    _end = "the loop"
    # RUN_PROFILE's INSTRUMENT, OPENED AROUND THE COMPONENTS BELOW (2026-09-24). RUN.mode has always
    # handed back a Timing whose span() is a shared no-op when profiling is off, and until this
    # date nothing in this file opened one, nor passed the Timing to RUN.bench_summary -- so
    # RUN_BENCH=1 RUN_PROFILE=1 printed "no per-component breakdown -- RUN_PROFILE is off" with
    # RUN_PROFILE on. Off, each span is contextlib.nullcontext and the run is bit-identical.
    _timing = sysm.mode.timing

    while True:
        tick = clock.advance()
        # THE CUT'S INDEX IS EPOCH-LOCAL AND `tick.step` IS NOT, AND THIS LINE READ `tick.step - 1`
        # UNTIL THE EPOCH ROLL WAS WIRED. RunClock.begin_epoch says which is which: "`step` is the
        # run's window total across every epoch -- it is what OPT's horizon is compared against --
        # while `_in_epoch` is how far into THIS stream the loop has read, which is the only
        # quantity a roll may zero." The clock keeps `_in_epoch` PRIVATE and Tick does not carry
        # it, so at epoch 1 the old spelling cut at `step * ctx` into a stream of the same length
        # and `_window_bounds` returned None on the FIRST window of the epoch -- the loop would
        # have warned that the segmentation ran out and stopped, one window into a second epoch it
        # had just correctly drawn.
        # THE LOOP KEEPS ITS OWN, AND THAT IS NOT A SECOND SOURCE FOR THE CLOCK'S. This file owns
        # THE CUT -- its module docstring says so and `_window_bounds` is here for that reason --
        # and the cut needs an offset into the CURRENT segmentation. The clock's `_in_epoch` is a
        # different question (has this window rolled the epoch) answered for a different consumer.
        # They agree by construction because both advance once per window and both zero at a roll.
        i = win_in_epoch
        win_in_epoch += 1
        bounds = _window_bounds(ids, i, ctx)
        if bounds is None:
            # THE WINDOW HAS NO MATERIAL, AND SINCE 2026-09-24 THAT IS ALWAYS A DEFECT (Q-RUN-12).
            # This branch used to name TWO causes and call the first arithmetic: the ONE-TOKEN TAIL,
            # when len(ids) was an exact multiple of ctx and `_windows_in_epoch` (then len // ctx)
            # declared a last window one target short. The window was skipped here, but the clock
            # had already counted it -- and on a flush tick it closed a flush with no backward
            # (6 flushes against 5 backward passes at OPT_BATCH_WINDOWS=1; at 2, a window that was
            # accumulated, never trained and never counted as dropped). `_windows_in_epoch` is now
            # (len(ids) - 1) // ctx, the number of windows that HAVE ctx + 1 ids, so that tail no
            # longer exists and what reaches here is a real disagreement between the epoch length
            # and the stream it was measured on. The window is skipped and the loop falls through
            # to the finished/rolled tail below, so the epoch can still roll.
            _short_by = (i * ctx + ctx + 1) - len(ids)
            warnings.append(
                f"loop: the segmentation ran out at window {i} of epoch "
                f"{int(tick.epoch) - (1 if tick.rolled else 0)} -- it is short by {_short_by} "
                f"(len(ids)={len(ids)}, ctx={ctx}). spine/compose.py::_windows_in_epoch counts "
                f"only windows with ctx+1 ids, so the epoch length and the stream it was measured "
                f"on disagree, which is a defect rather than arithmetic.")
        else:
            batch.append(bounds)
            # DOM.observe IS CALLED ONCE PER WINDOW, ABOVE THE BATCH EARLY-OUT, and that placement is
            # what makes `sustain` a Windows clock rather than a flush one -- domains/api.py::observe
            # says so, and `s.run` is incremented once per call. Putting it in the flush would divide
            # every domain clock by the batch width, silently, at every BATCH_W.
            # sample_window IS THE SAME OBJECT SIG.encode GETS, through the root's one slicer: a rekey
            # cannot reproduce the signature otherwise, so a second slice at this call site would be a
            # defect by construction.
            # DOM.observe IS THE ONLY PRODUCER OF A DOMAIN ID. This paragraph said "DOM.observe IS
            # NOT WIRED ... IT IS A TWELFTH STUB" until 2026-09-24, beside the call it describes:
            # observe has a body and is called here every window (part.n_windows equals the window
            # count). What it still guards against is its OFF state -- domains/api.py::observe:
            # "enabled == False returns did=0 for every window ... 0 is a real source id that MEM
            # sees, and the report must say 'the partition is off' rather than leaving the
            # per-source floor to protect exactly one source in silence."
            # A SECOND DEFECT WAS FOUND ON THE WAY AND IS RECORDED BECAUSE NOTHING ELSE WILL FIND IT:
            # spine/compose.py::_sample_window clamps its start at 0, so early in the stream it returns
            # a SHORT window -- 173 units against a frozen 192 on the first flush, measured -- and
            # sig/api.py::encode refuses exactly that ("no eval variant, no gist placeholder and no
            # fallback ... because the alternative measured a whole project's routing on one byte").
            # The helper returns a window its only consumer refuses, and until this loop called it
            # there was no consumer to find out. Padding would invent units the model has not consumed;
            # taking the units AHEAD of the cursor is what that helper's own docstring rules out. The
            # repair belongs in the root, which owns the slicer.

            # ---- ROW A, IN LOOP_ORDER'S OWN ORDER --------------------------------------------------
            # MEM.census -> DOM.manage -> DOM.census -> FAB.manage -> SIG.cadence_due -> SIG.train_step
            # -> SIG.encode -> DOM.observe -> DOM.rekey -> TOK.on_window. THIS WHOLE STAGE WAS UNCALLED
            # UNTIL 2026-09-21 and the ledger said so the entire time: 'dom.manage', 'dom.rekey' and
            # 'fab.manage' read checks=0 on every run ever taken, which is RUN.Cadences reporting that
            # the gate was never EVALUATED -- a different and worse fact than fires=0.
            #
            # THE CADENCED MAINTENANCE BLOCK. MEM.census is here and not only at R because it is
            # DOM.manage's PRODUCER: manage takes `memory_counts` and `mem_floor_entries` and nothing
            # else in the tree returns them. reconcile=False here -- the exact recount is the R stage's
            # one-shot repair, and running it every hundred windows would be an O(capacity) bincount on
            # a cadence nobody asked for.
            if cadences.due("dom.manage", periods["dom.manage"], clock):
                _c = mem_api.census(cfg["MEM"], sysm.store)
                _plan = dom_api.manage(dom_cfg, sysm.partition, now=tick.step,
                                       memory_counts=_c.counts, mem_floor_entries=_c.floor_entries)
                _pc = dom_api.census(dom_cfg, sysm.partition)
                # AND THE HALF OF THE PASS THAT TOUCHES THE STORE. DOM DECIDES, THE SPINE CARRIES,
                # MEM EDITS -- domains/api.py::Plan's first line is "the spine carries it to MEM;
                # this package touches no memory", and until this call existed the second half of
                # that sentence was true and the first was not. The old tree closed the same gap by
                # having the domain manager call mem.reassign_src()/mem.delete_src() and read
                # `int(mem.src_floor * mem.cap / max(1, mem._eligible().sum()))` inline at
                # self_organize.py:3688 -- a PRIVATE method, across a package boundary O10 forbids.
                # WHAT A PASS WITHOUT IT MEANT, and it is not "the merge did not take effect": DOM
                # renumbered its own partition while store.src kept the OLD ids, so every entry a
                # merged domain wrote became provenance filed under an id DOM no longer has, and
                # every entry a culled domain wrote stayed in the store forever with nothing left
                # to claim it. Both populations still counted toward the per-source floor that the
                # NEXT pass's cull brake is judged against -- store.n_orphan_sources is the number
                # that says how many, and it is the reading that goes to 0 here.
                # live_sources IS DOM.census's `live` AND NOT Plan.live, which is the wire LOOP_ORDER
                # declares on the DOM.census row ("its `live` list is what MEM.apply_domain_plan
                # takes as live_sources"). The two agree on a correct pass; the census is the one the
                # table names, and naming the other would be a wire recomputed at the call site under
                # a second spelling -- the defect self_organize.py:3688 is cited for one line up.
                # `_plan` AND `_pc`, NOT `_c`: `_c` is the MEM census this block opened with and
                # feeds mem_pressure three lines down.
                mem_api.apply_domain_plan(cfg["MEM"], sysm.store, folds=_plan.folds,
                                          deletions=_plan.deletions, live_sources=_pc.live)
                # AND THE OTHER HALF OF THE CENSUS ROW'S WIRE: n_live, under FAB.forward's spelling.
                live_domains = int(_pc.n_live)
                # AND THE PRESSURE VERDICT, CARRIED TO EVERY FLUSH UNTIL THE NEXT CENSUS. LOOP_ORDER's
                # B row for FAB.observe/grow_check names this shape exactly -- "memory_pressure from
                # MEM.census, which is a CADENCED producer feeding a per-flush required argument" -- so
                # the staleness is the table's design and not a shortcut. Calling census per flush
                # would materialise an 8192-entry dict and two capacity-wide reductions on every one of
                # a quarter-million flushes, to move a boolean that changes on the scale of eviction
                # pressure.
                mem_pressure = _c.pressure
            # FAB.manage: THE SELECTION PASS, AND THE LAST LOOP_ORDER ROW TO ACQUIRE A CALLER.
            # Growth ran and pruning did not, so the population only ever ROSE -- 570 births over
            # 634 windows at the shipped defaults, 569 of them from the spawn door, saturating
            # FAB_SLOTS at about window 2,300 of a quarter-million-window run. Culling is what
            # makes that a steady state instead of a ceiling.
            # `flush_loss` IS THE MEAN FLUSH LOSS SINCE THE PREVIOUS PASS AND None BEFORE THERE IS
            # ONE. It feeds step 6's depth curriculum only; passing a NaN would make the plateau
            # test compare against a value that is not a number and silently never deepen, which is
            # the shape of defect this tree spends its comments on. IT WAS THE LAST FLUSH'S RAW LOSS
            # UNTIL 2026-09-24, against FAB_DEPTH_EPS's own help ("improvement in the SMOOTHED flush
            # loss"): over the last 100 flushes of a default 300-window run one flush's loss has a
            # standard deviation of 1.61 nats (2.32 bits) against a threshold of 0.01 bits, so the
            # plateau test compared two draws of noise 500 windows apart. The mean over the ~500
            # flushes between passes is the smoothing the lever names; NaN flushes are left out.
            if cadences.due("fab.manage", periods["fab.manage"], clock):
                _ml = (sum(manage_losses) / len(manage_losses)) if manage_losses else None
                manage_losses = []
                with _timing.span("fab.manage"):
                    fab_api.manage(fab_cfg, pop, step_windows=tick.step, flush_loss=_ml)
            # SIG'S OWN CADENCE AND ITS STEP, WHICH ARE ONE MECHANISM AND LAND TOGETHER. Until
            # SIG.train_step had a body neither was asked, because asking a gate RECORDS its fire
            # and a fire nobody can act on is thrown away -- tok/api.py::on_window's rule ("asking
            # under a shared key CONSUMES the event"). Both are called now.
            # THIS IS THE ONLY PLACE THE ENCODER IS STEPPED IN THE LOOP. OPT.maybe_step writes `lr`
            # into the encoder optimizer's param groups and deliberately does NOT step it
            # (Q-OPT-6), and opt.encoder_steps_here is the tripwire that MUST stay 0 -- a nonzero
            # value means both sites are stepping, which makes SIG's floor and its three cadence
            # levers inert by construction. `opt` is OptState.encoder and nothing wider: before
            # that field had a name the root handed over the whole OptState, an object through
            # which this package could have stepped the language model.
            # `windows_since_boundary` IS A PREVIOUS-ITERATION VALUE BY CONSTRUCTION, which is what
            # domains/api.py::Assignment means by "`boundary` IS CONSUMED BACKWARDS": SIG's row
            # sits ABOVE DOM.observe's, so the count read here is the one DOM last reset and never
            # this window's own answer.
            # `seen_units` IS THE CURSOR AT THIS WINDOW'S FIRST BYTE -- ordinal `i`, the windows reached
            # BEFORE this one -- for the same reason the signature's is (Q-FAB-7): the window about to
            # be predicted is not yet material the loop has trained on, so an encoder step that could
            # draw it as an anchor would put this window's own text into the weights that then encode
            # its routing signature. It read `win_in_epoch` (i + 1) until 2026-09-24.
            if sig_api.cadence_due(sig_cfg, st, step_windows=tick.step,
                                   windows_since_boundary=since_boundary):
                with _timing.span("sig.train_step"):
                    sig_api.train_step(sig_cfg, st, stream=sig_stream,
                                       seen_units=_c_signature_cursor(sysm, st, i),
                                       opt=sysm.optimizer.encoder)
            #
            # SIG.encode, PER WINDOW, WHICH IS WHERE THE TABLE PUTS IT -- immediately above DOM.observe.
            # It used to be called once per FLUSH from inside _flush, off a second slice of the corpus;
            # both of those are now here, and `sample` is the ONE object both consumers take.
            # EPOCH-LOCAL FOR THE SAME REASON THE CUT IS: _signature_cursor multiplies `at_window` by
            # LM.ctx and indexes Segmentation.byte_pos, and `sysm.segmentation` is THIS epoch's.
            # THE ORDINAL IS `i`, THE CUT'S OWN 0-BASED INDEX, SO THE SAMPLE ENDS AT THIS WINDOW'S FIRST
            # BYTE -- AND IT WAS `win_in_epoch` (i + 1) UNTIL 2026-09-24, WHICH ROUTED EVERY WINDOW ON
            # ITS OWN TARGETS (Q-FAB-7). The ordinal counts windows REACHED, and the window being cut
            # here has not been reached: its logits are computed before anything trains on it. At
            # i + 1 the sample ended at byte_pos[(i + 1) * ctx], the last target's first byte, so it
            # covered the whole window -- measured at window 149 of a default run, x bytes
            # [28402, 28599) against a sample over [28407, 28599). Every position was routed, and
            # DOM.observe assigned the domain id FAB.forward bans on, from text the model was about to
            # be scored on predicting, and no generation path can reproduce a signature of text it has
            # not generated yet. At `i` the sample is the width_units units BEFORE the window, which
            # a generator holding the same prompt has in hand.
            sample = _c_sample_window(sysm, st, i)
            samples.append(sample)
            with _timing.span("sig.encode"):
                sig_i = sig_api.encode(sig_cfg, st, [sample])[0]
            if sig_i.device != sysm.process.device:
                sig_i = sig_i.to(sysm.process.device)
            sigs.append(sig_i)
            # DOM.observe: THE ONLY PRODUCER OF A DOMAIN ID IN THE TREE. Until it had a body every
            # window was domain 0 and the fabric's per-domain books, its breadth ban and MEM's
            # per-source floor all saw exactly ONE source. domains/api.py::Assignment says the loop
            # must take its `did` from here: "memory provenance (MEM.write's `sources`), the
            # expert-to-domain affiliation (FAB.forward's and FAB.observe's `domain_id`) and
            # DOM.note_competence's `did` are all the same id under three spellings, and a loop that
            # keeps a literal 0 makes all three see one source."
            with _timing.span("dom.observe"):
                asg = dom_api.observe(dom_cfg, sysm.partition, signature=sig_i,
                                      sample_window=sample,
                                      tokens=ids[bounds[0]:bounds[0] + ctx], now=tick.step)
            did = int(asg.did)
            dids.append(did)
            # THE BOUNDARY COUNTER SIG READS NEXT WINDOW. Zeroed on a boundary and incremented
            # otherwise, so the value SIG.cadence_due sees above is always the PREVIOUS window's --
            # the ordering domains/api.py::Assignment declares, not an accident of where this sits.
            since_boundary = 0 if bool(asg.boundary) else since_boundary + 1

            # DOM.rekey RE-ENCODES EVERY DOMAIN'S RESERVOIR WITH THE LIVE ENCODER, and it is what
            # MEASURES the acceptance radius: `radius` reads 0.0 for every domain until it runs, and so
            # does the POOLED radius, which it also measures. So on a run without it -- every
            # SIG_MODE=bigram run, where the arm test below skips it -- DOM_RADIUS_Q, DOM_RADIUS_MULT
            # and DOM_RADIUS_CAP are set-but-inert and every radius-arm re-entry is decided against
            # DOM_SPAWN_DIST (part.n_bootstrap_spawn_dist is the counter that says so; driven on
            # bigram over 260 windows: 98 of them, part.n_bootstrap_radius 0). Before this learned
            # arm's first rekey the same holds for it. `encode` is the root's ONE bound SIG.encode, for the reason
            # domains/api.py::rekey gives: a rekey that used a second encoder puts the partition into
            # two signature spaces that do not compare.
            # HERE, AFTER DOM.observe, AND IT RAN FIRST IN THIS BLOCK UNTIL 2026-09-24 -- above
            # FAB.manage, SIG.train_step, SIG.encode and DOM.observe, against its own row ("AFTER
            # observe, so the window that just triggered a boundary is inside the sample its own
            # radius is measured from"). Driven at the first fire of a default run (window 200): the
            # order was dom.manage, rekey, train_step, encode, observe -- so the partition was re-keyed
            # against an encoder SIG.train_step moved again within the same window, which is the drift
            # a rekey exists to remove. After observe the rekey sees this window's reservoir sample
            # and the encoder as this window's train step left it.
            # AND ONLY ON THE LEARNED ARM, which is the row's second test and was not made at all:
            # "the arm test is SIG.mode == 'learned', so BOTH are evaluated HERE" (the old line is
            # `if SIG_MODE == "learned" and SELF_ORG: asm.rekey(enc)`, self_organize.py:6689).
            # SIG_MODE=bigram is the frozen hashed-bigram CONTROL, and every number recorded for it
            # was taken without a rekey; SIG_MODE=bigram over 260 windows read n_rekey_passes 1. The
            # arm is tested BEFORE the cadence is asked, because Cadences.due RECORDS a fire when it
            # answers True, and a fire nothing acts on would print 'dom.rekey' firing on a run where
            # no partition was re-keyed; checks=0 is the honest ledger reading on that arm
            # (docs/04_CONTRACT.md Q-DOM-3).
            if (str(sig_cfg.mode) == "learned"
                    and cadences.due("dom.rekey", periods["dom.rekey"], clock)):
                dom_api.rekey(dom_cfg, sysm.partition, encode=sig_encode)

            # ---- ROW A CONTINUED: TOK'S FOUR CADENCES, ASKED ONCE PER WINDOW ------------------------
            # ASKED HERE AND ACTED ON AT THE FLUSH, which is the whole of Q-TOK-12. batch_windows Dues
            # reach one flush and the root ORs them PER CADENCE KEY, because `_due` RECORDS the step
            # when it answers True: a Due a flush discards is a fire that is silently GONE, at a rate of
            # gcd(period, batch_windows)/batch_windows -- half of all mints at grow_every=200 with
            # batch_windows=16, and 15 of every 16 at any period coprime with the batch.
            # THE OR IS THE ROOT'S BECAUSE THE ROOT IS THE ONLY THING THAT CAN SEE A BATCH, and it is
            # written with dataclasses.replace on the record TOK returned rather than by naming
            # tok_api.Due: this file receives records from packages and reads them, and the ruling that
            # settled the OR also said "`Due` keeps its four fields and no signature moves".
            # `frozen` COMES FROM THE LAST WINDOW, which is the same value as the OR because it is a
            # monotone STATE and not an event -- at step >= freeze_at it is True from then on.
            with _timing.span("tok.on_window"):
                due = tok_api.on_window(tok_cfg, vocab, ids[bounds[0]:bounds[1]], step=tick.step)
            if sysm.due is None:
                sysm.due = due
            else:
                prev = sysm.due
                # tok.due_merged: A FLUSH WHERE MORE THAN ONE WINDOW RAISED THE SAME KEY.
                # UNREACHABLE AT THE SHIPPED batch_windows=1, where no two windows share a flush, and
                # on any arm where TOK asks no cadence at all. So it is SEEDED HERE, in the branch
                # only a second window of a batch reaches and before the test that decides, and only
                # when TOK seeded one of the three cadence counters -- which is TOK's own statement
                # that a Due can be raised on this arm, read off its book rather than re-derived
                # from its levers. TOK.on_window seeded it unconditionally until 2026-09-24, so the
                # shipped configuration printed present-and-0 for a key this comment calls
                # unreachable.
                if any(k in vocab.counters for k in ("tok.due_mint", "tok.due_retok",
                                                     "tok.due_probation")):
                    vocab.counters.setdefault("tok.due_merged", 0)
                merged = ((prev.mint and due.mint) or (prev.retok and due.retok)
                          or (prev.probation and due.probation))
                if merged:
                    vocab.counters["tok.due_merged"] = vocab.counters.get("tok.due_merged", 0) + 1
                sysm.due = dataclasses.replace(
                    prev, mint=prev.mint or due.mint, retok=prev.retok or due.retok,
                    probation=prev.probation or due.probation, frozen=due.frozen)

            if tick.flush_due:
                if "loop.flush_mixed_domain" in books and len(set(dids)) > 1:
                    books["loop.flush_mixed_domain"] += 1
                try:
                    with _timing.span("flush"):
                        loss, per_window, probe_prev = _flush(
                            sysm, batch, ctx, model, pop, st, lm_cfg, fab_cfg, sig_cfg, opt_cfg,
                            vocab, clock, sysm.novelty, did, key_fn, sigs, dids, probe_prev,
                            mem_pressure, resegment, live_domains, books)
                except _gate.NonFinite as _nf:
                    # THE LAST FINITE STATE IS KEPT IF IT IS FINITE, for the reason a raising R stage
                    # still saves (Q-RUN-9): a stop is a reason to distrust what comes next, not to
                    # lose what came before. _flush raised before the optimizer stepped, so the
                    # parameters and moments are the previous flush's; CKPT.save scans the payload
                    # and refuses (NonFinite again) if anything in it is not finite -- a forward
                    # that poisoned a FAB centroid on its way to the nan loss is caught there.
                    _n_ref = len(_save_refused)
                    _kept = _save(sysm, clock, "final")
                    _why = _save_refused[_n_ref:]
                    del _save_refused[:]
                    raise _gate.NonFinite(
                        f"{_nf} "
                        + ("The pre-step state was finite and WAS saved as the final checkpoint "
                           "(reason 'final'), so a resume at a lower OPT_LR continues from the last "
                           "finite parameters." if _kept else
                           f"CKPT.save REFUSED the final checkpoint as well: {_why[-1]}" if _why else
                           "CKPT_DIR names no directory, so nothing was saved.")) from _nf
                # `resegment` IS CONSUMED ON THE FIRST FLUSH AFTER A ROLL AND NOT ON EVERY ONE. It is
                # an EVENT: memory/api.py::maintain drops and retakes its rekey snapshot each time it
                # is non-None, so leaving it set would restart that walk every flush and the amortized
                # rekey would never complete a pass -- n_rekey_passes pinned at 0 with n_rekey_slices
                # climbing, which reads exactly like a cadence that is working.
                resegment = None
                # NOVELTY CROSSES BACKWARDS, WHICH IS WHY IT LIVES ON THE SYSTEM AND NOT IN A RETURN.
                # compose.py's row says it: "novelty is the PREVIOUS flush's mean surprise
                # (self_organize.py:7499), carried on System.novelty because it crosses backwards and
                # `produces` reads forwards only". The loop is the only thing that can carry it, so the
                # loop writes it here, after the flush that measured it.
                # IT IS SURPRISE AND IT WAS THE PER-WINDOW LOSS UNTIL THIS EDIT, which is a defect the
                # MEM.write wiring found rather than a refinement. fabric/api.py::forward declares
                # "novelty: (B,) surprise from the previous step", the archive line the row cites is
                # `surprise = 1 - pm.gather(-1, y...)` and `_fab_nov = float(surprise.mean())`
                # (self_organize.py:683-685), and a cross-entropy in nats is a DIFFERENT QUANTITY on a
                # different scale: 8.3 at the start of a run against a surprise that cannot leave
                # [0, 1]. It is fed straight into `nov_proj`, a Linear(1, dk), so the router's query was
                # being biased by a number an order of magnitude outside the range that layer was
                # initialised for -- and nothing could have caught it except forming the real quantity
                # for the consumer that names it.
                sysm.novelty = per_window
                batch, sigs, dids, samples = [], [], [], []
                if loss is not None:
                    last_loss = loss
                    if curve == []:
                        first_loss = loss
                    curve.append(loss)
                    if loss == loss:
                        manage_losses.append(float(loss))

            # THE PERIODIC CHECKPOINT, THROUGH THE SAME Cadences EVERY OTHER GATE USES. A 53-minute
            # run finished with `ckpt checks=0` -- the gate was never EVALUATED, so nothing was written
            # and the trained weights were lost at process exit. That is what this call is: not a
            # refinement, a repair. It is evaluated per window rather than per flush because the period
            # is in WINDOWS and Cadences.due is phase-independent by construction.
            if cadences.due("ckpt", periods["ckpt"], clock):
                with _timing.span("ckpt.save"):
                    saves += 1 if _save(sysm, clock, "periodic") else 0
            # AND THE SIGUSR1 FLAG, DRAINED ONCE PER WINDOW. CKPT.install_save_signal armed it at
            # compose; take() returns True exactly once per `kill -USR1`, so a checkpoint is written on
            # demand without the run being stopped to get one.
            if sysm.save_flag is not None and sysm.save_flag.take():
                saves += 1 if _save(sysm, clock, "sigusr1") else 0

            if progress and cadences.due("progress", periods["progress"], clock):
                print(f"[{int(tick.step)} windows] loss={last_loss:.4f} "
                      f"opt_steps={int(clock.counters()['opt_steps'])} "
                      f"n_live={int(pop.n_live)} vocab={int(vocab.size())} "
                      f"uncalled={len(skipped)}", flush=True)

        if tick.finished:
            _end = "the finishing epoch roll"
            break
        # THE DRIVER'S STOP, TESTED BEFORE THE ROLL AND COUNTED IN THIS CALL'S WINDOWS (2026-09-24,
        # Q-RUN-10). It sat after the roll's `continue` and compared the absolute clock step, so a
        # stop landing exactly on an epoch boundary drew the next epoch and trained one window of it
        # (driven: max_windows=157 on a 157-window epoch ran 158 and saved at epoch 1, one window
        # in), and every resume given N <= its restored step trained one window. Stopping here, at
        # a boundary, leaves the clock at the new epoch with in_epoch 0, so the final checkpoint IS
        # a boundary checkpoint and its child draws that epoch's stream from window 0.
        if max_windows is not None and int(tick.step) - start_step >= int(max_windows):
            stopped_early = True
            warnings.append(f"loop: stopped at max_windows={int(max_windows)} window(s) trained by "
                            f"THIS process (the clock reads step {int(tick.step)}"
                            + (f", resumed at {start_step}" if start_step else "")
                            + "), which is a DRIVER argument and not a lever -- this run is "
                              "shorter than RUN.epochs and DATA asked for, and no report line "
                              "should be read as a full run.")
            _end = "max_windows"
            break
        if tick.rolled:
            # ---- STAGE E: THE EPOCH ROLL. DATA.draw_stream -> TOK.tokenize -> begin_epoch
            # -> DOM.on_retokenize (only when the match table moved) -------------------------
            # THIS DRIVER RAN A SINGLE PASS AND STOPPED HERE UNTIL 2026-09-22, and stage E's three
            # rows were three of the six the report listed as having no call site at all.
            # IT IS TESTED AFTER `finished` AND THAT ORDER IS THE CONTRACT'S. train/api.py::Tick:
            # "`finished` is tested BEFORE `rolled`. Both can be True on one advance -- at the
            # shipped RUN_EPOCHS=1 the only roll a run ever takes is exactly that one -- and a
            # caller that tests `rolled` first re-enters the stage-E rows to draw a stream for an
            # epoch the run has already finished." So at RUN_EPOCHS=1 this block is UNREACHABLE,
            # and it is exercised at RUN_EPOCHS=2.
            #
            # THE PARTIAL BATCH IS DISCARDED FIRST, AND THIS IS THE LINE THAT WOULD OTHERWISE BE A
            # SILENT DEFECT. `batch` holds (a, b) TOKEN BOUNDS into the OLD segmentation, and
            # `sigs` / `dids` / `samples` hold that segmentation's material; a flush after the roll
            # would cut the NEW ids at the OLD offsets and train on a batch spanning two
            # tokenizations. Nothing would raise -- the bounds are in range -- and the loss would
            # simply have been measured on text nobody assembled.
            if batch:
                warnings.append(
                    f"loop: {len(batch)} window(s) were accumulated and not flushed when epoch "
                    f"{int(tick.epoch)} began. DISCARDED rather than carried: their token bounds "
                    f"index the previous epoch's segmentation. At OPT_BATCH_WINDOWS=1 this cannot "
                    f"happen; above 1 it costs up to batch_windows-1 windows per epoch.")
            batch, sigs, dids, samples = [], [], [], []
            win_in_epoch = 0
            # probe_prev IS DROPPED FOR THE SAME REASON ONE LAYER OVER: a tensor of token ids under
            # a segmentation that has just been replaced, which MEM.read would encode as current.
            probe_prev = None
            # THE DRAW. `epoch=clock.epoch` is the row's own spelling and it is read INSIDE
            # draw_stream -- data/api.py owns whether dat.resample makes this a different stream --
            # so the root passes the number and never the decision.
            sysm.stream = data_api.draw_stream(dat_cfg, sysm.areas, sysm.plan,
                                               epoch=int(tick.epoch), seed=int(run_cfg.seed))
            # THE RE-SEGMENTATION, AND IT IS WHAT FINALLY LETS A MINTED TOKEN BE USED. Every id
            # minted during the previous epoch is in `vocab`'s match table, so tokenize() emits
            # them here -- the first route in this tree by which a token the run invented can
            # appear in the run's own training data. Until this line the loop warned, at the end of
            # every run, that its mints were real and unusable.
            prev_n = len(ids)
            sysm.segmentation = tok_api.tokenize(
                tok_cfg, vocab, sysm.stream.bytes, sysm.stream.labels,
                regularize=True, seed=int(run_cfg.seed))
            ids = sysm.segmentation.ids
            # SIG'S STREAM IS RE-RESOLVED, because _signature_stream returns Stream.bytes or
            # Segmentation.ids and the roll has just replaced both. A stale binding would train the
            # encoder on the previous epoch's material while the loop trains on this one's.
            sig_stream = _c_signature_stream(sysm, st)
            # THE LENGTH ARRIVES AS A COUNT OF WINDOWS, which is begin_epoch's own requirement --
            # "never as a byte budget divided by a token window" -- and the division is named once,
            # at compose.py::_windows_in_epoch, because what separates the right form from the
            # wrong one is WHICH STREAM was divided and no type states that.
            clock.begin_epoch(_windows_in_epoch_of(sysm))
            # AN EPOCH RESAMPLE IS A SELF-INFLICTED SHIFT, AND THIS IS THE FIRST THING IN THE TREE
            # EVER TO STAMP ONE. fabric/api.py::grow_check suppresses BOTH growth legs for
            # `cooldown` windows after a shift, because "A SHIFT WE CAUSED IS NOT NEW MATERIAL"
            # (Q-FAB-6) -- and until this line fab.shift_notifications read 0 on every run, which
            # that counter declares to mean the blackout is UNREACHABLE rather than armed.
            # compose.py names three stamping sites; this is the E draw row's.
            # ONE EVENT, TWO TYPED STAMPS, AND BOTH ARE NOW MADE (2026-09-24). The row has always
            # said "the root also stamps clock.opt_steps here as the shift_at OPT.maybe_step
            # consumes", and until this date only the Windows twin was stamped: maybe_step was
            # called with no shift_at, so OPT_LR_SHIFT_WARM re-warmed nothing on any multi-epoch
            # run. Both packages count one notification per distinct stamp, so handing the same
            # stamp over on every later flush is a re-delivery and not a new event.
            sysm.shift_at_windows = U.Windows(int(clock.step))
            # THE STEP THE SHIFT APPLIES TO, NOT THE STEPS ALREADY TAKEN (2026-09-24). maybe_step
            # increments st.opt_step BEFORE it prices the step, so the first step after this roll
            # is clock.opt_steps + 1; stamping clock.opt_steps made `step - shift_at` start at 1,
            # the ramp skip its first rung and re-warm W-1 steps, and OPT_LR_SHIFT_WARM=1 fully
            # inert on a run whose shift was delivered (driven: notifications 1, shift_warm_applied
            # 0). The old tree stamped the step it then priced (self_organize.py:6519, :4819).
            sysm.shift_at_steps = U.Steps(int(clock.opt_steps) + 1)
            # AND MEM IS TOLD, because every context it holds is token ids under a segmentation
            # that no longer exists. maintain's `resegment` arm drops and retakes the rekey
            # snapshot and counts the event; it deliberately does NOT rewrite the stored ids,
            # because that needs an old-id -> new-id mapping "not declared anywhere" (its words)
            # and inventing one would rewrite every stored token under a guess. The stale ids stay
            # visibly stale, which is what store.n_resegment_events exists to make readable.
            resegment = sysm.segmentation
            # AND DOM IS TOLD, WHEN THE MATCH TABLE MOVED SINCE THE LAST SEGMENTATION -- the
            # RetokEvent's DOM destination, which had no call site until 2026-09-24: this roll
            # re-segmented at the grown vocabulary and DOM never heard, so DOM_TOKC_DECAY was inert
            # in every configuration, DOM.prior blended counts from two segmentations, and
            # part.n_retok_events was ABSENT on an arm that had just re-segmented -- this tree's
            # spelling of "unreachable" (driven: RUN_EPOCHS=2 DATA_RESAMPLE=1, vocabulary 518,
            # on_retokenize calls 0). domains/api.py::on_retokenize decays every domain's token
            # histogram because "a retok makes the same text into DIFFERENT ids".
            # GATED ON THE TABLE HAVING MOVED, AND MEM IS NOT, ON PURPOSE. A roll whose vocabulary
            # did not change since the last segmentation (no mint, retirement or reinstatement:
            # `vocab.rev` unmoved) cuts the new text into the SAME ids the histograms were counted
            # under, so decaying them would discard counts that are still valid. MEM is told on
            # every roll because what it holds is token ids AND BYTE OFFSETS into the previous
            # epoch's stream, which the redraw invalidates whether or not the table moved. A roll
            # that did not tell DOM says so in the warning below; part.n_retok_events counts the
            # rolls that did (docs/04_CONTRACT.md Q-DOM-2).
            # part.n_retok_events IS SEEDED BY THE ROOT AT EVERY ROLL, BEFORE THE TEST (2026-09-24),
            # as tok.due_merged is: a roll that did not re-cut the table is a delivery that was
            # armed and did not fire, and on_retokenize seeds the key only when it is called, so
            # that arm printed ABSENT -- "unreachable" -- on a run that could retok and had rolled.
            sysm.partition.counters.setdefault("part.n_retok_events", 0)
            _resumed_stale = _rev_at_last_seg == -1
            _dom_told = int(vocab.rev) != _rev_at_last_seg
            if _dom_told:
                dom_api.on_retokenize(dom_cfg, sysm.partition)
            _rev_at_last_seg = int(vocab.rev)
            sysm.rev_at_last_seg = _rev_at_last_seg
            _unknown_note = (" THIS PROCESS RESUMED FROM A CHECKPOINT THAT PREDATES THE RECORD of "
                             "whether its table moved since its last segmentation, so whether the "
                             "restored histograms were counted under this table is UNKNOWN."
                             if _seg_unknown else "")
            _seg_unknown = False
            # EVERY PENDING RETOK IS SATISFIED BY THIS ROLL, because the roll IS the act: the
            # stream was just re-segmented with the vocabulary as it now stands. ADDED AS A COUNT
            # AND NOT AS ONE (2026-09-24): retok_pending counts the fires, and this counter
            # incremented once per ROLL, so on RUN_EPOCHS=2 DATA_RESAMPLE=1 TOK_RETOK_EVERY=10 it
            # read 1 against 41 deferred and Q-RUN-8's measurement -- compare it with
            # tok.retok_deferred -- could not be taken. Zeroed here so that what survives to the
            # end of the run is only the fires no roll ever reached, and
            # retok_satisfied_by_roll + that remainder == tok.retok_deferred.
            # THE MINT HIGH-WATER MARK AT THIS ROLL. Everything minted up to here is in the
            # vocabulary the re-segmentation just used, so it IS in the stream from this epoch on;
            # anything minted after the last roll is not. One number, captured where the fact is
            # made, rather than a claim re-derived at the end of the run.
            _mint_at_last_roll = int(vocab.counters.get("tok.mint", 0))
            if "tok.retok_deferred" in vocab.counters:
                vocab.counters["tok.retok_satisfied_by_roll"] = \
                    vocab.counters.get("tok.retok_satisfied_by_roll", 0) + int(sysm.retok_pending)
            sysm.retok_pending = 0
            warnings.append(
                f"loop: epoch {int(tick.epoch)} began -- redrew the stream and re-segmented at "
                f"vocabulary size {int(vocab.size())} ({prev_n} -> {len(ids)} ids). Every memory "
                f"entry written before this point holds token ids and byte offsets under the "
                f"PREVIOUS segmentation and is NOT rewritten; MEM.maintain is told, drops its "
                f"rekey snapshot and counts the event. "
                + ("DOM.on_retokenize is told: the PARENT's histograms were counted under a match "
                   "table this process's stream was never cut at (the resume re-segmented at the "
                   "saved, grown vocabulary), so DOM_TOKC_DECAY is applied to every domain's token "
                   "histogram."
                   if _dom_told and _resumed_stale else
                   "DOM.on_retokenize is told: the match table moved since the last segmentation, "
                   "so DOM_TOKC_DECAY is applied to every domain's token histogram."
                   if _dom_told else
                   "DOM.on_retokenize is NOT told: the match table has not moved since the last "
                   "segmentation (no mint, retirement or reinstatement), so the new text is cut "
                   "into the ids DOM's token histograms were counted under and they stay valid."
                   + _unknown_note))
            continue

    # THE PARTIAL BATCH AT THE END IS SAID, WHICHEVER EXIT LEFT IT (2026-09-24). The finishing roll
    # drops a partial batch into RunClock's dropped_windows exactly as a mid-run roll does, but
    # `finished` is tested before `rolled`, so the mid-run roll's warning below the break was
    # unreachable at the finish; and a max_windows stop leaves a partial batch no roll counts at
    # all. Driven at OPT_BATCH_WINDOWS=16 DATA_STREAM_BYTES=30000: 157 windows, 9 flushes, 13
    # windows that never reached a backward, and no line anywhere said so -- the summary printed
    # 157 windows as the run's length and throughput. One check here covers both exits, and
    # RunResult.never_backward carries the count run.py prints.
    _unflushed = len(batch)
    _dropped_here = int(clock.counters()["dropped_windows"])
    never_backward = _dropped_here + (_unflushed if _end == "max_windows" else 0)
    if _unflushed:
        warnings.append(
            f"loop: {_unflushed} window(s) were accumulated and never flushed when the run ended "
            f"({_end}); they are counted in `windows` and never reached a backward pass. "
            f"{never_backward} window(s) in all never reached one in this process (RunClock "
            f"dropped_windows {_dropped_here}"
            + (f" + {_unflushed} left by the max_windows stop" if _end == "max_windows" else "")
            + f"). At OPT_BATCH_WINDOWS=1 this cannot happen; above 1 it costs up to "
              f"batch_windows-1 windows per exit.")
    batch, sigs, dids, samples = [], [], [], []

    # THE FINAL SAVE, UNCONDITIONALLY, WHATEVER ENDED THE RUN. A run that stops because the epoch
    # finished, because max_windows was reached, or because the stream ran out has all done the
    # same amount of training, and losing it in the last two cases would make the driver's own
    # argument the difference between a kept model and a discarded one.
    # saving_on IS NOT RE-TESTED HERE: CKPT.save asks it and returns False, counting refused_off,
    # which is the reading that makes "0 saves" distinguishable from "saving is off".
    # WHAT THE DEFERRAL ACTUALLY COST, COUNTED ONCE AT THE END. A retok raised and never reached
    # by a roll is a fire that is gone -- Q-TOK-12's tok.due_dropped, which it says must read 0 --
    # so the two counters are kept apart: `tok.retok_deferred` is how many were raised, and
    # `tok.due_dropped` is how many of those the run never satisfied. At RUN_EPOCHS=1 they are
    # equal by construction (on a fresh run), because the only roll a single-epoch run takes is the
    # one that also finishes it and `finished` is tested first.
    # THE REMAINDER IS ADDED AS A COUNT (2026-09-24). This added 1 when a pending FLAG was set, so
    # TOK_RETOK_EVERY=10 over 45 windows read tok.retok_deferred 4 against tok.due_dropped 1 -- the
    # "equal by construction" above was false on the first run anyone checked it on.
    _unreached = int(sysm.retok_pending or 0)
    if _unreached:
        vocab.counters["tok.due_dropped"] = vocab.counters.get("tok.due_dropped", 0) + _unreached
        warnings.append(
            f"loop: {_unreached} retok(s) were raised and no epoch roll reached them before the "
            f"run ended, so the stream was never re-segmented for them (tok.due_dropped counts "
            f"each). At RUN_EPOCHS=1 that is every retok the run raises: the single roll a "
            f"one-epoch run takes is the one that also finishes it, and Tick requires `finished` "
            f"to be tested first. Raise RUN_EPOCHS (with DATA_RESAMPLE on, which the composition "
            f"root refuses to run without) to give the mints a route into the data.")
        sysm.retok_pending = 0
    # WHAT THE MINTS ACTUALLY DID, AND THE ANSWER CHANGED WHEN STAGE E LANDED. This block used to
    # say, of every token the run minted, that NONE of them could appear in its training stream --
    # true while the segmentation was built once and never rebuilt, and FALSE the moment the epoch
    # roll started re-segmenting at the current vocabulary. Measured on a three-epoch run: epoch 2
    # re-segmented at vocabulary 518 and the id count went 13,429 -> 13,202 for the same bytes,
    # which is the minted tokens being spent.
    # WHAT IS STILL TRUE IS NARROWER AND IS THE ONLY THING NOW CLAIMED: a token minted AFTER THE
    # LAST RE-SEGMENTATION has had none since it was born, so it is stranded exactly as before. The
    # re-segmentations are the epoch rolls AND the one compose cut this process's first stream
    # with, which on a resume already holds every token the parent minted -- the mark this counts
    # from starts there (see where _mint_at_last_roll is seeded). On a fresh RUN_EPOCHS=1 run that
    # is every mint the run makes, because the one roll a single-epoch run takes is the one that
    # also finishes it.
    _minted = int(vocab.counters.get("tok.mint", 0))
    _stranded = _minted - _mint_at_last_roll
    if _minted and _mint_at_last_roll:
        warnings.append(
            f"loop: {_minted} token(s) were minted (the run's total, a resumed parent's included); "
            f"{_mint_at_last_roll} of them were in the vocabulary at the last re-segmentation -- an "
            f"epoch roll, or the segmentation this process started on -- and ARE in this run's "
            f"training stream, because both segment at the vocabulary as it then stands.")
    if _stranded:
        warnings.append(
            f"loop: {_stranded} token(s) were minted AFTER THE LAST RE-SEGMENTATION and cannot "
            f"appear in this run's training stream -- their rows are initialised and a resume "
            f"carries them (a resumed run segments at the restored vocabulary, so they reach the "
            f"data there), but nothing has re-segmented since they were born. On a fresh "
            f"RUN_EPOCHS=1 run that is every mint the run makes: the single roll a one-epoch run "
            f"takes is the one that also finishes it, and Tick requires `finished` to be tested "
            f"first.")

    # THE R STAGE RUNS BEFORE THE FINAL SAVE, WHICH IS WHAT ITS OWN ROW ASKS FOR AND WHAT THIS
    # DRIVER DID BACKWARDS. LOOP_ORDER's ("R", "CKPT", "save") row reads: "the third route into the
    # C block: reason='final'. It runs AFTER the counters above so the checkpointed counter vectors
    # are the ones the report printed." The save was at this line and the report was built at the
    # return statement, so every final checkpoint this tree has written carries counters taken
    # BEFORE the R stage -- and the R stage is not a passive read: MEM.census(reconcile=True)
    # recounts the per-source census exactly and bumps n_census_reconciles, so the blob's census
    # and the report's census were two different numbers by construction.
    # ONE elapsed_s FOR BOTH, MEASURED HERE. RUN.bench_summary's throughput and RunResult.elapsed_s
    # were read at two different instants with a 130MB torch.save between them, so the run length
    # the report quoted and the one the throughput was computed from disagreed by the cost of the
    # save. They are now the same number, and it is the TRAINING time: a throughput figure that
    # includes the checkpoint is measuring the disk, which is the reason sweep_gpu.sh sets no
    # CKPT_DIR at all.
    elapsed_s = time.time() - t0
    # A RAISING R STAGE STILL SAVES FIRST (2026-09-24, Q-RUN-9). The order above is the row's and
    # is kept, but several R entry points ASSERT -- OPT.counters raises on a broken accumulation
    # invariant -- and with the save after them a failed assertion threw the trained weights away
    # with the report: the mid-accumulation resume that raised there wrote no checkpoint at all.
    # An invariant failure is a reason to distrust the run, not to lose it; the save is taken with
    # the counters as they stand and the exception is re-raised unchanged.
    try:
        report = _report(sysm, elapsed_s, ctx)
    except Exception:
        _save(sysm, clock, "final")
        raise
    # THE DRIVER'S OWN BOOK. An empty dict is a statement too -- neither mechanism was reachable on
    # this arm (batch_windows=1 and a routed fabric) -- so it is printed with that sentence rather
    # than as nothing.
    report["LOOP(flush books)"] = dict(books) if books else (
        "no key is reachable on this arm: loop.flush_mixed_domain needs OPT_BATCH_WINDOWS > 1 and "
        "loop.owners_from_domain needs FAB_ON=0 or FAB_NORM_ONLY=1")

    final_written = _save(sysm, clock, "final")
    for _d in dict.fromkeys(_disagree):
        warnings.append(f"loop: recorded-geometry disagreement -- {_d}")
    _disagree.clear()
    _refused_here = list(_save_refused)
    del _save_refused[:]
    for _r in _refused_here:
        warnings.append(f"loop: a checkpoint was NOT written -- {_r}")
    saves += 1 if final_written else 0
    if not final_written and not _refused_here:
        warnings.append(
            "loop: no final checkpoint was written -- CKPT_DIR names no directory, so saving is "
            "off and this run's weights end with the process. Set CKPT_DIR to keep them.")

    c = clock.counters()
    return RunResult(
        windows=int(c["step"]), windows_here=int(c["step"]) - start_step,
        opt_steps=int(c["opt_steps"]), flushes=int(c["flushes"]),
        epochs=int(c["epoch"]), loss_first=first_loss, loss_last=last_loss,
        loss_curve=tuple(curve), elapsed_s=elapsed_s, skipped=skipped,
        gated=_gate_report(sysm) + (
            f"CKPT.save: {saves} checkpoint(s) written by this run (periodic, SIGUSR1 and the "
            f"final one together); 0 means CKPT_DIR names no directory and saving is off",),
        report=report,
        cadence_ledger=cadences.ledger(), warnings=tuple(warnings),
        never_backward=never_backward)


# ---- THE R STAGE: the did-it-fire surfaces, asked through the entry points that own them --------
# EIGHT OF THE THIRTEEN R ROWS, AND THE FIVE THAT ARE MISSING ARE MISSING FOR ONE REASON EACH. This
# is the stage LOOP_ORDER puts after the last window, and until this function nothing ran it: a
# 262,601-window run printed a loss and a cadence ledger and NOTHING about whether an expert was
# born, a token minted or an entry written. The counters existed the whole time; no caller asked.
# WHY EACH ONE IS ASKED THROUGH ITS PACKAGE'S ENTRY POINT rather than read off the object: every
# one of these renders the three-state form (`fired N` / `armed but 0` / `unreachable (predicate)`)
# out of a flat counters dict PLUS that package's Gate objects, and the predicate's arithmetic is
# the package's own. Reading `pop.counters` here would give the numbers and drop the reachability,
# which is the half that distinguishes "set but inert" from "not set".
# TWO OF THE THREE ENTRIES HERE WENT FALSE UNDER THEIR OWN REPAIRS AND ARE GONE (2026-09-22).
# "MEM.census: a P4 stub" and "DOM.census: a P4 stub, and so is DOM.observe above it" were both
# true when written; both bodies exist, both are called at A on the dom.manage cadence and both are
# now called HERE with the arguments their R rows name. A list of what is missing is exactly the
# kind of text that rots into a claim about a repair that already landed, which is the defect class
# this file spends its comments on, so the two lines are deleted rather than annotated.
_R_MISSING = (
    "EVAL.*: the whole package is deferred; its holdout probe has no logits_fn that spans "
    "FAB.forward, which is the same missing join that deferred FAB.contribution.",
)


def _report(sysm, elapsed_s, ctx):
    """The R stage, as {row: rendering}. Asked once, after the last window.

    RUN.bench_summary TAKES THE LIVE bytes_per_window AND NOT THE SEED'S. ISSUES P1-L42 is a
    throughput number initialised at the SEED vocabulary and refreshed only inside an instrument's
    cadence, so a short run quoted kB/s at a vocabulary it had long since grown past -- a RUN-owned
    number whose correctness depended on an INSTRUMENT's clock. Segmentation.bytes_per_token is the
    live figure and `ctx` is the window, so the product is this run's.
    """
    cfg = sysm.configs
    out = {}
    out["LM.counters"] = lm_api.counters(cfg["LM"], sysm.model)
    out["SIG.counters"] = sig_api.counters(cfg["SIG"], sysm.sig)
    out["FAB.counters"] = fab_api.counters(cfg["FAB"], sysm.fabric)
    out["OPT.counters"] = opt_api.counters(cfg["OPT"], sysm.optimizer)
    out["CAP.counters"] = cap_api.counters(cfg["CAP"], sysm.valve)
    out["TOK(vocab.counters)"] = dict(sysm.vocab.counters)
    # AND TOK'S GATES, WHICH NO ROW RENDERED (2026-09-24). tok.probation_embed is the gate
    # judge_probation seals to say the embed test could not run -- "unreachable (no residual_ratio
    # supplied)", ISSUES P1-M41's repair -- and with it unrendered, TOK_PROBATION_BY=embed at
    # LM_COMPOSE=0 printed only "TOK.judge_probation: fired 2 time(s)" while no token was judged.
    # tok.build_passes_advice rides along. Same shared three-state form as MEM's and DATA's rows.
    out["TOK(vocab.gates)"] = (
        {f"gate:{k}": v for k, v in _gate.three_state(sysm.vocab.gates).items()}
        if getattr(sysm.vocab, "gates", ()) else "no TOK gates: the vocabulary carries none")
    # MEM.census(reconcile=True) IS CALLED BEFORE store.counters IS COPIED, AND THE ORDER IS THE
    # REPAIR (2026-09-24). The copy was taken first, so the census's own bump of
    # store.n_census_reconciles reached the checkpoint and not the report: the report printed
    # n_census_reconciles ABSENT beside a census row reading 1, while the final checkpoint's
    # /payload/MEM/counters held 1 -- against the save row's own words, "the checkpointed counter
    # vectors are the ones the report printed". The row it renders is still built further down,
    # where the reasons for it are written; only the CALL moved.
    _mc = mem_api.census(cfg["MEM"], sysm.store, reconcile=True)
    out["MEM(store.counters)"] = dict(sysm.store.counters)
    # WORLD HAD NO LINE IN THIS REPORT AT ALL, and it is the package that turned out to supply 45%
    # of the gradient on the language model's token embedding. It declares no counters() entry
    # point -- it is the third package without one, after TOK and MEM -- so the dict is read off
    # the record the same way and spelled the same way, `WORLD(w.counters)`, which is what says
    # the root took it rather than asked for it. What it makes readable: world.built (live against
    # null, the D4 distinction the class docstring calls its whole point), world.loss_terms.calls,
    # world.latent_std -- the COLLAPSE reading, and the one number that says whether an arm that
    # improved the loss did so by flattening the latent -- and world.forecast.*, which since the
    # call site landed (Q-WORLD-10) reads world.forecasts == lm.encode.extra_applied == flushes at
    # the defaults, and world.forecast.inert == calls with world.forecasts ABSENT at
    # WORLD_FEEDBACK=0. The forecast's size RELATIVE to h is LM's lm.encode.extra_ratio, in the
    # LM.counters line above.
    out["WORLD(w.counters)"] = dict(sysm.world.counters)
    # MEM.census AT R, WITH reconcile=True, WHICH IS THE ROW AND WHICH NOTHING CALLED. The A-stage
    # census runs on the dom.manage cadence with reconcile=False -- the exact recount is an
    # O(capacity) bincount and does not belong on a cadence -- so the settled numbers and
    # `census_drift` had no producer. Drift is the whole point: the incremental per-source census
    # is maintained by _commit_window and the exact one is `src & active`, and the difference
    # between them is how "s779 (-2 now, peaked 111230)" gets printed. The counters dict above is
    # NOT this: it carries the tallies, this carries the reconciliation.
    # WHY IT WAS INVISIBLE: spine/loop.py::_CALLS was one flat set, so the A-stage call spent the
    # name "MEM.census" for every stage at once and the run printed uncalled=0.
    # (`_mc` is the call made above, before store.counters was copied.)
    out["MEM.census(reconcile=True)"] = {
        "floor_entries": int(_mc.floor_entries), "live_src": int(_mc.live_src),
        "quota_arm": str(_mc.quota_arm), "pressure": _mc.pressure,
        "probation_share": round(float(_mc.probation_share), 4),
        "nsrc": int(_mc.nsrc), "nsrc_max": int(_mc.nsrc_max),
        # THE PER-SOURCE TABLE IS NOT PRINTED, and that is a size decision rather than a judgement:
        # `counts` is capacity-wide. Its WIDTH is the reading that belongs here.
        "sources_holding_entries": sum(1 for v in _mc.counts.values() if int(v) > 0),
        "census_drift": _mc.census_drift, "n_census_reconciles": int(_mc.n_census_reconciles),
    }
    # AND THE SEVEN mem.* GATES, WHICH THIS ROW DROPPED (2026-09-24). StoreCensus.gates exists so
    # "the numbers cross the boundary and the reachability" does too -- its own docstring -- and
    # this row copied the numbers and left `.gates` on the record: mem.probe, mem.rekey,
    # mem.pressure, mem.probation, mem.use_decay, mem.write_target and mem.key_depth reached no
    # report, so an armed-but-starved rekey read the same as an unreachable one and
    # MEM_WRITE_MODE=adaptive missing its target by 2x printed nothing. Rendered through
    # spine/gate.py::three_state, the shared form, because MEM has no counters() entry point to
    # render them in and the driver may not import FAB's private renderer.
    out["MEM.census(reconcile=True)"].update(
        {f"gate:{k}": v for k, v in _gate.three_state(_mc.gates).items()})
    # DATA'S STREAM GATES, READ OFF sysm.stream AT R AND NOT OFF A REFERENCE TAKEN AT COMPOSE: stage
    # E redraws the stream on every epoch roll, and a cached one would report epoch 0's draw.
    # data/api.py::Stream declares `gates` the DID-IT-FIRE surface for data.contig_wrap and
    # data.resample, and until this row nothing read that surface -- a DATA_SEG_CONTIG=1 or
    # DATA_RESAMPLE=1 run printed the same report as the default.
    out["DATA(stream.gates)"] = (
        {f"gate:{k}": v for k, v in _gate.three_state(sysm.stream.gates).items()}
        if sysm.stream is not None and getattr(sysm.stream, "gates", ()) else
        "no Stream gates: the stream carries none")
    # THE LAST FAB.grow_check CALL'S GATES. GrowReport was a bare expression statement's return
    # value until 2026-09-24 and its per-call gates reached nothing; spine/loop.py::_flush now keeps
    # the gates tuple -- never the record -- on System.grow_gates. Rendered as its own row because a
    # GrowReport gate may share a name with a FAB.build gate that FAB.counters prints, and the two
    # are verdicts about different things (per call against per run).
    out["FAB.grow_check(last call's gates)"] = (
        {f"gate:{k}": v for k, v in _gate.three_state(sysm.grow_gates).items()}
        if sysm.grow_gates else
        "no FAB.grow_check call in this process, or its record carried no gates")
    # DOM.census AT R -- "the partition's did-it-fire surface, and the domain sizes every verdict is
    # keyed by". Same history as the row above and the same repair. Until this line the partition
    # had NO report line but DOM.prior(0), so a run said nothing about how many domains it ended
    # with, how many boundaries it saw, or whether the acceptance radius had ever been measured.
    # DOM.prior IS CALLED BEFORE part.counters IS COPIED, for the reason the MEM copy above moved:
    # the copy was the census's snapshot, taken before prior bumped part.n_prior_reads, so the
    # report printed that key ABSENT on a run that had just read the prior -- the key's own
    # meaning of "never called". Both calls are made first and the rows are built after.
    _dc = dom_api.census(cfg["DOM"], sysm.partition)
    # DOM.prior FOR EVERY LIVE DOMAIN, AND IT WAS did=0 ALONE UNTIL 2026-09-24. The row asks for "one
    # of the ids DOM.census's `live` list carries", and the literal 0 dated from when every window
    # WAS domain 0: once DOM.observe assigned real ids, 0 could be a culled domain and the report
    # printed "no histogram, weight 0.0" while every live domain's prior was accumulated and weighted
    # at 0.15. Taken over the FULL live list, not the 32 the census row prints, so each read bumps
    # part.n_prior_reads -- which is therefore the number of R-stage reads, one per live domain.
    _live = [int(d) for d in _dc.live]
    _priors = {d: dom_api.prior(cfg["DOM"], sysm.partition, did=d) for d in _live}
    out["DOM.census"] = {
        "n_live": int(_dc.n_live), "live": list(_dc.live)[:32], "boundaries": int(_dc.boundaries),
        "created": _dc.created, "merged": _dc.merged, "culled": _dc.culled, "folded": _dc.folded,
        "held": _dc.held, "spared": _dc.spared, "emptied": _dc.emptied,
        "pooled_radius": round(float(_dc.pooled_radius), 6),
        "partition_off": bool(_dc.partition_off), "collapsed_at": _dc.collapsed_at,
    }
    out["DOM(part.counters)"] = dict(sysm.partition.counters)
    # ONE SUMMARY OVER THE LIVE DOMAINS (called above, before the copy). Rendered as counts of the
    # pair the entry point returns rather than as the histograms: (None, 0.0) is "off" at
    # DOM_PRIOR_BLEND=0 and "empty" above it, and both are different facts from a histogram of
    # zeros. `weight` is the value prior() returns beside a histogram; with no live domain holding
    # one it is None, because prior() returns 0.0 for an empty domain on EVERY arm and printing
    # that would read as DOM_PRIOR_BLEND=0 -- the driver does not read DOM's lever to fill the gap.
    # `consumed_by` SAYS WHAT NO OTHER LINE DOES: the prior is accumulated every window
    # (part.n_prior_accumulated) and NOTHING BLENDS IT INTO A PREDICTION -- its consumer is the eval
    # battery, deferred in spine/compose.py::DEFERRED_ENTRY_POINTS -- so a weight of 0.15 here is the
    # weight it WOULD be blended at, and these R-stage reads are the only reads it gets.
    # THE OFF ARM IS READ OFF DOM's OWN BOOK AND RENDERED AS OFF (2026-09-24). At DOM_PRIOR_BLEND=0
    # prior() returns (None, 0.0) on its off branch and never seeds part.n_prior_empty, and DOM.observe
    # never seeds part.n_prior_accumulated -- so both are ABSENT -- yet this row printed n_empty =
    # n_live, weight None and "read only by this R-stage row" about a histogram nobody accumulated.
    _with = [d for d, (p, _) in _priors.items() if p is not None]
    if "part.n_prior_accumulated" not in sysm.partition.counters:
        out["DOM.prior(live)"] = {
            "off": "nothing accumulated: part.n_prior_accumulated is ABSENT in DOM's book (the "
                   "accounting switch, DOM_PRIOR_BLEND, is 0), so no domain has a prior to read",
            "n_live": len(_live), "n_off": len(_live),
        }
    else:
        out["DOM.prior(live)"] = {
            "weight": float(_priors[_with[0]][1]) if _with else None,
            "n_live": len(_live), "n_with_histogram": len(_with),
            "n_empty": len(_live) - len(_with),
            "consumed_by": "nothing in training: the histogram is read only by this R-stage row; "
                           "its blend into a prediction belongs to the deferred eval battery",
        }
    if sysm.retention is not None:
        out["CKPT.Retention.counters"] = sysm.retention.counters()
    # THE CLOCK'S OWN BOOK, WHICH _CALLS HAS LONG LISTED AS AN R CALL AND NOTHING RENDERED UNTIL
    # 2026-09-24: dropped_windows (partial batches discarded at a roll, the finishing one included)
    # and batch_len were published "so the drop is readable" (train/api.py::RunClock.counters) and
    # reached no report, and only RUN.bench_summary -- off by default -- quoted dropped_windows.
    out["RUN.RunClock.counters"] = {k: (int(v) if hasattr(v, "n") else v)
                                    for k, v in sysm.clock.counters().items()}
    bench = run_api.bench_summary(
        cfg["RUN"], sysm.clock, elapsed_s=elapsed_s,
        bytes_per_window=int(ctx * float(sysm.segmentation.bytes_per_token)),
        n_params=sum(int(t.numel()) for t in sysm.base_params), timing=sysm.mode.timing)
    # THE SPANS ARE RENDERED HERE TOO, because bench_summary prints nothing at RUN_BENCH=0 and
    # RUN_PROFILE is a separate switch: profiling without bench would otherwise time the components
    # and print them nowhere. Seconds, summed over the run; "flush/..." spans nest inside "flush".
    if sysm.mode.profile:
        out["RUN.Timing.spans"] = {k: round(float(v), 3)
                                   for k, v in sorted(sysm.mode.timing.spans().items())} or (
            "RUN_PROFILE=1 and no span was entered")
    # None IS THE OFF ARM AND IS RECORDED AS SUCH. bench_summary "PRINTS INSTEAD OF the eval
    # battery", so it returns None rather than empty lines at RUN_BENCH=0 -- a caller that got []
    # would print a heading with nothing under it.
    out["RUN.bench_summary"] = bench if bench is not None else "RUN_BENCH=0: off"
    out["R ROWS WITH NO PRODUCER"] = _R_MISSING
    return out


def _windows_in_epoch_of(sysm):
    """compose.py::_windows_in_epoch, reached without importing compose at this module's top level.

    THE DIVISION IS NAMED ONCE, THERE. `(len(Segmentation.ids) - 1) // LM.ctx` and `stream_bytes // ctx`
    are both ints and both would wrap as units.Windows; what separates them is WHICH STREAM was
    divided, and no type states that -- which is why RunClock.begin_epoch takes a bare count and
    refuses a Clock, and why this driver must not write the division itself.
    """
    from spine import compose as _c
    return _c._windows_in_epoch(sysm)


def _periods_of(sysm):
    """compose.py::_periods, reached without importing compose into this module's top level."""
    from spine import compose as _c
    return _c._periods(sysm)


def _flush(sysm, batch, ctx, model, pop, st, lm_cfg, fab_cfg, sig_cfg, opt_cfg, vocab, clock,
           novelty, domain_id, key_fn, sigs, dids, probe_prev, mem_pressure, resegment,
           live_domains, books):
    cfg_world = sysm.configs["WORLD"]
    cfg_dom = sysm.configs["DOM"]
    cfg_mem = sysm.configs["MEM"]
    cfg_cap = sysm.configs["CAP"]
    tok_cfg = sysm.configs["TOK"]
    """One flush: cut the batch, forward, loss, backward. Returns the scalar loss, or None.

    THE ORDER IS LOOP_ORDER's B ROW, minus the rows whose entry points are stubs -- and the caller
    has already recorded which those are, by name, so this function's silence about them is not
    the report's silence about them.
    """
    _timing = sysm.mode.timing      # RUN_PROFILE's spans; a shared no-op when profiling is off
    ids = sysm.segmentation.ids
    pairs = _flush_bounds(batch)
    # THE BATCH IS CUT ONTO THE PROCESS DEVICE, NOT ONTO THE DEFAULT ONE. RUN.process_setup
    # resolved the device once and every module was built with `.to()` targeting it; a batch made
    # with a bare torch.tensor() lands on the CPU regardless, so at RUN_DEVICE=cuda the model is on
    # the GPU and its inputs are not. That is an immediate device-mismatch raise at the first
    # matmul -- not a silent slowdown, but a crash on the first flush of every GPU run, which is
    # the whole of what this driver had been tested against (CPU, where the two agree by accident).
    dev = sysm.process.device
    x = torch.tensor([ids[a:a + ctx] for a, b in pairs], dtype=torch.long, device=dev)
    y = torch.tensor([ids[a + 1:b] for a, b in pairs], dtype=torch.long, device=dev)

    # THE EMBEDDING IS TAKEN BEFORE THE ENCODER AND IT IS NOT encode()'s INPUT REUSED.
    # WORLD.loss_terms takes obs_emb, "the lowest layer, the point where a new sense plugs in", and
    # its docstring refuses three other producers by name -- encode(n_layers=0) returns the full
    # GRU hidden on the gru arm and embedding-PLUS-positional on the transformer arm, and the root
    # reaching for model.emb is an AttributeError at lm.compose=1. LM.embed is the producer that
    # exists for this.
    # THE AUTOCAST IS ENTERED HERE AND IT WAS NEVER ENTERED AT ALL UNTIL 2026-09-21.
    # RUN.process_setup builds `Process.autocast` -- torch.autocast on cuda at RUN_AMP=bf16,
    # contextlib.nullcontext otherwise -- and NOTHING IN THIS TREE CALLED IT. So RUN_AMP=bf16
    # resolved, reported amp_state="active", printed "the LM step runs under torch.autocast" on
    # run.py's banner, and the step ran in fp32. That is the exact defect class this whole project
    # exists to refuse: a lever that is set, REPORTED AS ACTIVE, and does nothing.
    # BOTH HALVES OF IT WERE PREDICTED IN WRITING AND NEITHER PREDICTION COULD FIRE.
    # train/api.py::Process says of its own three reporting fields that "it becomes a real defect
    # the day a banner prints tf32_applied and amp_state" -- and run.py began printing both on
    # 2026-09-17, which is the day it named. train/levers.py says the mechanism
    # is "STRUCTURALLY UNTESTABLE ON CPU, and that is a property of the lever rather than a gap in
    # the suite ... There is no test that can catch a regression here". Both were right, and what
    # found it was a MEASUREMENT ON THE CARD: sweep_gpu.sh's `amp` arm returned a loss curve
    # BIT-IDENTICAL to `base` (8.4163 -> 4.2922 on both) and `xf_amp` bit-identical to `xf`. bf16
    # carries 8 mantissa bits against fp32's 24; two runs agreeing to four decimals after 400
    # optimizer steps did not differ in arithmetic at all.
    # WHAT IS INSIDE: the LM step, which is the lever's own scope -- "Autocast precision for the LM
    # step". Embed, the world forecast and encode here; the fabric, the decode, the loss, the world
    # terms and the anchor in the second block below.
    # WHAT IS OUTSIDE, AND EVERY EXCLUSION IS THE CONTRACT'S RATHER THAN CAUTION:
    #   SIG.encode, which is why this is TWO blocks and not one. train/levers.py's carve-out is
    #   about "the one place in the step where reduced precision changes BEHAVIOUR rather than
    #   speed" -- retrieval by dot product over normalised vectors -- and the signature is the
    #   other vector in this step consumed exactly that way: FAB routes on dot products against
    #   expert centroids and DOM assigns by distance to domain centroids. It is also not "the LM
    #   step": SIG's encoder is its own parameter group in OPT.build. Two context entries per flush
    #   is the price of saying so, and it is a few microseconds.
    #   MEM.write's key_fn, which is the carve-out the lever NAMES (":5719-5723 MUST SURVIVE THE
    #   PORT: memory keys are retrieved by dot product over normalised keys ... An autocast that
    #   swallows the key path turns a retrieval system into a noisier one with no error anywhere").
    #   It is satisfied BY PLACEMENT -- the memory block sits below the backward, outside both
    #   contexts -- so moving MEM.write up into either block would reintroduce it in silence.
    #   THE BACKWARD, which is torch's own documented rule: autocast wraps the forward and the
    #   loss, and the backward runs in the dtypes the forward recorded.
    cast = sysm.process.autocast
    with cast():
        obs_emb = lm_api.embed(lm_cfg, model, x)
        # THE FORECAST IS LM.encode's `extra` (Q-WORLD-10, RESOLVED 2026-09-24). None at
        # WORLD_FEEDBACK=0 and on the null world, which encode already accepts, so the off arm is
        # this tree before the call site existed, bit for bit. world_proj is born ZERO, so the
        # first call adds exactly nothing (flush-0 loss 8.354218 wired and unwired, seed 0) while
        # world_proj's own gradient is nonzero from that first backward.
        h = lm_api.encode(lm_cfg, model, x,
                          extra=world_api.forecast(cfg_world, sysm.world, obs_emb))
    # THE SIGNATURE IS REAL OR THE CALL RAISES, AND THE FIRST DRAFT OF THIS BLOCK SWALLOWED IT.
    # It read `try: sig_vec = sig_api.encode(...) except Exception: sig_vec = None`, and then
    # skipped FAB.forward when the result was None -- so the fabric silently left the forward path
    # and NOTHING in RunResult said so. That is the exact shape sig/api.py::encode spends its
    # opening paragraph refusing ("a caller that cannot supply width_units units gets an EXCEPTION,
    # never a narrower window and never a zero vector", the whole of the C4/C5 repair), reproduced
    # in the one file that decides what runs. It also hid the actual fault, which was mundane: the
    # call passed `ctx` ids (128) where SIG asks for `width_units` UNITS (192).
    #
    # THE UNITS ARE BYTES UNDER space="bytes", AND THE SEGMENTATION IS WHAT MAPS TO THEM.
    # byte_pos[t] is the byte offset of token t, so a window that starts at token `a` starts at
    # byte byte_pos[a], and the signature reads the width_units bytes that END there -- the text
    # BEFORE the window, in the alphabet SIG was built for. THIS PARAGRAPH USED TO SAY "the same
    # text the window is made of", and until 2026-09-24 that was what the loop fed the router: the
    # window's own targets (Q-FAB-7, and the paragraph at the A stage's SIG.encode call).
    # THE SIGNATURES ARE THE A STAGE'S AND ARE NOT RE-ENCODED HERE. SIG.encode is a ROW A entry
    # point sitting IMMEDIATELY ABOVE DOM.observe in LOOP_ORDER, and this function used to call it
    # itself off a second slice of the corpus -- which made the driver hold TWO SLICERS for a value
    # whose entire contract is that there is one.
    # WHAT THE TWO DISAGREED ABOUT, MEASURED: this block took `raw[byte_pos[a] : byte_pos[a] + 192]`
    # -- 192 bytes FORWARD from the window's first token -- while spine/compose.py::_sample_window
    # took the 192 units ending at the cursor AFTER the window. Those coincide only when a window
    # happens to be exactly width_units bytes long; at the shipped geometry window 2's two slices differ
    # (b'sBsCsuupqyrCtqAq' against b'rBrDqsBsCsuupqyr') and window 5's agree. _sample_window's own
    # docstring says why that cannot stand: "ONE OBJECT, TWO CONSUMERS ... because domains/api.py::
    # observe says a rekey cannot reproduce the signature otherwise -- so a second slicer at the DOM
    # call site is a defect by construction". The defect was at the SIG call site instead, and it
    # would have put the signature DOM stores in its reservoir in a different space from the one
    # the router actually used -- exactly the drift DOM.rekey exists to prevent. AND BOTH SLICES
    # READ THE WINDOW'S OWN TEXT, so reconciling them to one left the routing seeing its targets;
    # that is the half Q-FAB-7 repaired, by moving the cursor and not the slicer.
    sig_vec = torch.stack(sigs) if len(sigs) > 1 else sigs[0].unsqueeze(0)
    # SIG BUILDS ITS OWN TENSOR AND NEED NOT AGREE WITH THE PROCESS DEVICE, so the signature is
    # moved rather than assumed. Checked instead of called unconditionally, because `.to()` on a
    # tensor already there is a copy on some backends.
    if sig_vec.device != x.device:
        sig_vec = sig_vec.to(dev)
    # NOVELTY IS THE PREVIOUS FLUSH'S PER-WINDOW SURPRISE, AND THE FIRST FLUSH HAS NONE.
    # Seeded at zeros rather than at a guess, and the distinction is reportable: a zero novelty
    # says "nothing was surprising yet" for exactly one flush, which is true, where any other seed
    # would be a measurement nobody took. It is resized to this flush's batch when the two differ,
    # which happens on the last, short flush of a stream.
    nb = x.shape[0]
    if novelty is None or int(novelty.shape[0]) != nb:
        novelty = torch.zeros(nb, device=dev)
    elif novelty.device != x.device:
        novelty = novelty.to(dev)
    # THE DOMAIN THE ROUTER BANS ON IS THE FLUSH'S FIRST WINDOW'S, dids[0], AND IT WAS THE LAST
    # WINDOW'S (`domain_id`) UNTIL 2026-09-24. FAB.forward takes ONE id for the whole batch, and the
    # breadth ban it builds from it masks experts out of EVERY row. The last window's id was assigned
    # from a signature over the bytes before the LAST window, which at OPT_BATCH_WINDOWS > 1 are the
    # earlier rows' own text -- so rows 0..B-2 were routed on a domain read off their own targets,
    # the Q-FAB-7 leak surviving the cursor repair one level up. dids[0]'s signature precedes every
    # row. THAT CLOSES THE BAN, NOT THE BATCH: inside FAB.forward the spawn test and the grounding
    # EMA also wrote a mean over every row into state row 0 then routed on, and both were moved onto
    # what precedes every row on 2026-09-24 (Q-FAB-7 (4), tests/test_causality.py C4). At the shipped OPT_BATCH_WINDOWS=1 the two are the same id and nothing moves. FAB.observe,
    # DOM.note_competence and MEM.write take `dids`, one id PER WINDOW (the first two took the last
    # window's id for the whole flush until 2026-09-24): they book what already happened and reach
    # no logit of this flush. The ban itself stays batch-wide because FAB.forward's domain_id is
    # one int; loop.flush_mixed_domain counts the flushes where that matters (Q-FAB-10).
    route_did = int(dids[0]) if dids else domain_id
    # `head` AND `targets` ARE PASSED, AND FOR THE WHOLE LIFE OF THIS CALL UNTIL 2026-09-24 THEY WERE
    # NOT. FAB.forward takes head=None and targets=None as "no vote, no deep supervision, no
    # independence term, no halt-on-base spend", and this call supplied neither -- so the shipped
    # FAB_HOP_VOTE=True and FAB_IND_W=0.5 never entered the objective, FAB_SOCIETY=1 and
    # FAB_HOP_SUP>0 produced reports identical to the default but for timing, and the gates that
    # said "no head was supplied" rode FabricOut.gates, which nothing printed. `head` is
    # compose.py::_head -- LM.decode with the vocabulary boundary bound, the same boundary the
    # decode below uses -- and `targets` is `y`, the tokens lm_loss scores.
    # `live_domains` IS DOM.census's n_live AND IT WAS THE LITERAL 1. LOOP_ORDER's DOM.census row
    # names the wire ("live_domains = n_live -- under FAB.forward's spelling"), and the literal
    # made the breadth cap's limit max(FAB_DOM_MIN, int(FAB_DOM_FRAC * 1)) = FAB_DOM_MIN on every
    # pass: FAB_DOM_FRAC=0.1 and 0.9 gave bit-identical 300-window runs (limit 4 on 300 of 300
    # passes, 1322 bans each) while DOM held 15 live domains. The value is carried from the
    # dom.manage pass's census -- the row's own declared staleness -- and is 1 until that pass first
    # fires (Q-FAB-9).
    with cast():
        with _timing.span("flush/fab.forward"):
            out = fab_api.forward(
                fab_cfg, pop, h=h, signature=sig_vec, novelty=novelty,
                head=_c_head(sysm), targets=y,
                step_windows=U.Windows(int(clock.step)),
                domain_id=route_did, live_domains=live_domains, training=True)
        # `hidden`, NOT `h`, AND THE FIRST DRAFT GOT THIS WRONG IN THE SAME TWO LINES AS THE SWALLOWED
        # EXCEPT ABOVE. It read `h = out.h if hasattr(out, "h") else h` -- so FabricOut, whose field is
        # `hidden`, never matched, the routed output was discarded, and the run trained on the
        # UNROUTED hidden while reporting that the fabric was in the path. The tell was that the loss
        # curve was byte-identical to the run taken before the fabric was wired in at all.
        # `hasattr(x, "a") else <unchanged>` IS THE SAME DEFECT AS A BARE EXCEPT: both turn a wrong
        # assumption into a silent no-op, and both produce a report that describes a mechanism that did
        # not run. Written plainly now, so a rename raises instead of degrading.
        h = out.hidden
        # THE FABRIC'S OWN LOSS TERM ENTERS THE OBJECTIVE. aux_loss is the balance/ponder/diversity sum
        # the fabric computes about its own routing; dropping it trains the router on nothing but the
        # language loss, which is the configuration every load-balance result in this project's history
        # was accidentally taken under.
        aux = out.aux_loss
        # `live_vocab` IS THE POSITIONAL BOUNDARY AND NOT THE COUNT OF LIVE ROWS, and this line read
        # `vocab.live_size()` until TOK.judge_probation was wired. tok/api.py's header is explicit:
        # "id_count is the positional boundary -- where never-minted rows begin, i.e. Vocabulary.size()
        # -- and it is what LM.decode's `live_vocab` argument must receive, because ids are positional:
        # retire() pops from the match table and leaves id2bytes intact, so retired rows sit BELOW the
        # boundary and are handled separately, by id. live_size is that boundary minus the retired
        # count, and passing it to decode would move the boundary down and mask exactly that many LIVE
        # rows to -inf. The composition root's own wiring table named live_size here until 2026-09-03."
        # THE TWO ARE EQUAL UNTIL SOMETHING RETIRES, which is why this survived every run so far: with
        # `retired` empty size() == live_size(), and nothing could retire while judge_probation was
        # uncalled. It is the same defect the header describes, one call site over, and it would have
        # started masking the `len(retired)` HIGHEST live ids on the first retirement of the first run
        # that turned probation on.
        # WHEN THE POPULATION VOTED, ITS LOGITS ARE THE PREDICTION AND `hidden` IS NOT RE-DECODED.
        # fabric/api.py::FabricOut: "the caller must not re-decode `hidden` -- that is the H11
        # offset, a loss scored through a different function from the one the contribution
        # counterfactual is subtracted from". out.logits is None exactly when nothing voted
        # (FAB_HOP_VOTE=0 off the society arm, and the FAB_ON=0 / FAB_NORM_ONLY=1 control arms), and
        # then this decode is the prediction, as it was on every run before the head was wired.
        if out.logits is not None:
            logits = out.logits
        else:
            logits = lm_api.decode(lm_cfg, model, h,
                                   live_vocab=int(vocab.size()), retired_ids=tuple(vocab.retired))
        per_window, mean = lm_api.lm_loss(lm_cfg, logits, y)

        # THE APPEARANCE COUNTER IS ADVANCED BY THIS FLUSH'S TOKENS, BEFORE THE TERMS THAT READ IT.
        # index_add_ over the flattened batch is the shipped form (:6804).
        sysm.token_seen.index_add_(0, x.reshape(-1),
                                   torch.ones(x.numel(), device=x.device, dtype=sysm.token_seen.dtype))

        # THE WORLD MODEL'S TWO TERMS. Its docstring is emphatic that the two weights must not be
        # folded into one: the integration once multiplied the anti-collapse term by WORLD_W=0.1, ran
        # it at a tenth strength, and the latent collapsed to std 0.24. Splitting it moved latent std
        # 0.24 -> 0.97 and forward-pred against persistence +13.6% -> +34.1%. loss_terms returns the
        # WEIGHTED sum, so the loop adds one number and cannot re-weight it here.
        wstep = world_api.loss_terms(cfg_world, sysm.world, obs_emb)
        world_loss = getattr(wstep, "loss", None) if wstep is not None else None

        # THE ANCHOR, ALREADY MULTIPLIED BY anchor_w BY THE ENTRY POINT. TOK_ANCHOR=0.05 was printed on
        # the EFFECTIVE line of every run in this project's history while model.compose was None and
        # the term never once entered the loss, because it was simply missing from the loss-weight list
        # at :5802-5813. Returning the weighted tensor is what keeps the number and the term together;
        # adding it here unweighted would rebuild the defect one call further out.
        anchor = lm_api.anchor_term(lm_cfg, model, token_seen=sysm.token_seen)

        total = mean
        for term in (aux, world_loss, anchor):
            if term is not None:
                total = total + term
    # THE DTYPE THE STEP ACTUALLY RAN IN, OBSERVED AND RECORDED -- the did-it-fire surface this
    # lever had none of. `amp_state` says what was ASKED FOR and what process_setup DECIDED; it
    # cannot say whether any caller ever ENTERED the context, which is precisely the fact that was
    # false for the whole life of this driver. This is read off the tensor the step produced, and
    # run.py prints it beside amp_state so a reader compares two numbers instead of trusting one.
    sysm.process_dtype = str(logits.dtype)
    # THE OPTIMIZER'S PER-ROW STATE FOLLOWS THE EXPERT ROWS FAB MOVED, BEFORE THIS BACKWARD
    # (Q-FAB-13). FabricOut.row_events carries every move / clear / birth since the previous
    # training pass -- the last flush's grow_check births, any manage pass's culls in between, and
    # this forward's spawns -- and this is the one point all of those have happened and the next
    # gradient has not been accumulated onto the old rows. Until 2026-09-24 nothing moved the
    # moments: a culled slot's survivor took its next step on the culled expert's exp_avg.
    opt_api.remap_rows(opt_cfg, sysm.optimizer, out.row_events)
    # A NON-FINITE TRAINING LOSS STOPS THE RUN HERE, BEFORE THE OPTIMIZER STEPS ON IT (2026-09-24).
    # The flag is formed BEFORE the backward and read AFTER it, so the host waits on the backward
    # the next line enqueues rather than stalling between the forward and the backward; the
    # optimizer's own grad-norm read a few lines down syncs at the same point anyway. Driven before
    # this guard: one flush whose loss was nan stepped AdamW on nan gradients, all 8 LM parameter
    # tensors went non-finite, and the run died a flush later inside DOM.note_competence with a
    # message about domain competence. Stopping here leaves the parameters, the AdamW moments and
    # every book downstream of the step (FAB.observe, grow_check, MEM.write, DOM.note_competence)
    # as the previous flush left them; the gradients just accumulated are discarded with the run.
    # NOT A DIVERGENCE ALARM: a finite loss of any size passes (EVAL owns that, and it is deferred).
    _finite = torch.isfinite(total.detach())
    with _timing.span("flush/backward"):
        n_bwd_opt = opt_api.scaled_backward(opt_cfg, sysm.optimizer, total)
    if not bool(_finite):
        _terms = {"LM loss": mean, "FAB aux": aux, "WORLD loss": world_loss, "LM anchor": anchor}
        _bad = [k for k, t in _terms.items()
                if t is not None and not bool(torch.isfinite(t.detach()).all())]
        _params_bad = sum(1 for t in sysm.base_params if not bool(torch.isfinite(t).all()))
        _st = sysm.optimizer
        _norms = list(getattr(_st, "grad_norms", ()) or ())
        # THE DISCARDED BACKWARD IS UN-COUNTED BEFORE THE FINAL SAVE (2026-09-24). scaled_backward
        # advanced OPT's n_backward (and opt.backward) for this nan pass, the clock's note_backward
        # has not run, and the loop's final save then persisted a count one above the clock's --
        # driven at OPT_ACCUM=3, nan at flush 8: clock 7, OPT 8, saved 8 -- so a resume, which
        # seeds the clock from OPT, phase-shifted its first accumulation group. The pass's nan
        # gradients are dropped with it; the group's earlier finite passes go with them, which the
        # resume counts as opt.ckpt.partial_accum_dropped.
        _st.n_backward = U.Backwards(int(_st.n_backward) - 1)
        _st.counters["opt.backward"] = int(_st.n_backward)
        _st.base.zero_grad(set_to_none=True)
        _c = clock.counters()
        raise _gate.NonFinite(
            f"loop: the training loss is non-finite ({float(total.detach())!r}) at window "
            f"{int(_c['step'])}, flush {int(_c['flushes'])}, optimizer step {int(_st.opt_step)} "
            f"(epoch {int(_c['epoch'])}); non-finite term(s): {', '.join(_bad) or 'none alone'}. "
            f"Stopped BEFORE the optimizer stepped on it. "
            + (f"{_params_bad} of {len(sysm.base_params)} base parameter tensor(s) are ALREADY "
               f"non-finite: written by an earlier optimizer step, or in place during this flush's "
               f"forward (FAB.forward updates its own rows, so a non-finite signature or hidden "
               f"reaching the fabric writes them before any loss exists). If an earlier step, the "
               f"likely lever is OPT_LR (the last applied rate was {float(_st.lr_prev):.4g}; last "
               f"recorded grad norm {(_norms[-1] if _norms else float('nan')):.4g}), with "
               f"OPT_GRAD_CLIP (0 = off) and OPT_LR_WARMUP beside it. "
               if _params_bad else
               f"Every base parameter was still finite, so the non-finite value arose in this "
               f"flush's forward: the likely lever is OPT_LR (last applied rate "
               f"{float(_st.lr_prev):.4g}, last recorded grad norm "
               f"{(_norms[-1] if _norms else float('nan')):.4g}) if the LM loss is the term, or "
               f"the weight lever of the term named above otherwise. ")
            + "No checkpoint is written from a non-finite state: CKPT.save refuses one.")

    # THE BACKWARD IS COUNTED BY THE CLOCK, and the optimizer steps only when the
    # clock says a step is due -- derive.accum_due on a Backwards clock, never a modulo on the
    # window counter. Two real runs one line apart measured 55 optimizer steps where 13 were due.
    # THESE TWO LINES MOVED HERE FROM `run` and the move is LOOP_ORDER's, not a preference. The B
    # row reads scaled_backward -> note_backward -> maybe_step -> own_lr_scale -> caps ->
    # observe/grow_check -> write/maintain -> ... -> note_competence, and with the step outside
    # `_flush` the driver ran observe and note_competence BEFORE the step every flush -- an order
    # nothing noticed while nothing downstream of maybe_step was wired. FAB.own_lr_scale is
    # downstream of it: its `applied_lr` is THIS flush's StepOutcome.lr, and there is no way to
    # supply that from a caller that has not stepped yet.
    stepped = clock.note_backward()
    # THE TWO BACKWARD COUNTS ARE COMPARED EVERY FLUSH, because two gates decide one step: the
    # clock's accum_due on RunClock.backwards lets maybe_step be called, and maybe_step re-decides
    # on OPT's own st.n_backward (scaled_backward's return). When they disagree the optimizer
    # silently never steps -- which is what every resume from a checkpoint saved partway through an
    # accumulation did until 2026-09-24 (Q-RUN-9): the clock restarted at 0 while OPT resumed at the
    # parent's count, and a 30-window OPT_ACCUM=4 child took 0 steps in 30 backward passes. The
    # clock is now seeded from OPT's restored count, so this cannot fire in a sound process; it is
    # here so the next route to that state stops the run on the first flush instead of at R.
    _clock_bwd = int(clock.counters()["backwards"])
    if _clock_bwd != int(n_bwd_opt):
        raise RuntimeError(
            f"loop: the clock counts {_clock_bwd} backward pass(es) and OPT counts "
            f"{int(n_bwd_opt)}. RunClock.note_backward decides whether a step is due on the first "
            f"and OPT.maybe_step on the second, so with them apart the optimizer steps on neither "
            f"schedule. spine/compose.py seeds the clock from OPT's restored n_backward for exactly "
            f"this reason (Q-RUN-9).")
    # shift_at IS THE E ROLL'S Steps STAMP (None until the first roll). OPT keeps it on its own
    # state and counts it once, so it is handed over on every stepped flush rather than cleared.
    with _timing.span("flush/opt.maybe_step"):
        outcome = (opt_api.maybe_step(opt_cfg, sysm.optimizer, shift_at=sysm.shift_at_steps)
                   if stepped else None)

    # THE PER-EXPERT RATES, ON THE RATE THE OPTIMIZER JUST APPLIED. LOOP_ORDER's own row says this
    # call "PRODUCES NOTHING ANY SIGNATURE ACCEPTS" -- the return is per-expert multipliers and
    # OPT.maybe_step has no parameter for them -- so calling it buys the ledger and not an effect,
    # and that is the honest state rather than a reason to leave it uncalled. fab.lr_calls now
    # separates "no expert was scaled" from "spine/loop.py never invoked it", which is the exact
    # distinction the entry point's own docstring says the counter exists for. At the shipped
    # FAB_LR_OWN=False it returns None on the first line after seeding its seven counters.
    # ONLY ON A FLUSH THAT STEPPED: with accum > 1 most flushes do not step, and StepOutcome.lr on
    # a flush that did not is a number nobody applied. Skipping is the truthful reading, and
    # fab.lr_calls counting fewer than the flushes is what says so.
    if outcome is not None:
        fab_api.own_lr_scale(fab_cfg, pop, applied_lr=float(outcome.lr))

    # THE OPERATING CEILING, READ ONCE PER FLUSH, AS THE WHOLE RECORD.
    # `soft_cap=caps` AND NOT `caps.experts`, WHICH IS A REAL DISAGREEMENT INSIDE THE CONTRACT AND
    # NOT A STYLE CHOICE. compose.py's CAP.caps row spells the produced value "soft_cap --
    # Caps.experts under FAB.grow_check's spelling" (an int) and then says four lines later "THE
    # LOOP TAKES ITS BIRTH BUDGET THROUGH Caps.headroom(population) AND NEVER BY SUBTRACTING".
    # Both cannot be true at one call site: FAB may not import capacity (O10), so the only way the
    # method can be reached is for the RECORD to arrive. fabric/api.py::_headroom refuses a bare
    # int by name and says so at length; passing `.experts` here would make FAB re-derive
    # `min(n_born, cap - fab.n())`, which is P3-C30 -- negative the moment the population sits
    # above the soft cap, and a negative clamp freezes growth for a whole run in silence.
    caps = cap_api.caps(cfg_cap, sysm.valve)

    # TOK.lift_vocab_cap, EDGE-TRIGGERED ON THE VALVE MOVING, WHICH IS WHAT ITS DOCSTRING ASKS FOR
    # AND WHAT THE ROW ABOVE COULD NOT SAY. tok/api.py::lift_vocab_cap opens with "AN EVENT, NOT A
    # PERIOD" and its RECEIVES line reads "to <- CAP.caps().vocab, as an argument, ON THE FLUSH CAP
    # LIFTED"; LOOP_ORDER's CAP.caps row names the wire ("-> ... TOK.lift_vocab_cap(to=...)") and a
    # wire carries no frequency, so the two together left the call site unruled and the body's own
    # comment enumerated both readings rather than choosing. This is the choice, and it is the
    # docstring's: a lift is a CHANGE, so it is announced when the number changes.
    # THE DIFFERENCE IS NOT COSMETIC AND IT IS NOT PERFORMANCE. Per flush, tok.cap_lift reads
    # present-and-0 for a whole run -- "this route ran a quarter of a million times and lifted
    # nothing" -- which is indistinguishable in the report from a valve that was asked and declined.
    # Edge-triggered, the counters stay ABSENT while CAP.observe is deferred, and ABSENT is this
    # tree's word for UNREACHABLE, which is the true state: valve.cap_vocab moves only inside
    # CAP.observe, so today nothing can move it and the event cannot occur. The route is wired all
    # the same, because the route existing is what lets that body be written later without a second
    # copy of the cap rule appearing at a call site.
    # THE FIRST FLUSH SEEDS AND DOES NOT CALL. A lift is a change and the first observation has
    # nothing to be a change from; calling on it would put a present-and-0 in the ledger that means
    # "the driver started", which is the reading this whole arrangement exists to avoid.
    _cv = int(caps.vocab)
    if sysm.cap_vocab_seen is None:
        sysm.cap_vocab_seen = _cv
    elif _cv != int(sysm.cap_vocab_seen):
        # THE RETURN IS THE CAP IN FORCE AND IT IS NOT WHAT IS STORED. lift_vocab_cap clamps
        # against d_vocab_ceiling and against this vocabulary's own (possibly closed) ceiling, so
        # its answer can sit below `_cv`; storing that instead would leave every later flush seeing
        # a difference and re-firing the event on a valve that never moved again.
        tok_api.lift_vocab_cap(tok_cfg, vocab, to=_cv)
        sysm.cap_vocab_seen = _cv

    # THE BOOKS, AFTER THE BACKWARD AND ON THE SAME FLUSH'S NUMBERS. FAB.observe credits `use` by
    # routing MASS and `uage` by SELECTION -- the H12/H13 split -- against the experts that actually
    # produced this output, so it takes the FabricOut and the per-window loss rather than a scalar.
    # AND ONE DOMAIN ID PER WINDOW, `dids`, WHICH WAS `domain_id` -- THE LAST WINDOW'S -- UNTIL
    # 2026-09-24: at OPT_BATCH_WINDOWS=4 21 of 60 flushes spanned more than one domain, and every
    # earlier window of those was affiliated (dom_of, which the breadth cap reads) with the last
    # one's domain. Identical at the shipped OPT_BATCH_WINDOWS=1, where `dids` is [domain_id].
    fab_api.observe(fab_cfg, pop, out, per_window_loss=per_window.detach(),
                    domain_id=list(dids) if dids else domain_id)

    # GROWTH. THE ONE MECHANISM GOAL B CANNOT BE STUDIED WITHOUT, and until this line the run's
    # report read "0 experts born" for a population that was never asked to grow.
    # memory_pressure COMES FROM MEM.census NOW, AND THIS ARGUMENT WAS HARD-CODED None UNTIL
    # 2026-09-21. grow_check's docstring described that state and named its TWO causes -- "MEM.read
    # is deferred and MEM.maintain's probe has no contexts, so nothing promotes out of probation" --
    # and both are closed: read has a body and the probe has the previous flush's batch. What
    # arrives here is MEM'S VERDICT (True / False / None) and never MEM's reading, because the
    # pressure_thresh comparison belongs to the package that declares it; passing the raw share
    # would make fab.grow_mem_eligible fire on every flush, which is Q-MEM-4's ruling.
    # STILL None UNTIL THE FIRST CADENCED CENSUS, and None after it whenever census cannot form the
    # verdict -- no eviction yet, or nothing has ever promoted. grow_check prints UNREACHABLE for
    # None and "armed, did not fire" for False, which are different sentences about different runs.
    # FAB_GROW_ON_MEM_PRESSURE STILL SHIPS False, so the leg is off by configuration even now that
    # it has a producer. That is a lever the owner turns, not something this driver decides.
    # shift_at RIDES THE SYSTEM AND IS None UNTIL SOMETHING STAMPS IT. Three sites are supposed to:
    # the E draw row's resample, TOK.mint_burst's retok and OPT's LR restart. ONE IS DRIVEN: the
    # epoch-roll block in `run` stamps it when it redraws the stream, into BOTH typed twins --
    # shift_at_windows for this call and shift_at_steps for OPT.maybe_step above. The retok is not
    # stamped on its own -- this driver defers it to that same roll, which is the act that
    # satisfies it -- and OPT's LR restart stamps nothing. On a run that takes no roll before it
    # ends (every RUN_EPOCHS=1 run) fab.shift_notifications therefore reads 0 and the blackout is
    # UNREACHABLE rather than armed -- which is precisely what that counter was declared to
    # distinguish. The same stamp is re-delivered on every later flush and grow_check counts it
    # ONCE (it read 158 for one roll until 2026-09-24, one per flush after it).
    # THE RECORD IS BOUND AND ITS GATES KEPT (2026-09-24). This was a bare expression statement, so
    # GrowReport's per-call gates -- the arithmetic of the call that evaluated them -- reached no
    # report. ONLY THE GATES TUPLE is kept, on System.grow_gates, and spine/loop.py::_report renders
    # it at R: the record itself is not held, and nothing here is on CKPT's save path.
    with _timing.span("flush/fab.grow_check"):
        _grow = fab_api.grow_check(fab_cfg, pop, flush_loss=mean.detach(),
                                   step_windows=U.Windows(int(clock.step)), soft_cap=caps,
                                   memory_pressure=mem_pressure, signature=sig_vec,
                                   shift_at=sysm.shift_at_windows)
    sysm.grow_gates = tuple(getattr(_grow, "gates", ()) or ())

    # ---- MEMORY -------------------------------------------------------------------------------
    # SURPRISE IS FORMED HERE AND NOWHERE ELSE, from LM.decode's logits and `y`, because it is the
    # one quantity on this row that no entry point returns. It is 1 - p_model(true token) at every
    # position -- the archive's `pm = F.softmax(lg.detach(), -1); surprise = 1 - pm.gather(...)`
    # (self_organize.py:683-684) -- and the SAME tensor whose per-window mean becomes the next
    # flush's `novelty`. One formation, two consumers, which is what stops the two from drifting
    # into different quantities under one word, as they had.
    # logsumexp RATHER THAN A FULL SOFTMAX: the gathered logit minus the row's normaliser is the
    # same number without materialising a second (B, L, 4096) tensor, and under AMP the float()
    # keeps the normaliser out of fp16, where a 4096-wide sum is where that format runs out.
    with torch.no_grad():
        lg = logits.detach().float()
        p_true = torch.exp(lg.gather(-1, y.unsqueeze(-1)).squeeze(-1)
                           - torch.logsumexp(lg, dim=-1))
        surprise = (1.0 - p_true)
        del lg
        # THE OWNER BLOCK, WHICH IS THE ONE JOIN IN THIS DRIVER THAT NO HELPER IN compose.py MAKES.
        # ROW_ARGUMENTS_ELSEWHERE["MEM.write"] says so in as many words: "argmax over
        # FabricOut.weights, modulo MEM.d_owner_blocks. FAB.forward does NOT return it ... it needs
        # a tensor operation and nothing in src/ imports torch; P4 writes it in the loop and this
        # entry is what says so."
        # PROVENANCE, PER WINDOW, FROM DOM.observe -- AND IT WAS A BROADCAST ZERO UNTIL OBSERVE
        # HAD A BODY. memory/api.py::_require_rows refuses a broadcast argument by name for exactly
        # this shape: "the six per-row arguments are six different quantities about the same rows,
        # and a broadcast one writes a whole flush under one window's provenance". `dids` is one id
        # per WINDOW, which is what the (B,) requirement means, and it is now genuinely more than
        # one value -- measured, 7 domains over 600 windows at the shipped defaults.
        sources = torch.tensor(dids, dtype=torch.long, device=dev)
        # THE OWNER BLOCK HAS TWO DECLARED SOURCES, ONE PER KIND OF ARM, AND THE SECOND IS NEW.
        # On the ROUTED arm it is the argmax of the routing weights, and a None there is a fabric
        # that did not route -- a fault, still refused. On the two CONTROL arms FabricOut.weights is
        # None BY DECLARATION (fabric/api.py::forward's FAB_ON=0 and FAB_NORM_ONLY=1 gates: routing
        # is "ABSENT rather than zero"), and until 2026-09-24 this line raised on both at the first
        # flush, after a full compose and SIG warm-up, naming no lever -- so neither ablation could
        # run. There the owner is the window's DOMAIN folded onto the blocks, `sources % blocks`:
        # per row, like the routed owner, and never a whole flush under block 0, which is what the
        # refusal below rightly refused to default to. IT IS A DIFFERENT QUANTITY UNDER THE SAME
        # ARGUMENT NAME, so it is counted -- loop.owners_from_domain, seeded in `run` on those arms --
        # and a MEM-side comparison between a routed and a control arm must read that counter first.
        _blocks = int(cfg_mem.d_owner_blocks)
        if out.weights is not None:
            owners = (out.weights.argmax(dim=1).long() % _blocks)
        elif "loop.owners_from_domain" in books:
            # A CONTROL ARM -- the key is seeded in `run` exactly when FAB_ON=0 or FAB_NORM_ONLY=1.
            owners = sources % _blocks
            books["loop.owners_from_domain"] += 1
        else:
            raise RuntimeError(
                "spine/loop.py::_flush: FabricOut.weights is None on the ROUTED arm (FAB_ON=1, "
                "FAB_NORM_ONLY=0), and MEM.write's `owners` is an argmax over it. "
                "fabric/api.py::FabricOut declares weights as the (B, n_live) routing distribution "
                "'the attribution table `observe`, the breadth cap and MEM's owner argmax all read' "
                "-- so a None here is a fabric that did not route, and writing every entry of the "
                "flush to block 0 instead would put a whole flush under one owner's provenance. "
                "Refused rather than defaulted. (The two control arms take the owner from the "
                "window's domain instead; this is neither of them.)")
        # TRUE BYTE OFFSETS, NOT AN ARANGE. MEM.write's docstring: "a token averages ~1.85 bytes
        # and the drift reached 200+ bytes per window against a 220-byte recall span". byte_pos is
        # the Segmentation's own table and the cut is `_window_bounds`'s, so the two cannot
        # disagree about which token a position is.
        bp = sysm.segmentation.byte_pos
        positions = torch.tensor([bp[a:a + ctx] for a, _b in pairs], dtype=torch.long, device=dev)
    now_w = U.Windows(int(clock.step))
    with _timing.span("flush/mem.write"):
        mem_api.write(cfg_mem, sysm.store, contexts=x, tokens=y, surprise=surprise,
                      sources=sources, owners=owners, positions=positions, key_fn=key_fn, now=now_w)
    # MAINTAIN, AND THE PROBE NOW HAS CONTEXTS -- WHICH IT COULD NOT HAVE UNTIL MEM.read EXISTED.
    # This block said "the None IS FORCED rather than chosen" and quoted maintain's own sentence,
    # "MEM.read is still a P4 stub, so this line raises NotImplementedError the moment a caller
    # supplies probe_contexts". read has a body now, so supplying them RETRIEVES instead of
    # raising, and both of those sentences have been corrected where they were written.
    # WHAT IT UNLOCKS, AND IT IS THE LARGEST SINGLE THING ON THIS ROW: only a retrieval promotes out
    # of probation. With no probe, nothing promoted, every eviction took the probation branch,
    # store.n_evict_main was identically 0 for every configuration -- so evict='lru' and
    # evict='usage' were WRITE-ORDER FIFO whatever they said (four archive files recorded that as
    # measured fact when it was measured through a constant), and MEM.census's pressure was
    # structurally None rather than merely low.
    # THE PROBE READS THE PREVIOUS FLUSH'S BATCH AND NOT THIS ONE'S, AND THAT IS A MEASUREMENT
    # DECISION RATHER THAN CONVENIENCE. MEM.write ran four lines above on THIS flush's x, so
    # probing with the same tensor asks the store whether it can retrieve what it stored
    # microseconds ago -- a question whose answer is yes by construction and tells nobody anything.
    # The previous flush's batch is material the store has had a full flush of eviction pressure to
    # lose, which is the question worth asking, and it costs one carried tensor. Q-MEM-4 named "one
    # P4 smoke run with probe_contexts stubbed from the training batch itself" as the way to
    # measure this rather than guess; this is that, with the lag that makes it a measurement.
    # IT IS None ON THE FIRST FLUSH, and on the first after each epoch roll, which maintain handles
    # as the declared armed-but-0 reading (n_probe_fired counts the CADENCE, n_probe_rows does not
    # move) rather than as an error. maintain forms ONE QUERY PER POSITION of this (B, L) batch and
    # issues MEM_PROBE_ROWS of them (Q-MEM-12): until 2026-09-24 it issued one per ROW, which at the
    # shipped OPT_BATCH_WINDOWS=1 was one query per probe against 64 declared.
    # THE PROBE MOVES `use`, `prob` AND `last`, AND THAT IS THE MECHANISM, NOT AN INSTRUMENT
    # EDITING ITS SUBJECT. memory/levers.py's probe_rows is emphatic that a probe must not consume
    # RNG draws, and it does not -- the stride is deterministic and MEM.read draws no randomness.
    # What it does change is which entries survive eviction, which is precisely what promotion is
    # for; an instrument that refused to promote would be the constant this repair removes.
    # `resegment` IS THE EPOCH ROLL'S NEW Segmentation ON THE FIRST FLUSH AFTER A ROLL AND None ON
    # EVERY OTHER (see where `run` sets and clears it). A mid-epoch Due.retok is not acted on -- the
    # roll is what re-segments -- so the roll is the only producer of a resegment event.
    # THE TWO GATES ARE MEM'S OWN and are compared against `now` INSIDE the call -- there is no
    # Cadences key for them, which is why their did-it-fire surface is store.n_probe_fired /
    # n_rekey_passes and the mem.probe / mem.rekey Gates the R stage's MEM.census row renders. Calling it once per flush is the shipped semantics: both periods are
    # Windows and elapsed-since-last-fire is phase-independent.
    with _timing.span("flush/mem.maintain"):
        mem_api.maintain(cfg_mem, sysm.store, now=now_w, key_fn=key_fn,
                         probe_contexts=probe_prev, resegment=resegment)

    # ---- THE EVENT-DRIVEN ROWS: what THIS BATCH'S Dues made due ---------------------------------
    # ACTED ON PER FLUSH, ASKED PER WINDOW. The Due was OR-ed across the batch in `run`; it is
    # CONSUMED here, so a fire is acted on exactly once and the next batch starts from nothing.
    due = sysm.due
    sysm.due = None
    if due is not None:
        now_w2 = U.Windows(int(clock.step))
        if due.mint:
            # THE VOCABULARY MINTS. `step` is clock.step AT THE FLUSH, so a token raised by a
            # mid-batch window is born up to batch_windows-1 windows later -- tok/api.py::on_window
            # says so ("BIRTH STEPS ARE FLUSH-ALIGNED") and probation_deadline compares
            # `step - birth` with both in Windows, so nothing raises.
            mints = tok_api.mint_burst(tok_cfg, vocab, step=now_w2)
            if mints:
                # AND THE MODEL IS TOLD, IN THE SAME FLUSH, WHICH IS NOT OPTIONAL. lm/levers.py
                # calls this goal B's row-level case: "a freshly minted token id points at a
                # randomly initialised embedding row and a randomly initialised head row, so the
                # model must re-learn from scratch material it can already spell with the parents",
                # measured at 2.1699 (random) against 1.4822 (last_first) immediate post-mint loss.
                # Minting without this call is that 2.1699 arm, chosen by omission.
                # sig_emb COMES FROM SIG.encoder_embedding, WHICH THIS COMMENT CALLED A STUB UNTIL
                # 2026-09-22. SIG needs the warm row more than the LM does: a domain centroid is a MEAN
                # of encodings, so one freshly-random token id inside a window perturbs every signature
                # containing it and the assembler reads that as a domain shift -- a spurious shift
                # arriving at the mechanism whose whole job is to notice real ones.
                # IT STILL RETURNS None AT THE SHIPPED SIG_SPACE=bytes, and that is the SECOND of
                # lm.mint.sig_rows' three declared states, not the third: "SIG is in byte space and
                # needs none" rather than "nobody passed it". The encoder's alphabet is 256 bytes and
                # it has no row for a token id in any sense.
                lm_api.on_mint(lm_cfg, model, mints, vocab.id2bytes, at_window=now_w2,
                               sig_emb=sig_api.encoder_embedding(sig_cfg, st))
        if due.retok:
            # THE RETOK IS DEFERRED TO THE NEXT EPOCH ROLL, NOT DROPPED -- and that is a change
            # from "dropped", which is what this branch did until the roll was wired.
            # WHAT THE ACT IS: re-segment the stream with the vocabulary as it now stands, so the
            # ids the run has been minting start appearing in its own training data. THE EPOCH
            # ROLL ALREADY DOES EXACTLY THAT, so a pending retok is satisfied by the next roll and
            # the only thing lost is the latency between them.
            # WHY NOT MID-EPOCH, STATED PRECISELY BECAUSE IT IS A CONTRACT GAP AND NOT A
            # PREFERENCE: re-segmenting mid-epoch changes how many WINDOWS the epoch holds, and
            # RunClock decides the roll with `rolled = self._in_epoch >= self.windows_in_epoch`.
            # The only public way to set `windows_in_epoch` is begin_epoch, and begin_epoch ZEROES
            # `_in_epoch` -- "the only quantity a roll may zero", its own words -- so calling it
            # here would restart the epoch and re-train on material already consumed. The archive
            # did the other half of this ("refresh the token stream with the grown vocab; remap
            # position by byte", self_organize.py:702) and the remap is writable here; what is not
            # writable is telling the clock a new length while KEEPING the position. That needs a
            # frozen-surface move on RUN -- a revise-length entry point, or an `at=` on
            # begin_epoch -- and it is the owner's, so it is recorded rather than invented.
            # A COUNT OF FIRES, NOT A FLAG: every fire is satisfied by the next roll or counted in
            # tok.due_dropped at the end, one each, and a bool made four fires read as one.
            sysm.retok_pending = int(sysm.retok_pending or 0) + 1
            vocab.counters["tok.retok_deferred"] = \
                vocab.counters.get("tok.retok_deferred", 0) + 1

        if due.probation:
            # THE RESIDUAL READ AND THE JUDGEMENT, IN THAT ORDER AND UNDER THE SAME GATE. The row
            # above exists so the per-token norm is NOT computed every flush for a consumer on a
            # probation_deadline-window cadence: "an instrument computed thousands of times and
            # discarded". It returns None at lm.compose=False, which is the shipped default, and
            # TOK's Gate then prints "unreachable (no residual_ratio supplied)" instead of silently
            # running the `use` test -- ISSUES P1-M41, the defect where the banner said embed and
            # the run had judged by use.
            ratios = lm_api.residual_ratios(lm_cfg, model)
            tok_api.judge_probation(tok_cfg, vocab, step=now_w2, appearances=sysm.token_seen,
                                    residual_ratio=ratios)
            # THE Judgement IS NOT STORED, AND THAT IS NOT IT BEING DROPPED ON THE FLOOR. Its three
            # numbers -- retired_ids, id_count, live_size -- are a REFRESH of what the vocabulary
            # holds, and the decode above reads them off `vocab` itself on the next flush, which is
            # the same object judge_probation just mutated. Keeping a copy here would be a second
            # home for a fact one object already owns, which is what DEFECT D-T3 is about from the
            # other side. What the record buys a caller that needs the numbers WITHOUT the
            # vocabulary in hand is real; this caller has the vocabulary.

    # COMPETENCE IS SEPARATE FROM DOM.observe BECAUSE THE NUMBER IS ONLY KNOWN AFTER THE FORWARD
    # PASS. It is bits per window, not nats: the loss is a natural-log cross-entropy and the
    # domain series is declared in bits, so the conversion happens once, here, at the one place the
    # two meet. Dividing by ln(2) at the read site instead is how one series ends up compared
    # against another in different units.
    # ONE CALL PER WINDOW, ON THAT WINDOW'S OWN id AND LOSS -- WHICH IS WHAT THE CALLEE DEMANDS AND
    # WHAT THIS LINE DID NOT DO UNTIL 2026-09-24. It passed did=domain_id (the LAST window's) and
    # bits=the FLUSH MEAN as a Python float, which slipped past domains/api.py::note_competence's
    # own refusal of a batch vector ("A per-window vector is a loop over this call, one `did` at a
    # time -- averaging it here would attribute a whole batch's windows to whichever domain the last
    # one landed in") and folded one number into the EMA where batch_windows belong. At the shipped
    # OPT_BATCH_WINDOWS=1 the one iteration is the old call exactly (per_window has one row and its
    # mean is `mean`); above it the EMA now runs at its declared per-window rate.
    _ln2 = math.log(2.0)
    _pw = per_window.detach().float().reshape(-1).tolist()
    for _did, _nats in zip(dids if dids else [domain_id] * len(_pw), _pw):
        dom_api.note_competence(cfg_dom, sysm.partition, did=int(_did), bits=float(_nats) / _ln2)
    # THE PER-WINDOW MEAN SURPRISE IS RETURNED BECAUSE THE NEXT FLUSH NEEDS IT AS `novelty`, and
    # it is NOT the per-window loss this function returned until the MEM wiring landed. Both are
    # (B,) and both come off the same flush, which is exactly why the substitution survived: only
    # forming the quantity MEM.write names by its own definition made the two visibly different.
    return float(mean.detach()), surprise.mean(dim=1), x
