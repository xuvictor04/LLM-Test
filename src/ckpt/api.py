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
  Snapshot         payload, geometry, step, epoch, best_state
  GeometryField    value, rule (EXACT | MAY_WIDEN | MAY_NARROW), env_name, why
  GeometryReport   checked, unchecked, refused, both values per field
  Saves            periodic, sigusr1, best, best_keep_by_slot, final, refused_off
  Resume           attempted, loaded, step_restored, epoch_restored, best_restored
  Retention        the best-model policy object; BestAction(save_best, rotate_slot)
"""
from spine.lever import Config
from spine import units as U


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
    raise NotImplementedError(
        "CKPT.saving_on: P4 (ckpt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CKPT.")


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

    LEVERS READ: every
    WIRES READ: none
    DID IT FIRE: Cadences.ledger()["ckpt"]; plus a declared Gate for the :5619-5621 warning -- dir
                 set and every == 0 means the only save is the final one plus SIGUSR1, printed with
                 its own condition rather than as a warning string
    """
    ckpt = ckpt.owned_by("CKPT")
    # NOT A STUB, AND THE THREE SIBLINGS ARE NOT EITHER. A period accessor is one
    # construction over one declared lever, and its whole job is that Cadences.due REFUSES a
    # bare int while Config hands one back for all 35 levers that declare a Clock unit
    # (ISSUES H51). Leaving it a stub kept spine.compose._periods -- and therefore
    # RUN.cadence_audit, the one statement that makes ISSUES C11 visible -- unreachable
    # until P4, for no reason but symmetry with entry points that have real work to do.
    return U.Windows(int(ckpt.every))


def save(ckpt: Config, *, payload, geometry, step, epoch, reason, suffix=""):
    """Write one checkpoint generation ATOMICALLY (.tmp + os.replace, one previous generation kept).
    Returns True iff a file was written -- the caller used to assume success and printed "saved to
    None.best".

    `reason` is one of "periodic" | "sigusr1" | "best" | "bestN" | "final" and is RECORDED, so the
    log can name the route that fired rather than describing the mechanism that did nothing.

    THE SUFFIX APPLIES TO THE WHOLE SNAPSHOT, NOT ONLY TO ckpt.pt. ISSUES M46: `ck = ck + suffix`
    (:5335-5337) suffixed the checkpoint while `TOK.save(_TOK_SAVE)` (:5344-5348) ALWAYS wrote the
    BASE vocabulary path, so every later save overwrote the file a .bestN snapshot records as its
    own; by the end of a run a .best checkpoint's recorded merge count no longer matches the file
    it names and resuming from it trips the VOCABULARY MISMATCH refusal at :4380-4408. best_keep
    multiplies that defect n times over. A SNAPSHOT'S VOCABULARY IS PART OF THE SNAPSHOT: the
    tokenizer bytes go in `payload`, and the d_vocab_save_path wire names the run's own directory.

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
    raise NotImplementedError(
        "CKPT.resume_source: P4 (ckpt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CKPT.")


def load(ckpt: Config):
    """Read the resume source. Returns Snapshot(payload, geometry, step, epoch, best_state) or None.

    `best_state` IS IN THE CHECKPOINT -- ISSUES M45: `_best_bpb` starts cold on every process
    (:4243) and nothing carried it, so the first post-resume probe satisfied "no best yet" and
    OVERWROTE THE PARENT'S best-by-held-out snapshot with the Adam re-warm bump. That is this
    package's own bug, not a coupling: the best-so-far is checkpoint state.

    LEVERS READ: resume
    WIRES READ: none
    DID IT FIRE: Resume(attempted, loaded, step_restored, epoch_restored, best_restored)
    """
    ckpt = ckpt.owned_by("CKPT")
    raise NotImplementedError(
        "CKPT.load: P4 (ckpt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CKPT.")


def check_geometry(ckpt: Config, snapshot, geometry):
    """Refuse a checkpoint that cannot load into this run's shapes, NAMING THE KNOB. Raises
    GeometryRefusal; returns a GeometryReport when it passes.

    `geometry` is {field: GeometryField(value, rule, env_name, why)} assembled by the composition
    root from each package's own geometry() call. RULES ARE THE OWNER'S, because the direction
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

    LEVERS READ: none -- this is mechanism
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

        curve_bpb IS AN ARGUMENT, NOT A WIRE. eval/levers.py:124 declares an outgoing d_curve_bpb
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
        window. ISSUES L43: `_cs = [b for st, _p, b, _a in _CURVE if st == step]` ran once per
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
