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

WHAT THIS DRIVER SKIPS, AND WHY IT SAYS SO OUT LOUD
====================================================
Eleven entry points on LOOP_ORDER's B row are still `raise NotImplementedError`. A driver that
simply did not call them would produce a run whose report is indistinguishable from a run where
those mechanisms were ARMED AND DID NOTHING -- which is the two-states-printed-as-one collapse this
whole tree is built to refuse, arriving in the one file that decides what runs.

So every skipped mechanism is recorded in `RunResult.skipped`, by name, with the reason, and the
progress line prints the count. A reader of this run's output can tell "the fabric did not grow"
from "the fabric's growth was never called", which are different facts about different runs.

WHAT A RUN ON THIS DRIVER MEASURES TODAY: goal A's core -- a language model, routed through the
fabric, trained by the optimizer on the corpus DATA draws. WHAT IT DOES NOT MEASURE: goal B. The
fabric does not grow, memory is never written, the vocabulary never mints, domains are never
scored and the world model contributes no loss. Continual learning is a claim about what survives
a second pass through mechanisms that are, today, not called.
"""
import dataclasses
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
})

# CALLS THIS DRIVER MAKES THAT ARE NOT B-ROW ENTRY POINTS. The clock, which LOOP_ORDER lists under
# RUN and which `run` drives directly, and SIG.encode, which is a ROW A entry point -- the
# per-window signature -- that the flush needs before FAB.forward can route on it.
# THE CROSS-CHECK BELOW FOUND SIG.encode ON ITS FIRST RUN, which is the guard doing its job: the
# first draft of _CALLS listed it as though it were a B-row name, and a set that quietly disagreed
# with the table is exactly what the check exists to refuse. Row A, not row B, measured through
# spine/compose.py::plan().
_NOT_B_ROW = frozenset({"RUN.RunClock.advance", "RUN.RunClock.note_backward", "SIG.encode"})

# WHY EACH UNWIRED MECHANISM'S ABSENCE MATTERS, in the consequence a reader needs rather than the
# name they already have. Missing keys fall back to a plain sentence; nothing here is load-bearing
# for correctness, only for legibility.
_WHY = {
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

    curve, t0 = [], time.time()
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

        if tick.flush_due:
            loss, per_window = _flush(sysm, batch, ctx, model, pop, st, lm_cfg, fab_cfg, sig_cfg,
                                      opt_cfg, vocab, clock, sysm.novelty)
            # NOVELTY CROSSES BACKWARDS, WHICH IS WHY IT LIVES ON THE SYSTEM AND NOT IN A RETURN.
            # compose.py's row says it: "novelty is the PREVIOUS flush's mean surprise
            # (self_organize.py:7499), carried on System.novelty because it crosses backwards and
            # `produces` reads forwards only". The loop is the only thing that can carry it, so the
            # loop writes it here, after the flush that measured it.
            sysm.novelty = per_window
            batch = []
            if loss is not None:
                last_loss = loss
                if curve == []:
                    first_loss = loss
                curve.append(loss)
            # THE BACKWARD IS COUNTED BY THE CLOCK AND NOWHERE ELSE, and the optimizer steps only
            # when the clock says a step is due -- derive.accum_due on a Backwards clock, never a
            # modulo on the window counter. Two real runs one line apart measured 55 optimizer
            # steps where 13 were due.
            if clock.note_backward():
                opt_api.maybe_step(opt_cfg, sysm.optimizer)

        # THE PERIODIC CHECKPOINT, THROUGH THE SAME Cadences EVERY OTHER GATE USES. A 53-minute
        # run finished with `ckpt checks=0` -- the gate was never EVALUATED, so nothing was written
        # and the trained weights were lost at process exit. That is what this call is: not a
        # refinement, a repair. It is evaluated per window rather than per flush because the period
        # is in WINDOWS and Cadences.due is phase-independent by construction.
        if cadences.due("ckpt", periods["ckpt"], clock):
            _save(sysm, clock, "periodic")
        # AND THE SIGUSR1 FLAG, DRAINED ONCE PER WINDOW. CKPT.install_save_signal armed it at
        # compose; take() returns True exactly once per `kill -USR1`, so a checkpoint is written on
        # demand without the run being stopped to get one.
        if sysm.save_flag is not None and sysm.save_flag.take():
            _save(sysm, clock, "sigusr1")

        if progress and cadences.due("progress", periods["progress"], clock):
            print(f"[{int(tick.step)} windows] loss={last_loss:.4f} "
                  f"opt_steps={int(clock.counters()['opt_steps'])} "
                  f"skipped_mechanisms={len(skipped)}", flush=True)

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
    final_written = _save(sysm, clock, "final")
    if not final_written:
        warnings.append(
            "loop: no final checkpoint was written -- CKPT_DIR names no directory, so saving is "
            "off and this run's weights end with the process. Set CKPT_DIR to keep them.")

    c = clock.counters()
    return RunResult(
        windows=int(c["step"]), opt_steps=int(c["opt_steps"]), flushes=int(c["flushes"]),
        epochs=int(c["epoch"]), loss_first=first_loss, loss_last=last_loss,
        loss_curve=tuple(curve), elapsed_s=time.time() - t0, skipped=skipped,
        cadence_ledger=cadences.ledger(), warnings=tuple(warnings))


def _periods_of(sysm):
    """compose.py::_periods, reached without importing compose into this module's top level."""
    from spine import compose as _c
    return _c._periods(sysm)


def _flush(sysm, batch, ctx, model, pop, st, lm_cfg, fab_cfg, sig_cfg, opt_cfg, vocab, clock,
           novelty):
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
        domain_id=0, live_domains=1, training=True)
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
    logits = lm_api.decode(lm_cfg, model, h,
                           live_vocab=int(vocab.live_size()), retired_ids=tuple(vocab.retired))
    per_window, mean = lm_api.lm_loss(lm_cfg, logits, y)
    total = mean if aux is None else (mean + aux)
    opt_api.scaled_backward(opt_cfg, sysm.optimizer, total)
    # THE PER-WINDOW VECTOR IS RETURNED BECAUSE THE NEXT FLUSH NEEDS IT. This is the reason
    # LM.lm_loss keeps reduction='none' and hands back both: "competence attribution, the domain
    # EMA and the marginal-contribution counterfactual all read them and none of them can be
    # tracked without them" -- and so, it turns out, can the fabric's routing.
    return float(mean.detach()), per_window.detach()
