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
is unreachable. ALL THREE OF THOSE SENTENCES WERE TRUE UNTIL 2026-09-21 AND ARE NOW FALSE: observe,
read and census have bodies, this driver calls all three, the partition assigns real ids, the probe
retrieves and promotes, and pressure has a producer. What remains: FAB.manage and SIG.train_step
are stubs, so no expert is ever culled and the signature encoder never learns, and their cadences
are deliberately NOT ASKED because an asked gate records its fire; and the retok is DEFERRED TO THE
EPOCH ROLL rather than performed mid-epoch, which at RUN_EPOCHS=1 means never (Q-RUN-8).

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
from spine.compose import _sig_encode_fn as _c_sig_encode_fn
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
    # ---- stage E, the epoch roll (reachable only at RUN_EPOCHS > 1)
    "DATA.draw_stream", "TOK.tokenize", "RUN.RunClock.begin_epoch",
    # ---- stage A: the cadenced maintenance block, then the per-window pair
    "MEM.census", "DOM.manage", "DOM.census", "DOM.rekey",
    "RUN.RunClock.advance", "SIG.encode", "DOM.observe", "TOK.on_window",
    # ---- stage B, per flush: all twenty-one
    "LM.embed", "LM.encode", "SIG.encode", "FAB.forward", "LM.decode", "LM.lm_loss",
    "WORLD.loss_terms", "LM.anchor_term", "OPT.scaled_backward", "RUN.RunClock.note_backward",
    "OPT.maybe_step", "FAB.own_lr_scale", "CAP.caps", "FAB.observe", "FAB.grow_check",
    "MEM.write", "MEM.maintain", "TOK.mint_burst", "LM.residual_ratios", "TOK.judge_probation",
    "DOM.note_competence", "CKPT.save",
    # ---- stage C, the checkpoint fan-out, through _payload and _save
    "DATA.stream_state", "TOK.vocab_state", "LM.state_dict", "SIG.state_dict", "FAB.state_dict",
    "WORLD.state_dict", "WORLD.geometry", "MEM.state_dict", "DOM.state_dict", "CAP.state",
    "OPT.state_dict", "CKPT.Retention.state", "TOK.save_vocabulary",
    # ---- stage R, the report, through _report and run's own tail
    "DOM.prior", "LM.counters", "SIG.counters", "FAB.counters", "OPT.counters", "CAP.counters",
    "RUN.RunClock.counters", "RUN.Cadences.ledger", "CKPT.Retention.counters",
    "RUN.bench_summary",
})

