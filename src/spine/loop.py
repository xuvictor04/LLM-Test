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
    skipped = tuple(sorted(
        f"{pkg}.{name}: {why}" for pkg, name, fn, why in (
            ("WORLD", "loss_terms", getattr(__import__("world.api", fromlist=["api"]),
                                            "loss_terms"), "no world-model loss term enters the objective"),
            ("LM", "anchor_term", lm_api.anchor_term, "minted tokens are not held near their byte composite"),
            ("FAB", "own_lr_scale", fab_api.own_lr_scale, "every expert trains at the base learning rate"),
            ("FAB", "observe", fab_api.observe, "per-expert usage and competence are never recorded"),
            ("FAB", "grow_check", fab_api.grow_check, "THE FABRIC DOES NOT GROW -- no expert is ever born"),
            ("MEM", "write", __import__("memory.api", fromlist=["api"]).write,
             "NOTHING IS EVER WRITTEN TO MEMORY"),
            ("MEM", "maintain", __import__("memory.api", fromlist=["api"]).maintain,
             "no eviction, decay or rekey runs"),
            ("TOK", "mint_burst", tok_api.mint_burst, "THE VOCABULARY NEVER MINTS A TOKEN"),
            ("TOK", "judge_probation", tok_api.judge_probation, "no minted token is ever confirmed or retired"),
            ("LM", "residual_ratios", lm_api.residual_ratios, "no residual-ratio reading is produced"),
            ("DOM", "note_competence", __import__("domains.api", fromlist=["api"]).note_competence,
             "per-domain competence is never updated, so domain protection has no input"),
        ) if _is_stub(fn)))

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
    x = torch.tensor([ids[a:a + ctx] for a, b in pairs], dtype=torch.long)
    y = torch.tensor([ids[a + 1:b] for a, b in pairs], dtype=torch.long)

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
    # NOVELTY IS THE PREVIOUS FLUSH'S PER-WINDOW SURPRISE, AND THE FIRST FLUSH HAS NONE.
    # Seeded at zeros rather than at a guess, and the distinction is reportable: a zero novelty
    # says "nothing was surprising yet" for exactly one flush, which is true, where any other seed
    # would be a measurement nobody took. It is resized to this flush's batch when the two differ,
    # which happens on the last, short flush of a stream.
    nb = x.shape[0]
    if novelty is None or int(novelty.shape[0]) != nb:
        novelty = torch.zeros(nb)
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
