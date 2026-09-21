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
`RunResult.skipped` names every LOOP_ORDER B row this driver has NO CALL SITE FOR. It is empty as
of the edit that wired the last of the twenty-one, and an empty list is exactly the state that made
the FIRST version of this report wrong: it filtered the B row through "is the body a stub" and
printed "0 MECHANISM(S) NOT CALLED" on a run that invoked six of twenty-one. The list is derived
from the table and cross-checked against `_CALLS` in both directions, so a row this driver drops
cannot vanish from the report and a `_CALLS` entry the table does not list raises.

`RunResult.gated` IS THE SECOND LIST AND IT EXISTS BECAUSE A CALL SITE IS NOT A CALL. Three rows
stand behind events (Due.mint, Due.probation) and one behind "the optimizer actually stepped"; at
the shipped TOK_PROBATION_USES=0 the probation cadence is never even asked, so two of the
twenty-one have a call site that CANNOT RUN. Reporting only the first list would say this run
judged probation when nothing did -- the same overstatement, one layer in. `_gate_report` reads the
three states (fired N / armed but 0 / unreachable) off the counter each owning package keeps,
rather than re-deriving a verdict here from levers this file does not own.

WHAT A RUN ON THIS DRIVER MEASURES TODAY: goal A's core -- a language model, routed through the
fabric, trained by the optimizer -- AND the mechanisms goal B is made of. The fabric grows, memory
is written and maintained, the vocabulary mints and LM.on_mint initialises each new row from its
parents. WHAT IS STILL MISSING, all of it for a named reason a reader can check: DOM.observe is a
stub so every window is domain 0; MEM.read is a stub so the store is write-only and its eviction
rules are write-order FIFO whatever they say; MEM.census is a stub so growth's memory-pressure leg
is unreachable; and the retok is RAISED AND NOT ACTED ON, counted in tok.due_dropped rather than
allowed to look like a cadence that never came due.
"""
import dataclasses
import math
import time

import torch

from spine import units as U
from train import api as run_api
from data import api as data_api
from tok import api as tok_api
from lm import api as lm_api
from sig import api as sig_api
from fabric import api as fab_api
from opt import api as opt_api
from capacity import api as cap_api
from spine.compose import _sample_window as _c_sample_window
from spine.compose import _key_fn as _c_key_fn
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
_CALLS = frozenset({
    "LM.encode", "SIG.encode", "FAB.forward", "LM.decode", "LM.lm_loss",
    "OPT.scaled_backward", "OPT.maybe_step", "CKPT.save",
    "LM.embed", "WORLD.loss_terms", "LM.anchor_term",
    "FAB.observe", "DOM.note_competence",
    "FAB.own_lr_scale", "CAP.caps", "FAB.grow_check", "MEM.write", "MEM.maintain",
    "TOK.mint_burst", "LM.residual_ratios", "TOK.judge_probation",
})

# CALLS THIS DRIVER MAKES THAT ARE NOT B-ROW ENTRY POINTS. The clock, which LOOP_ORDER lists under
# RUN and which `run` drives directly, and SIG.encode, which is a ROW A entry point -- the
# per-window signature -- that the flush needs before FAB.forward can route on it.
# THE CROSS-CHECK BELOW FOUND SIG.encode ON ITS FIRST RUN, which is the guard doing its job: the
# first draft of _CALLS listed it as though it were a B-row name, and a set that quietly disagreed
# with the table is exactly what the check exists to refuse. Row A, not row B, measured through
# spine/compose.py::plan().
_NOT_B_ROW = frozenset({"RUN.RunClock.advance", "RUN.RunClock.note_backward",
                        "SIG.encode", "DOM.observe", "TOK.on_window", "LM.on_mint"})

# WHY EACH UNWIRED MECHANISM'S ABSENCE MATTERS, in the consequence a reader needs rather than the
# name they already have. Missing keys fall back to a plain sentence; nothing here is load-bearing
# for correctness, only for legibility.
_WHY = {
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
# TO PREVENT, ONE LAYER IN. The first version of `skipped` filtered LOOP_ORDER's B row through "is
# the body a stub" and printed 0 on a run that invoked six entry points of twenty-one; this is that
# error's smaller sibling -- every B row now HAS a call site, and three of them stand behind gates
# that are UNREACHABLE at the shipped defaults (TOK_PROBATION_USES=0 turns the whole probation
# family off, and its cadence is never even asked). Printing "0 not called" and stopping there
# would say a run judged probation when nothing did.
# THE THREE STATES ARE THE TREE'S OWN, read off the counter dicts by the convention every package
# in it states: an ABSENT key means the mechanism was UNREACHABLE on the arm this run took, a key
# PRESENT AND 0 means it was armed and did not fire, and a positive value is a fire count. So this
# table names the gate in words and the counter to ask, and the reading is the counter's -- not a
# second opinion computed here from levers this file does not own.
_GATED = {
    "TOK.mint_burst": ("Due.mint, TOK's grow_every cadence asked at row A", "tok.due_mint"),
    "LM.residual_ratios": ("Due.probation (TOK_PROBATION_USES=0 makes it unreachable)",
                           "tok.due_probation"),
    "TOK.judge_probation": ("Due.probation (TOK_PROBATION_USES=0 makes it unreachable)",
                            "tok.due_probation"),
    "FAB.own_lr_scale": ("a flush on which the optimizer actually stepped", "fab.lr_calls"),
}
# CKPT.save IS GATED TOO AND IS NOT IN THAT TABLE, because its count is not in a counters dict this
# file can index -- CKPT keeps its books on the Retention record -- and because the driver itself
# holds the fact: `_save` returns whether a file was written, and the three routes into it (the
# cadence, SIGUSR1, the final save) are all this function's. Its line is appended by `run` from
# that count, which is a measurement rather than a lookup.


def _gate_report(sysm):
    """One line per gated call site: fired N / armed but 0 / unreachable. A tuple of strings.

    THE COUNTER IS ASKED, NOT RE-DERIVED. Each row names a key in the package's own did-it-fire
    dict -- vocab.counters for tok.*, Population.counters for fab.*, the retention record for
    ckpt.* -- and the three states come from whether that key is absent, zero or positive, which is
    the convention tok/api.py::Vocabulary.__init__ and fabric/api.py::_bump both state in full.
    Computing the answer here from levers would be a second verdict about a question the package
    that owns the threshold has already answered.
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