# CALLS THIS DRIVER MAKES THAT LOOP_ORDER DOES NOT GIVE A ROW OF THEIR OWN. Exactly one: LM.on_mint
# is named inside TOK.mint_burst's B-row text ("-> LM.on_mint(sig_emb=SIG.encoder_embedding(...))")
# rather than carrying a row, so it is a real call with no row to be counted against.
# THIS SET USED TO CARRY FOUR NAMES AND TWO OF THEM WERE WRONG IN OPPOSITE DIRECTIONS.
# RUN.RunClock.advance and RUN.RunClock.note_backward are ON the table -- A and B respectively --
# and belong in _CALLS, which is where they are now. DOM.observe was in here, and this set does two
# things at once: it excuses a name from the cross-check AND asserts the driver calls it. The driver
# does NOT call DOM.observe -- the comment at that call site says so at length -- so listing it here
# subtracted it from the uncalled list and hid it. It was invisible while the report only ever read
# the B row, because DOM.observe is a row-A entry point and the subtraction was a no-op; the moment
# the report covered every stage it would have started lying. Two wrongs cancelling is not a test
# passing.
_OFF_TABLE = frozenset({"LM.on_mint"})

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
_GATED = {
    "TOK.mint_burst": ("Due.mint, TOK's grow_every cadence asked at row A", "tok.due_mint"),
    "LM.residual_ratios": ("Due.probation (TOK_PROBATION_USES=0 makes it unreachable)",
                           "tok.due_probation"),
    "TOK.judge_probation": ("Due.probation (TOK_PROBATION_USES=0 makes it unreachable)",
                            "tok.due_probation"),
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


# DISAGREEMENTS BETWEEN THE TWO GEOMETRY PRODUCERS, COLLECTED ACROSS THE RUN AND SURFACED ONCE.
# Module level rather than per-call because _save runs on a cadence and a reader needs the fact
# once, not once per checkpoint; `run` drains it into RunResult.warnings.
_disagree = []


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
    wrote = ckpt_api.save(sysm.configs["CKPT"], payload=_payload(sysm),
                          geometry=recorded, step=int(clock.step),
                          epoch=int(clock.epoch), reason=reason,
                          best_state=(None if sysm.retention is None
                                      else sysm.retention.state()),
                          suffix=suffix)
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
    stray = sorted(_CALLS - every - _OFF_TABLE)
    if stray:
        raise RuntimeError(
            f"spine/loop.py::_CALLS names {stray}, which LOOP_ORDER does not list at any stage and "
            f"_OFF_TABLE does not excuse. One of the three is wrong, and a driver whose own record "
            f"of what it calls disagrees with the table is a driver whose report cannot be read.")
    # PER STAGE, BECAUSE A TOTAL HIDES WHICH PART OF THE LOOP IS MISSING. Stage E uncalled means
    # this driver runs one pass; stage A uncalled means the cadenced maintenance never happens;
    # stage C uncalled would mean the checkpoint is short a package. Those are three different
    # runs and one number cannot say which.
    uncalled = {st: sorted(rows[st] - _CALLS) for st in sorted(rows) if rows[st] - _CALLS}
    skipped = tuple(
        f"[{st}] {k}: {_WHY.get(k, 'not called by this driver')}"
        + ("" if not _is_stub(_entry(k)) else "  [and the body is still a P4 stub]")
        for st in sorted(uncalled) for k in uncalled[st])

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
    # THE EPOCH-LOCAL WINDOW INDEX. Zero at the start of every epoch, which is what makes the cut
    # and the signature slice index the segmentation that is currently loaded rather than the run's
    # cumulative window count. See the paragraph at the cut.
    win_in_epoch = 0
    # ONE TAIL WARNING PER RUN, not one per epoch: the one-token tail is a property of the
    # geometry, so a resampling run would otherwise repeat the same sentence every time a
    # draw happened to land on a multiple of ctx.
    _tail_warned = False
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
    # THE PENDING RESEGMENTATION EVENT, set by the epoch roll and consumed by the next flush. None
    # on every other flush, which is what makes store.n_resegment_events a count of ROLLS.
    resegment = None
    # THE ROOT'S ONE BOUND SIG.encode, formed once: DOM.rekey's `encode`. domains/api.py::rekey
    # requires the SAME callable the live path used, or the partition drifts into two signature
    # spaces that do not compare.
    sig_encode = _c_sig_encode_fn(sysm)
    first_loss = last_loss = float("nan")
    batch = []
    ids = sysm.segmentation.ids
    stopped_early = False

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
            # THE WINDOW HAS NO MATERIAL. TWO CAUSES, AND THEY ARE DIFFERENT FACTS ABOUT DIFFERENT
            # RUNS, so this branch names which before it does anything.
            # (1) THE ONE-TOKEN TAIL, WHICH IS ARITHMETIC AND NOT A DEFECT. `_windows_in_epoch` is
            #     `len(ids) // ctx` and a window needs ctx + 1 ids -- `y` is `x` shifted one token
            #     -- so whenever len(ids) is an exact multiple of ctx the LAST window of the epoch
            #     is one target short. The clock is right, the division is right, and the epoch
            #     simply ends one window earlier than the floor suggests. It happens on about one
            #     epoch in `ctx`, so a single-epoch run almost never sees it and a long resampling
            #     run eventually does.
            # (2) A REAL DISAGREEMENT between the epoch length and the stream it was measured on,
            #     which is a defect somebody needs to see.
            # THIS BRANCH USED TO `break` FOR BOTH, and in case (1) that STOPPED THE RUN one window
            # before a roll it should have taken -- so a multi-epoch run would silently become a
            # one-epoch run, with a warning that called the arithmetic a defect. The window is
            # skipped either way; what changed is that the loop now falls through to the
            # finished/rolled tail below instead of leaving, so the epoch can roll.
            _short_by = (i * ctx + ctx + 1) - len(ids)
            if _short_by == 1 and not _tail_warned:
                _tail_warned = True
                warnings.append(
                    f"loop: epoch {int(tick.epoch)}'s last window has inputs and no final target "
                    f"-- len(ids)={len(ids)} is an exact multiple of LM_CTX={ctx}, and a window "
                    f"needs ctx+1 ids because `y` is `x` shifted one token. The window is skipped "
                    f"and the epoch rolls normally. This is the floor in "
                    f"spine/compose.py::_windows_in_epoch, not a defect.")
            elif _short_by != 1:
                warnings.append(
                    f"loop: the segmentation ran out at window {i} of epoch {int(tick.epoch)} and "
                    f"it is NOT the one-token tail -- it is short by {_short_by} "
                    f"(len(ids)={len(ids)}, ctx={ctx}). The epoch length and the stream it was "
                    f"measured on disagree, which is a defect rather than arithmetic.")
        else:
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
                dom_api.manage(dom_cfg, sysm.partition, now=tick.step,
                               memory_counts=_c.counts, mem_floor_entries=_c.floor_entries)
                dom_api.census(dom_cfg, sysm.partition)
                # AND THE PRESSURE VERDICT, CARRIED TO EVERY FLUSH UNTIL THE NEXT CENSUS. LOOP_ORDER's
                # B row for FAB.observe/grow_check names this shape exactly -- "memory_pressure from
                # MEM.census, which is a CADENCED producer feeding a per-flush required argument" -- so
                # the staleness is the table's design and not a shortcut. Calling census per flush
                # would materialise an 8192-entry dict and two capacity-wide reductions on every one of
                # a quarter-million flushes, to move a boolean that changes on the scale of eviction
                # pressure.
                mem_pressure = _c.pressure
            # DOM.rekey RE-ENCODES EVERY DOMAIN'S RESERVOIR WITH THE LIVE ENCODER, and it is what
            # MEASURES the acceptance radius: `radius` reads 0.0 for every domain until it runs, so on
            # a run without it DOM_RADIUS_Q, DOM_RADIUS_MULT and DOM_RADIUS_CAP are set-but-inert and
            # every assignment is decided on the pooled bootstrap (part.n_bootstrap_radius is the
            # counter that says so). `encode` is the root's ONE bound SIG.encode, for the reason
            # domains/api.py::rekey gives: a rekey that used a second encoder puts the partition into
            # two signature spaces that do not compare.
            if cadences.due("dom.rekey", periods["dom.rekey"], clock):
                dom_api.rekey(dom_cfg, sysm.partition, encode=sig_encode)
            # FAB.manage IS A STUB AND ITS CADENCE IS THEREFORE NOT ASKED. Asking it and doing nothing
            # would CONSUME the fire -- Cadences.due RECORDS the step when it answers True -- so the
            # ledger would show fab.manage firing on a run where no expert was ever culled. An
            # unevaluated gate reading checks=0 is the honest state and `skipped` names it.
            # SIG.cadence_due IS NOT ASKED FOR THE SAME REASON, AND IT IS THE STRONGER CASE: it is the
            # gate for SIG.train_step, which IS a stub, and tok/api.py::on_window's own paragraph is
            # the general rule -- "asking under a shared key CONSUMES the event: probation sharing the
            # grow key means minting never fires at all". A gate asked by nobody who can act on it is a
            # fire thrown away.
            #
            # SIG.encode, PER WINDOW, WHICH IS WHERE THE TABLE PUTS IT -- immediately above DOM.observe.
            # It used to be called once per FLUSH from inside _flush, off a second slice of the corpus;
            # both of those are now here, and `sample` is the ONE object both consumers take.
            # EPOCH-LOCAL FOR THE SAME REASON THE CUT IS: _signature_cursor multiplies `at_window` by
            # LM.ctx and indexes Segmentation.byte_pos, and `sysm.segmentation` is THIS epoch's. The
            # ordinal is 1-based there -- it is "how many windows have been reached" -- so it is the
            # cut's 0-based index plus one, which is `win_in_epoch` after the increment above.
            sample = _c_sample_window(sysm, st, win_in_epoch)
            samples.append(sample)
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
            asg = dom_api.observe(dom_cfg, sysm.partition, signature=sig_i, sample_window=sample,
                                  tokens=ids[bounds[0]:bounds[0] + ctx], now=tick.step)
            did = int(asg.did)
            dids.append(did)

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
                loss, per_window, probe_prev = _flush(
                    sysm, batch, ctx, model, pop, st, lm_cfg, fab_cfg, sig_cfg, opt_cfg, vocab, clock,
                    sysm.novelty, did, key_fn, sigs, dids, probe_prev, mem_pressure, resegment)
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
            # ---- STAGE E: THE EPOCH ROLL. DATA.draw_stream -> TOK.tokenize -> begin_epoch -------
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
            sysm.shift_at_windows = U.Windows(int(clock.step))
            # AND MEM IS TOLD, because every context it holds is token ids under a segmentation
            # that no longer exists. maintain's `resegment` arm drops and retakes the rekey
            # snapshot and counts the event; it deliberately does NOT rewrite the stored ids,
            # because that needs an old-id -> new-id mapping "not declared anywhere" (its words)
            # and inventing one would rewrite every stored token under a guess. The stale ids stay
            # visibly stale, which is what store.n_resegment_events exists to make readable.
            resegment = sysm.segmentation
            # A PENDING RETOK IS SATISFIED BY THIS ROLL, because the roll IS the act: the stream
            # was just re-segmented with the vocabulary as it now stands. Cleared here so that what
            # survives to the end of the run is only the fires no roll ever reached.
            if sysm.retok_pending:
                vocab.counters["tok.retok_satisfied_by_roll"] = \
                    vocab.counters.get("tok.retok_satisfied_by_roll", 0) + 1
                sysm.retok_pending = False
            warnings.append(
                f"loop: epoch {int(tick.epoch)} began -- redrew the stream and re-segmented at "
                f"vocabulary size {int(vocab.size())} ({prev_n} -> {len(ids)} ids). Every memory "
                f"entry written before this point holds token ids and byte offsets under the "
                f"PREVIOUS segmentation and is NOT rewritten; MEM.maintain is told, drops its "
                f"rekey snapshot and counts the event.")
            continue
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
    # WHAT THE DEFERRAL ACTUALLY COST, COUNTED ONCE AT THE END. A retok raised and never reached
    # by a roll is a fire that is gone -- Q-TOK-12's tok.due_dropped, which it says must read 0 --
    # so the two counters are kept apart: `tok.retok_deferred` is how many were raised, and
    # `tok.due_dropped` is how many of those the run never satisfied. At RUN_EPOCHS=1 they are
    # equal by construction, because the only roll a single-epoch run takes is the one that also
    # finishes it and `finished` is tested first.
    if sysm.retok_pending:
        vocab.counters["tok.due_dropped"] = vocab.counters.get("tok.due_dropped", 0) + 1
        warnings.append(
            "loop: a retok was raised and no epoch roll reached it before the run ended, so the "
            "stream was never re-segmented with the tokens this run minted. At RUN_EPOCHS=1 that "
            "is every retok the run raises: the single roll a one-epoch run takes is the one that "
            "also finishes it, and Tick requires `finished` to be tested first. Raise RUN_EPOCHS "
            "(with DATA_RESAMPLE on, which the composition root refuses to run without) to give "
            "the mints a route into the data.")
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
    for _d in dict.fromkeys(_disagree):
        warnings.append(f"loop: recorded-geometry disagreement -- {_d}")
    _disagree.clear()
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


def _windows_in_epoch_of(sysm):
    """compose.py::_windows_in_epoch, reached without importing compose at this module's top level.

    THE DIVISION IS NAMED ONCE, THERE. `len(Segmentation.ids) // LM.ctx` and `stream_bytes // ctx`
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
           novelty, domain_id, key_fn, sigs, dids, probe_prev, mem_pressure, resegment):
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
    # step". Embed and encode here; the fabric, the decode, the loss, the world terms and the
    # anchor in the second block below.
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
    # THE SIGNATURES ARE THE A STAGE'S AND ARE NOT RE-ENCODED HERE. SIG.encode is a ROW A entry
    # point sitting IMMEDIATELY ABOVE DOM.observe in LOOP_ORDER, and this function used to call it
    # itself off a second slice of the corpus -- which made the driver hold TWO SLICERS for a value
    # whose entire contract is that there is one.
    # WHAT THE TWO DISAGREED ABOUT, MEASURED: this block took `raw[byte_pos[a] : byte_pos[a] + 192]`
    # -- 192 bytes FORWARD from the window's first token -- while spine/compose.py::_sample_window
    # takes the 192 units ENDING AT THE CURSOR. Those coincide only when a window happens to be
    # exactly width_units bytes long; at the shipped geometry window 2's two slices differ
    # (b'sBsCsuupqyrCtqAq' against b'rBrDqsBsCsuupqyr') and window 5's agree. _sample_window's own
    # docstring says why that cannot stand: "ONE OBJECT, TWO CONSUMERS ... because domains/api.py::
    # observe says a rekey cannot reproduce the signature otherwise -- so a second slicer at the DOM
    # call site is a defect by construction". The defect was at the SIG call site instead, and it
    # would have put the signature DOM stores in its reservoir in a different space from the one
    # the router actually used -- exactly the drift DOM.rekey exists to prevent.
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
    with cast():
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
    # THE DTYPE THE STEP ACTUALLY RAN IN, OBSERVED AND RECORDED -- the did-it-fire surface this
    # lever had none of. `amp_state` says what was ASKED FOR and what process_setup DECIDED; it
    # cannot say whether any caller ever ENTERED the context, which is precisely the fact that was
    # false for the whole life of this driver. This is read off the tensor the step produced, and
    # run.py prints it beside amp_state so a reader compares two numbers instead of trusting one.
    sysm.process_dtype = str(logits.dtype)
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
    # the E draw row's resample, TOK.mint_burst's retok and OPT's LR restart. The first two are not
    # driven yet (the retok needs TOK.on_window's Due, a stub), so fab.shift_notifications reads 0
    # and the blackout is UNREACHABLE rather than armed -- which is precisely what that counter was
    # declared to distinguish.
    fab_api.grow_check(fab_cfg, pop, flush_loss=mean.detach(),
                       step_windows=U.Windows(int(clock.step)), soft_cap=caps,
                       memory_pressure=mem_pressure, signature=sig_vec,
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
        # PROVENANCE, PER WINDOW, FROM DOM.observe -- AND IT WAS A BROADCAST ZERO UNTIL OBSERVE
        # HAD A BODY. memory/api.py::_require_rows refuses a broadcast argument by name for exactly
        # this shape: "the six per-row arguments are six different quantities about the same rows,
        # and a broadcast one writes a whole flush under one window's provenance". `dids` is one id
        # per WINDOW, which is what the (B,) requirement means, and it is now genuinely more than
        # one value -- measured, 7 domains over 600 windows at the shipped defaults.
        sources = torch.tensor(dids, dtype=torch.long, device=dev)
        # TRUE BYTE OFFSETS, NOT AN ARANGE. MEM.write's docstring: "a token averages ~1.85 bytes
        # and the drift reached 200+ bytes per window against a 220-byte recall span". byte_pos is
        # the Segmentation's own table and the cut is `_window_bounds`'s, so the two cannot
        # disagree about which token a position is.
        bp = sysm.segmentation.byte_pos
        positions = torch.tensor([bp[a:a + ctx] for a, _b in pairs], dtype=torch.long, device=dev)
    now_w = U.Windows(int(clock.step))
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
    # IT IS None ON THE FIRST FLUSH, which maintain handles as the declared armed-but-0 reading
    # (n_probe_fired counts the CADENCE, n_probe_rows stays 0) rather than as an error.
    # THE PROBE MOVES `use`, `prob` AND `last`, AND THAT IS THE MECHANISM, NOT AN INSTRUMENT
    # EDITING ITS SUBJECT. memory/levers.py's probe_rows is emphatic that a probe must not consume
    # RNG draws, and it does not -- the stride is deterministic and MEM.read draws no randomness.
    # What it does change is which entries survive eviction, which is precisely what promotion is
    # for; an instrument that refused to promote would be the constant this repair removes.
    # resegment=None FOR THE SAME REASON THE RETOK IS NOT DRIVEN: no Due.retok is acted on, so
    # there is no RetokEvent to distribute.
    # THE TWO GATES ARE MEM'S OWN and are compared against `now` INSIDE the call -- there is no
    # Cadences key for them, which is why store.n_probe_fired / n_rekey_passes are their only
    # did-it-fire surface. Calling it once per flush is the shipped semantics: both periods are
    # Windows and elapsed-since-last-fire is phase-independent.
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
                # sig_emb IS None BECAUSE SIG.encoder_embedding IS A P4 STUB, and the consequence
                # is SIG's and not LM's: a domain centroid is a mean of encodings, so one
                # freshly-random token inside a window perturbs every signature containing it and
                # the assembler reads that as a domain shift. lm.mint.sig_rows reading 0 is the
                # third of its three declared states -- "nobody passed it" -- and it is this line.
                lm_api.on_mint(lm_cfg, model, mints, vocab.id2bytes, at_window=now_w2,
                               sig_emb=None)
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
            sysm.retok_pending = True
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
    dom_api.note_competence(cfg_dom, sysm.partition, did=domain_id,
                            bits=float(mean.detach()) / math.log(2.0))
    # THE PER-WINDOW MEAN SURPRISE IS RETURNED BECAUSE THE NEXT FLUSH NEEDS IT AS `novelty`, and
    # it is NOT the per-window loss this function returned until the MEM wiring landed. Both are
    # (B,) and both come off the same flush, which is exactly why the substitution survived: only
    # forming the quantity MEM.write names by its own definition made the two visibly different.
    return float(mean.detach()), surprise.mean(dim=1), x