def _b_row_entry_points():
    """{"PKG.name"} for LOOP_ORDER's B row, splitting the rows that name two in one column.

    `FAB.observe/grow_check` and `MEM.write/maintain` are ONE ROW EACH and TWO ENTRY POINTS EACH.
    A count that does not split them is short by four, which is exactly the error the orchestrator
    made when it reported this row as 10/17 rather than 10/21.
    """
    from spine import compose as _c
    out = set()
    for row in _c.LOOP_ORDER:
        if row[0] != "B":
            continue
        for part in str(row[2]).split("/"):
            part = part.strip()
            if part:
                out.add(f"{row[1]}.{part}")
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
    """
    windows: int
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
    }


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
    wrote = ckpt_api.save(sysm.configs["CKPT"], payload=_payload(sysm),
                          geometry=dict(sysm.manifest), step=int(clock.step),
                          epoch=int(clock.epoch), reason=reason, suffix=suffix)
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
    """
    cfg = sysm.configs
    run_cfg, lm_cfg, tok_cfg = cfg["RUN"], cfg["LM"], cfg["TOK"]
    fab_cfg, sig_cfg, dat_cfg, opt_cfg = cfg["FAB"], cfg["SIG"], cfg["DATA"], cfg["OPT"]
    tok_cfg = cfg["TOK"]
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
    b_row = _b_row_entry_points()
    # _NOT_B_ROW IS SUBTRACTED TOO, AND LEAVING IT OUT PUT A CALL THIS DRIVER MAKES ON THE
    # NOT-CALLED LIST. `RUN.RunClock.note_backward` is invoked every flush (it is what counts the
    # backward and answers whether an optimizer step is due), and it appeared under "not called by
    # this driver" on the first corrected run. The set excuses a name from the cross-check below
    # AND states that the driver calls it; only the first of those two was wired up.
    # OVER-REPORTING IS THE SAFE DIRECTION AND STILL WRONG: a reader who trusts this list would
    # have concluded no backward was counted, on a run whose optimizer stepped twelve times.
    unwired = sorted(b_row - _CALLS - _NOT_B_ROW)
    stray = sorted(_CALLS - b_row - _NOT_B_ROW)
    if stray:
        raise RuntimeError(
            f"spine/loop.py::_CALLS names {stray}, which LOOP_ORDER's B row does not list and "
            f"_NOT_B_ROW does not excuse. One of the three is wrong, and a driver whose own record "
            f"of what it calls disagrees with the table is a driver whose report cannot be read.")
    skipped = tuple(f"{k}: {_WHY.get(k, 'not called by this driver')}"
                    + ("" if not _is_stub(_entry(k)) else "  [and the body is still a P4 stub]")
                    for k in unwired)

    warnings = list(sysm.warnings)
    clock, cadences = sysm.clock, sysm.cadences
    periods = {k: v for k, v in _periods_of(sysm).items()}
    model, pop, st = sysm.model, sysm.fabric, sysm.sig
    ctx = int(lm_cfg.ctx)
    batch_w = int(opt_cfg.batch_windows)
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
    did = 0
    first_loss = last_loss = float("nan")
    batch = []
    ids = sysm.segmentation.ids
    stopped_early = False

    while True:
        tick = clock.advance()
        i = int(tick.step) - 1
        bounds = _window_bounds(ids, i, ctx)
        if bounds is None:
            # THE STREAM RAN OUT INSIDE AN EPOCH THE CLOCK STILL THINKS IS RUNNING. Reported rather
            # than silently treated as the end: the clock's epoch length came from
            # _windows_in_epoch and a disagreement between it and the ids it was measured on is a
            # defect somebody needs to see, not a loop exit.
            warnings.append(
                f"loop: the segmentation ran out at window {i} while the clock's epoch was not "
                f"finished (len(ids)={len(ids)}, ctx={ctx}). Stopping; the epoch length and the "
                f"stream it was measured on disagree.")
            break
        batch.append(bounds)
        # DOM.observe IS CALLED ONCE PER WINDOW, ABOVE THE BATCH EARLY-OUT, and that placement is
        # what makes `sustain` a Windows clock rather than a flush one -- domains/api.py::observe
        # says so, and `s.run` is incremented once per call. Putting it in the flush would divide
        # every domain clock by the batch width, silently, at every BATCH_W.
        # sample_window IS THE SAME OBJECT SIG.encode GETS, through the root's one slicer: a rekey
        # cannot reproduce the signature otherwise, so a second slice at this call site would be a
        # defect by construction.
        # DOM.observe IS NOT WIRED, AND IT IS NOT ONE OF THE ELEVEN -- IT IS A TWELFTH STUB.
        # It is the only producer of a domain id, so with no body every window is domain 0 and the
        # fabric's per-domain books, the breadth ban and DOM.note_competence all see ONE domain.
        # domains/api.py::observe says what that state is: "enabled == False returns did=0 for every
        # window ... THAT IS NOT A DEGENERACY MEM HAS TO DISCOVER: 0 is a real source id that MEM
        # sees, and the report must say 'the partition is off' rather than leaving the per-source
        # floor to protect exactly one source in silence." The same sentence applies to a stubbed
        # observe, and this is the loop saying it.
        # A SECOND DEFECT WAS FOUND ON THE WAY AND IS RECORDED BECAUSE NOTHING ELSE WILL FIND IT:
        # spine/compose.py::_sample_window clamps its start at 0, so early in the stream it returns
        # a SHORT window -- 173 units against a frozen 192 on the first flush, measured -- and
        # sig/api.py::encode refuses exactly that ("no eval variant, no gist placeholder and no
        # fallback ... because the alternative measured a whole project's routing on one byte").
        # The helper returns a window its only consumer refuses, and until this loop called it
        # there was no consumer to find out. Padding would invent units the model has not consumed;
        # taking the units AHEAD of the cursor is what that helper's own docstring rules out. The
        # repair belongs in the root, which owns the slicer.

        # ---- ROW A: TOK'S FOUR CADENCES, ASKED ONCE PER WINDOW ---------------------------------
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
        due = tok_api.on_window(tok_cfg, vocab, ids[bounds[0]:bounds[1]], step=tick.step)
        if sysm.due is None:
            sysm.due = due
        else:
            prev = sysm.due
            merged = ((prev.mint and due.mint) or (prev.retok and due.retok)
                      or (prev.probation and due.probation))
            if merged:
                # tok.due_merged: A FLUSH WHERE MORE THAN ONE WINDOW RAISED THE SAME KEY.
                # UNREACHABLE AT THE SHIPPED batch_windows=1, where no two windows share a flush --
                # which is why it is bumped here, in the branch that only a second window can reach,
                # rather than seeded to a number the shipped configuration cannot produce.
                vocab.counters["tok.due_merged"] = vocab.counters.get("tok.due_merged", 0) + 1
            sysm.due = dataclasses.replace(
                prev, mint=prev.mint or due.mint, retok=prev.retok or due.retok,
                probation=prev.probation or due.probation, frozen=due.frozen)

        if tick.flush_due:
            loss, per_window = _flush(sysm, batch, ctx, model, pop, st, lm_cfg, fab_cfg, sig_cfg,
                                      opt_cfg, vocab, clock, sysm.novelty, did, key_fn)
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
            batch = []
            if loss is not None:
                last_loss = loss
                if curve == []:
                    first_loss = loss
                curve.append(loss)

        # THE PERIODIC CHECKPOINT, THROUGH THE SAME Cadences EVERY OTHER GATE USES. A 53-minute
        # run finished with `ckpt checks=0` -- the gate was never EVALUATED, so nothing was written
        # and the trained weights were lost at process exit. That is what this call is: not a
        # refinement, a repair. It is evaluated per window rather than per flush because the period
        # is in WINDOWS and Cadences.due is phase-independent by construction.
        if cadences.due("ckpt", periods["ckpt"], clock):
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
            break
        if tick.rolled:
            # THE CALLER MUST SUPPLY A FRESH STREAM AND CALL begin_epoch, which RunClock now
            # ENFORCES by re-arming windows_in_epoch to None at the roll.
            warnings.append("loop: an epoch rolled; this driver runs a single pass and stops "
                            "there, because DATA.draw_stream at stage E is not yet driven per "
                            "epoch from here.")
            break
        if max_windows is not None and int(tick.step) >= int(max_windows):
            stopped_early = True
            warnings.append(f"loop: stopped at max_windows={int(max_windows)}, which is a DRIVER "
                            f"argument and not a lever -- this run is shorter than RUN.epochs and "
                            f"DATA asked for, and no report line should be read as a full run.")
            break

    # THE FINAL SAVE, UNCONDITIONALLY, WHATEVER ENDED THE RUN. A run that stops because the epoch
    # finished, because max_windows was reached, or because the stream ran out has all done the
    # same amount of training, and losing it in the last two cases would make the driver's own
    # argument the difference between a kept model and a discarded one.
    # saving_on IS NOT RE-TESTED HERE: CKPT.save asks it and returns False, counting refused_off,
    # which is the reading that makes "0 saves" distinguishable from "saving is off".
    # WHAT THE MINTS ACTUALLY DID TO THIS RUN, WHICH IS LESS THAN "THE VOCABULARY GREW" SOUNDS.
    # The stream is segmented ONCE, before the first window, at the vocabulary the run entered with;
    # the only thing that re-segments it is the retok, and this driver raises that Due and does not
    # act on it (see the Due.retok branch in _flush for why). So every id minted during the run is
    # a row LM.on_mint initialised from its parents and NOTHING IN Segmentation.ids EVER REFERS TO
    # IT. The merge table has it, a resume carries it, tok.mint counts it -- and no window contains
    # it, so no gradient reaches it and the vocabulary's growth cannot show up in the loss.
    # THIS IS SAID HERE BECAUSE NOTHING ELSE IN THE REPORT SAYS IT. tok.mint reads 18 and
    # lm.mint.rows_init_mean reads 18 and both are true; a reader adding those to "the vocabulary
    # mints" would conclude the mechanism is contributing to this run's numbers, and it is not.
    _minted = int(vocab.counters.get("tok.mint", 0))
    if _minted:
        warnings.append(
            f"loop: {_minted} token(s) were minted and their rows initialised, and NONE OF THEM "
            f"CAN APPEAR IN THIS RUN'S TRAINING STREAM. Segmentation.ids was built once, before "
            f"the first window, at the vocabulary the run entered with, and the only thing that "
            f"re-segments it is the retok -- which this driver raises (tok.due_retok) and does not "
            f"act on (tok.due_dropped). The mints are real, the rows are real and a resume carries "
            f"both; what they are not is USED. Minting contributes nothing to this run's loss.")

    final_written = _save(sysm, clock, "final")
    saves += 1 if final_written else 0
    if not final_written:
        warnings.append(
            "loop: no final checkpoint was written -- CKPT_DIR names no directory, so saving is "
            "off and this run's weights end with the process. Set CKPT_DIR to keep them.")

    c = clock.counters()
    return RunResult(
        windows=int(c["step"]), opt_steps=int(c["opt_steps"]), flushes=int(c["flushes"]),
        epochs=int(c["epoch"]), loss_first=first_loss, loss_last=last_loss,
        loss_curve=tuple(curve), elapsed_s=time.time() - t0, skipped=skipped,
        gated=_gate_report(sysm) + (
            f"CKPT.save: {saves} checkpoint(s) written by this run (periodic, SIGUSR1 and the "
            f"final one together); 0 means CKPT_DIR names no directory and saving is off",),
        report=_report(sysm, time.time() - t0, ctx),
        cadence_ledger=cadences.ledger(), warnings=tuple(warnings))


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
_R_MISSING = (
    "MEM.census: a P4 stub. The store's occupancy, its probation share and the pressure "
    "FAB.grow_check's memory_pressure leg needs are all this row's, and none of them is produced.",
    "DOM.census: a P4 stub, and so is DOM.observe above it -- the partition has one domain because "
    "nothing ever assigned a second, so there is no census to take.",
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
    out["MEM(store.counters)"] = dict(sysm.store.counters)
    # DOM.prior FOR did=0, WHICH IS EVERY WINDOW THIS RUN HAD. Rendered as the pair the entry point
    # returns rather than as the histogram: (None, 0.0) is the real answer at the shipped
    # DOM_PRIOR_BLEND, and it is a different fact from a histogram of zeros.
    _pr, _w = dom_api.prior(cfg["DOM"], sysm.partition, did=0)
    out["DOM.prior(0)"] = {"has_histogram": _pr is not None, "weight": float(_w)}
    if sysm.retention is not None:
        out["CKPT.Retention.counters"] = sysm.retention.counters()
    bench = run_api.bench_summary(
        cfg["RUN"], sysm.clock, elapsed_s=elapsed_s,
        bytes_per_window=int(ctx * float(sysm.segmentation.bytes_per_token)),
        n_params=sum(int(t.numel()) for t in sysm.base_params))
    # None IS THE OFF ARM AND IS RECORDED AS SUCH. bench_summary "PRINTS INSTEAD OF the eval
    # battery", so it returns None rather than empty lines at RUN_BENCH=0 -- a caller that got []
    # would print a heading with nothing under it.
    out["RUN.bench_summary"] = bench if bench is not None else "RUN_BENCH=0: off"
    out["R ROWS WITH NO PRODUCER"] = _R_MISSING
    return out


def _periods_of(sysm):
    """compose.py::_periods, reached without importing compose into this module's top level."""
    from spine import compose as _c
    return _c._periods(sysm)


def _flush(sysm, batch, ctx, model, pop, st, lm_cfg, fab_cfg, sig_cfg, opt_cfg, vocab, clock,
           novelty, domain_id, key_fn):
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
    obs_emb = lm_api.embed(lm_cfg, model, x)
    h = lm_api.encode(lm_cfg, model, x)
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
    # byte byte_pos[a], and the signature reads width_units bytes from there -- the same text the
    # window is made of, measured in the alphabet SIG was built for.
    bpos, raw = sysm.segmentation.byte_pos, sysm.stream.bytes
    wu = int(st.width_units)
    units = []
    for a, _b in pairs:
        o = int(bpos[a])
        chunk = raw[o:o + wu]
        if len(chunk) < wu:
            # SHORT AT THE END OF THE CORPUS. Padded with zeros ONLY here, at the last window of
            # the stream, and never as a fallback for a call that should have supplied the units:
            # the difference is that this is a real window whose text ran out, not a caller
            # declining to measure. A narrower window is what SIG refuses; a full-width window
            # whose tail is past the end of the corpus is a fact about the corpus.
            chunk = chunk + bytes(wu - len(chunk))
        units.append(list(chunk))
    sig_vec = sig_api.encode(sig_cfg, st, units)
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
    out = fab_api.forward(
        fab_cfg, pop, h=h, signature=sig_vec, novelty=novelty,
        step_windows=U.Windows(int(clock.step)),
        domain_id=domain_id, live_domains=1, training=True)
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
    opt_api.scaled_backward(opt_cfg, sysm.optimizer, total)

    # THE BACKWARD IS COUNTED BY THE CLOCK AND NOWHERE ELSE, and the optimizer steps only when the
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
    outcome = opt_api.maybe_step(opt_cfg, sysm.optimizer) if stepped else None

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

    # THE BOOKS, AFTER THE BACKWARD AND ON THE SAME FLUSH'S NUMBERS. FAB.observe credits `use` by
    # routing MASS and `uage` by SELECTION -- the H12/H13 split -- against the experts that actually
    # produced this output, so it takes the FabricOut and the per-window loss rather than a scalar.
    fab_api.observe(fab_cfg, pop, out, per_window_loss=per_window.detach(), domain_id=domain_id)

    # GROWTH. THE ONE MECHANISM GOAL B CANNOT BE STUDIED WITHOUT, and until this line the run's
    # report read "0 experts born" for a population that was never asked to grow.
    # memory_pressure=None IS THE DECLARED PRESENT STATE AND NOT A PLACEHOLDER. grow_check's own
    # docstring: "when it is None that lever is UNREACHABLE and says so ... ITS PRESENT STATE IS
    # unreachable AND THE ARITHMETIC IS MEM'S: MEM.read is deferred and MEM.maintain's probe has no
    # contexts, so nothing promotes out of probation ... which is why grow_on_mem_pressure also
    # ships False. Two named causes, not one." The producer is MEM.census, which is still a P4
    # stub; inventing a number here would be a threshold comparison at a consumer site, in a
    # package that does not own pressure_thresh, which is the defect Q-MEM-4 settled.
    # shift_at RIDES THE SYSTEM AND IS None UNTIL SOMETHING STAMPS IT. Three sites are supposed to:
    # the E draw row's resample, TOK.mint_burst's retok and OPT's LR restart. The first two are not
    # driven yet (the retok needs TOK.on_window's Due, a stub), so fab.shift_notifications reads 0
    # and the blackout is UNREACHABLE rather than armed -- which is precisely what that counter was
    # declared to distinguish.
    fab_api.grow_check(fab_cfg, pop, flush_loss=mean.detach(),
                       step_windows=U.Windows(int(clock.step)), soft_cap=caps,
                       memory_pressure=None, signature=sig_vec,
                       shift_at=sysm.shift_at_windows)

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
        if out.weights is None:
            raise RuntimeError(
                "spine/loop.py::_flush: FabricOut.weights is None, and MEM.write's `owners` is an "
                "argmax over it. fabric/api.py::FabricOut declares weights as the (B, n_live) "
                "routing distribution 'the attribution table `observe`, the breadth cap and MEM's "
                "owner argmax all read' -- so a None here is a fabric that did not route, and "
                "writing every entry of the flush to block 0 instead would put a whole flush under "
                "one owner's provenance. Refused rather than defaulted.")
        owners = (out.weights.argmax(dim=1).long() % int(cfg_mem.d_owner_blocks))
        # PROVENANCE, AND IT IS domain 0 FOR EVERY WINDOW BECAUSE DOM.observe IS A STUB. That is a
        # real source id rather than an absence -- domains/api.py::observe's own sentence, quoted
        # in full at the DOM.observe call site above -- so the store's per-source floor is
        # protecting exactly one source and `n_floor_blocked` must be read with that in mind. It is
        # `domain_id` and not a literal 0 so that the day observe lands, this line is already right.
        sources = torch.full((x.shape[0],), int(domain_id), dtype=torch.long, device=dev)
        # TRUE BYTE OFFSETS, NOT AN ARANGE. MEM.write's docstring: "a token averages ~1.85 bytes
        # and the drift reached 200+ bytes per window against a 220-byte recall span". byte_pos is
        # the Segmentation's own table and the cut is `_window_bounds`'s, so the two cannot
        # disagree about which token a position is.
        bp = sysm.segmentation.byte_pos
        positions = torch.tensor([bp[a:a + ctx] for a, _b in pairs], dtype=torch.long, device=dev)
    now_w = U.Windows(int(clock.step))
    mem_api.write(cfg_mem, sysm.store, contexts=x, tokens=y, surprise=surprise,
                  sources=sources, owners=owners, positions=positions, key_fn=key_fn, now=now_w)
    # MAINTAIN, WITH NO PROBE CONTEXTS, AND THE None IS FORCED RATHER THAN CHOSEN. Its docstring:
    # "MEM.read is still a P4 stub, so this line raises NotImplementedError the moment a caller
    # supplies probe_contexts -- which is the loud state, and is why the cadence above is counted
    # before it", and "WITH probe_contexts None OR EMPTY the honest DID IT FIRE reading is
    # n_probe_fired counting the CADENCE and n_probe_rows == 0: armed-but-0, not unreachable and
    # not silence." So the probe cadence fires and retrieves nothing, which means evict='lru' and
    # evict='usage' are write-order FIFO for this run whatever they say, and probation can never
    # promote. That is a fact about what this run measures and it belongs in the report.
    # resegment=None FOR THE SAME REASON THE RETOK IS NOT DRIVEN: TOK.on_window is a stub, so no
    # Due.retok is ever raised and there is no RetokEvent to distribute.
    # THE TWO GATES ARE MEM'S OWN and are compared against `now` INSIDE the call -- there is no
    # Cadences key for them, which is why store.n_probe_fired / n_rekey_passes are their only
    # did-it-fire surface. Calling it once per flush is the shipped semantics: both periods are
    # Windows and elapsed-since-last-fire is phase-independent.
    mem_api.maintain(cfg_mem, sysm.store, now=now_w, key_fn=key_fn,
                     probe_contexts=None, resegment=None)

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
                # sig_emb IS None BECAUSE SIG.encoder_embedding IS A P4 STUB, and the consequence
                # is SIG's and not LM's: a domain centroid is a mean of encodings, so one
                # freshly-random token inside a window perturbs every signature containing it and
                # the assembler reads that as a domain shift. lm.mint.sig_rows reading 0 is the
                # third of its three declared states -- "nobody passed it" -- and it is this line.
                lm_api.on_mint(lm_cfg, model, mints, vocab.id2bytes, at_window=now_w2,
                               sig_emb=None)
        if due.retok:
            # THE RETOK IS RAISED AND NOT ACTED ON, AND THE FIRE IS COUNTED AS DROPPED RATHER THAN
            # LEFT TO LOOK LIKE A CADENCE THAT NEVER CAME DUE. Q-TOK-12 says tok.due_dropped is
            # "0 BY CONSTRUCTION" under the OR and that "a counter that must read zero is the only
            # way a later reader can tell which reading was actually implemented" -- that sentence
            # is about the BATCH, where the OR really does drop nothing. This is a larger fact of
            # the same kind: `_due` banked the step, the act did not happen, and the next retok is
            # a full retok_every away. So the counter is bumped, which makes the claim visibly
            # false on any run where it happens, which is the loud state.
            # WHY IT IS NOT DRIVEN: the act is TOK.tokenize over the whole stream, producing a new
            # Segmentation -- new ids, new byte_pos -- mid-epoch. The clock's windows_in_epoch was
            # measured on the OLD segmentation (compose.py::_windows_in_epoch), every byte offset
            # already written into the memory store indexes the old one, and the RetokEvent the
            # root is supposed to distribute is a record type "no entry point's docstring returns"
            # (compose.py's own words), with DOM.on_retokenize a stub and SIG and FAB having no
            # retokenize entry point at all. Doing a third of it would put the run into two
            # segmentations at once, which is worse than not doing it.
            vocab.counters["tok.due_dropped"] = vocab.counters.get("tok.due_dropped", 0) + 1
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
    dom_api.note_competence(cfg_dom, sysm.partition, did=domain_id,
                            bits=float(mean.detach()) / math.log(2.0))
    # THE PER-WINDOW MEAN SURPRISE IS RETURNED BECAUSE THE NEXT FLUSH NEEDS IT AS `novelty`, and
    # it is NOT the per-window loss this function returned until the MEM wiring landed. Both are
    # (B,) and both come off the same flush, which is exactly why the substitution survived: only
    # forming the quantity MEM.write names by its own definition made the two visibly different.
    return float(mean.detach()), surprise.mean(dim=1)
