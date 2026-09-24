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
# THE HANDLER INSTALL LIVES IN install_save_signal BELOW, AND THIS IS THE ONLY IMPORT
# THIS PACKAGE GROWS FOR IT. tests/test_ownership.py::check_o10_no_backdoor_imports judges
# an import by the HEAD of its dotted name: head "spine" is an ALLOWLIST over
# {lever, units, derive, rng, wire, gate, init}, and a head in the set of package
# directories under src/ (minus spine) is a foreign package. "signal" is neither, so the
# standard library is outside that rule's scope. Read from the check rather than assumed,
# and MEASURED: tests/test_ownership.py is green with this import in place (2026-09-15).
import signal

import torch

from spine.lever import Config, LeverError
from spine.gate import Gate
from spine import units as U
from spine import derive


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


# ==================================================================================================
# THE SWITCH ON THE NEGATIVE-PERIOD REFUSAL -- THE OWNER'S SECOND SENTENCE, MADE REAL
# ==================================================================================================

REFUSE_NEGATIVE_PERIOD = True
"""Whether save_period refuses a negative CKPT_EVERY. True is the shipped state; False lets the
value through to units.Windows exactly as it did before 2026-09-04.

THE RULING THIS IMPLEMENTS, VERBATIM (owner, 2026-09-04): "On the periods, let's refuse for now. If
it has a bad effect, we can turn off the refusal." THE SECOND SENTENCE BINDS AS HARD AS THE FIRST.
The first is why the guard in save_period exists and why the four siblings the ruling was asked
about now carry the same one -- eval/api.py::curve_period, domains/api.py::manage_period,
fabric/api.py::manage_period and memory/api.py::rekey_period, each with a constant of this same
name at the top of its own file. The second is why this name exists at all: OFF is the state being
kept for later, and .rework/DECISIONS.md D4 rules that a thing kept for later is kept WITH A SWITCH
rather than as a code path that rots -- OFF as a first-class configuration.

WHAT IT IS NOT, so that no reader generalises it into a convention. It is NOT a precedent that a
range refusal gets a switch, and the tree it lands in is emphatic about that: lm/api.py::resolve,
opt/api.py::build and capacity/api.py::new_valve all refuse out-of-range lever values with no switch
of any kind, and none of them grows one from this. This switch exists because the owner asked for
THIS refusal to be turn-off-able, by name, in the same breath as ordering it -- and it is the only
one in the tree that was asked for.

WHERE THE FIVE REFUSALS ARE REACHABLE FROM TODAY, because "it refuses at startup" would be a claim
about a path that does not run yet. spine/compose.py::compose halts at CAP.startup_refusals, which
is row 29 of the 39 in spine/compose.py::ASSEMBLY_ORDER, while all five accessors are called at the
`cadence` row further down -- measured by running compose(environ={'DOM_MANAGE_EVERY': '-5'}) and the
four siblings' equivalents in fresh processes on 2026-09-04, every one of which ended at
CAP.startup_refusals and never reached an accessor. So the refusals are live for anything that calls
an accessor (spine/compose.py::_periods, a probe, a test) and become live for the composition root
on the day CAP.startup_refusals gets a body. That is the standing this accessor's own refusal has
had since it shipped; the four siblings inherit it rather than introduce it.

THREE SHAPES WERE WEIGHED AND TWO LOST, priced against what the tree actually has rather than
against preference.

  (a) ONE PROCESS-WIDE SWITCH OWNED BY RUN, read by all five accessors. REFUSED, AND NOT ON TASTE.
      A value one package owns and another reads is a WIRE -- a d_ field on the RECEIVING Config,
      declared in spine/assemble.py -- so this is five wires, one per receiving package, against the
      six edges that remain of spine/wire.py::WIRE_BUDGET. The wire-free routes were checked one at
      a time rather than assumed, and every one is closed by a check that is green today: a package
      may not name os.environ (tests/test_ownership.py::check_o1_one_env_reader), may not call
      from_env (check_o8_from_env_only_in_wiring_file), may not import another package or any spine
      module outside {lever, units, derive, rng, wire, gate, init}
      (check_o10_no_backdoor_imports), and spine/lever.py::Config.owned_by refuses a foreign Config
      at the read site. A new spine module holding one flag would be refused by O10 until somebody
      widened that allowlist, which is an edit to tests/ rather than to any package here.

  (b) ONE LEVER PER OWNING PACKAGE. No wire, and it is the D4-faithful shape -- D4's own subject,
      the world model, got a real lever (WORLD_ENABLED, src/world/levers.py). It loses on price and
      on what the price buys: five new environment names, five census rows and five rows in the
      generated lever document, for a policy that is ONE decision; and five INDEPENDENT switches
      make "three accessors refuse and two do not" a reachable configuration of one convention,
      which is the many-spellings-of-one-thing this whole spine exists to end. It is also the worse
      instrument for the measurement that would settle the question: spine/lever.py latches the
      assembly after one build, so a lever-shaped switch needs a fresh process per arm, while this
      constant can be set both ways inside one.

  (c) NO SWITCH AT ALL, on the reading that "we can turn off the refusal" means the owner would
      revert the change. REFUSED on the owner's own words and on D4, and the practical half is (b)'s
      last clause: with no named switch, "does the refusal have a bad effect" cannot be answered by
      running one configuration twice.

WHAT THE CHOSEN SHAPE COSTS, STATED RATHER THAN DISCOVERED. Turning it off is a CODE EDIT and not an
environment variable: there is no CKPT_REFUSE_NEGATIVE_PERIOD, this constant takes no census row and
no row in the generated lever document, and an operator holding only a shell cannot reach it. And
the name is spelled five times, once per owning package, because O10 forbids the four siblings to
import this one -- they are five per-package policies that happen to share a default, each governing
only its own package's lever, not one number stored in five places.

WHAT WOULD CHANGE THE ANSWER, since a recommendation that cannot name its own falsifier is not
finished (.rework/DECISIONS.md D11). If any configuration this project actually runs ever sets one of
the five periods negative ON PURPOSE, this stops being a guard against a typo and becomes a lever,
and (b) is then right. Measured across the repository on 2026-09-04 and the answer was none: no
script, sweep or recorded run sets any of EVAL_CURVE_EVERY, DOM_MANAGE_EVERY, FAB_MANAGE_EVERY,
MEM_REKEY_EVERY or CKPT_EVERY below zero, so the refusal is inert in every configuration that exists
and its OFF state has no user today but the person who ordered it.
"""


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
    every == 0 with the final-plus-SIGUSR1 sentence as its reason, FIRED at every > 0. THAT
    ENUMERATION IS EXHAUSTIVE ONLY BECAUSE OF THE FOURTH OUTCOME, WHICH IS NOT A GATE STATE: since
    2026-09-04 a NEGATIVE `every` reaches none of the three AT THE SHIPPED SETTING OF THE SWITCH
    BELOW, because the body refuses it by name before the period is constructed. The argument and
    the alternatives are in the body, at the guard. TWO THINGS ABOUT THAT SENTENCE ARE NEWER THAN
    THE SENTENCE AND ARE SAID HERE RATHER THAN FOUND. It is now conditional on REFUSE_NEGATIVE_PERIOD at the top of this file -- the owner's
    ruling of 2026-09-04 requires the refusal to be turn-off-able, and with it False a negative
    reaches the armed-and-not-fired state again -- through a FOURTH construction of the same gate,
    added 2026-09-05, because the two configurations are not one sentence: the `every == 0` arm
    says the only saves are the final one and any SIGUSR1, and a negative under RUN.Cadences.due's
    declared contract saves EVERY window, which is what the refusal below says a negative means.
    Both arms render the value rather than spelling it, which is why both reasons are f-strings.
    And it is no longer a statement about this accessor alone: the same ruling put
    the same guard, under the same switch, in eval/api.py::curve_period, domains/api.py::manage_period,
    fabric/api.py::manage_period and memory/api.py::rekey_period, so the clause in the body that used
    to say this refusal rules nothing for the other four has been replaced by what the owner ruled.

    WHY IT RIDES ON THE RETURNED Windows RATHER THAN CHANGING THE SHAPE OR MINTING AN ACCESSOR.
    Three alternatives, each priced by running it rather than by preference:
      (a) return (Windows, Gate), or a small record. REFUSED: this value is read UNWRAPPED into the
          `periods` mapping in spine/compose.py, which this package does not own -- at ONE site
          since 2026-09-15, spine/compose.py::_periods, because the cadence stage used to build a
          second five-key mapping inline and now passes _periods(sysm) like the audit does -- and
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

    (2) THE ATTACHMENT IS A DECLARED AFFORDANCE, AND IT USED TO WORK BY AN OMISSION (corrected
    against spine/units.py as it now stands; every measurement in the description this replaces is
    now false, and it was already false at the commit that edited the comment eighteen lines below
    it). It landed in an implicit `__dict__`: Clock declared `__slots__ = ('n',)` and the six kinds
    declared none of their own, so `'__slots__' in units.Windows.__dict__` was False and
    `period.__dict__` came back `{'gates': (...)}`. The hazard that description named -- adding
    `__slots__ = ()` to the six kinds, the ordinary tidy-up for a subclass of a slotted class --
    HAS SINCE BEEN TAKEN, and taken safely: `gates` moved onto spine/units.py::Clock's own
    `__slots__ = ('n', 'gates')`, every kind now carries `__slots__ = ()`, `period.__dict__` now
    RAISES AttributeError, and spine/units.py::_verify_gate_channel runs at import and refuses a
    Clock kind that cannot carry `.gates`, that carries a `__dict__`, or that shadows the slot --
    naming this function's gate while it does it. So this statement is protected by a check rather
    than by a reader, and the four sibling producers named above are unaffected either way. What is
    NOT at risk was checked rather than assumed: with the tuple attached, `int`/`__index__`/`bool`/`str`/`repr` are unchanged, `hash`
    is still `hash((kind name, n))` so a gated Windows hashes and compares equal to a bare one,
    and units.py's one reason for existing is intact -- `Steps(1) >= period` still raises UnitError
    and `period == 0` still raises rather than silently comparing.

    (3) NOTHING RENDERS IT YET, so the condition this Gate states reaches an OBJECT GRAPH and not
    an operator. `grep -rn "[.]line()" src/` returns exactly one call site, in opt/api.py, over
    OPT's own local list; `grep -rn "[.]gates" src/` finds SEVEN producing sites -- the five named
    above, this function's own, and ckpt/api.py::install_save_signal's ckpt.sigusr1_armed on the
    flag object it returns, which landed 2026-09-15 with that body -- and NO consumer, compose
    included. Both halves re-measured by running the grep on 2026-09-15, not by adding one to the
    old number. (Seven and not six: the paragraph above counts the packages that ALREADY produced
    one before this ruling, and re-using that number for the grep would be the off-by-one this
    file's other count paragraph is about. It read SIX until the seventh producer landed in THIS
    SAME FILE two hundred lines below it, which is the drift O12's rule is about -- open the
    sentence, do not trust it.)
    The path from here to a printed line exists -- spine/compose.py holds the same
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
                 SIGUSR1" as its reason (the reason PRINTS the value rather than naming 0, and the
                 refusal in the body is what makes 0 the only value that can reach that arm WHILE
                 REFUSE_NEGATIVE_PERIOD IS TRUE); with the owner's switch off a negative is
                 armed-and-not-fired too, on its OWN arm and with its own reason, which says a
                 negative period saves EVERY window rather than none -- the three GATE STATES are
                 still three, and it is the fourth CONSTRUCTION that keeps the sentence honest; and
                 dir off is UNREACHABLE instead of a zero the ledger cannot explain. The word an
                 operator sees is owed by RUN.cadence_audit, WHICH HAS A BODY AND RUNS: this
                 sentence read "which is a stub; until it has a body this Gate is readable only
                 from the returned object" until 2026-09-22. compose() calls it and run.py prints
                 its warnings, so the operator does see the word
    """
    ckpt = ckpt.owned_by("CKPT")
    # NOT A STUB, AND THE FOUR SIBLINGS ARE NOT EITHER -- EVAL.curve_period, DOM.manage_period,
    # FAB.manage_period and MEM.rekey_period, each verified stub-free by reading it. This
    # comment said THREE, which is the same off-by-one docs/04_CONTRACT.md corrected in its own
    # sentence about these five accessors on 2026-09-03 and eval/api.py::curve_period corrected in
    # its copy of this comment, and it survived here for the reason that document gave: the number
    # is spelled as a WORD, tests/test_contract.py's K13 reads digits, and K13's own output lists
    # "a number written in words" under NOT SEARCHED FOR -- so no check in the suite can see a
    # miscount written this way, and only a reader can. A period accessor is one
    # construction over its declared levers -- "its declared levers" and NOT "one declared lever",
    # because THIS accessor reads TWO: `every` here and `dir` through saving_on below, which the
    # LEVERS READ line already states.
    # WHAT THIS COMMENT SAID ABOUT THE FOUR AND NO LONGER SAYS, because it stopped being true on
    # 2026-09-04 and a stale claim about a neighbour is the defect this file keeps correcting: it
    # read "every one of the four ends in a bare `return U.Windows(int(<its own lever>))` and raises
    # nothing", and all four now carry the same negative-period refusal this one does, under the
    # owner's ruling recorded at REFUSE_NEGATIVE_PERIOD above. The REFERRAL that stood here in the
    # same breath -- that eval/api.py::curve_period still read "one declared lever" and named this
    # function while doing it -- is DISCHARGED in the same edit and is not merely dropped: that
    # sentence now reads "its declared levers" and states which two THIS accessor reads.
    # THE ACCESSOR'S WHOLE JOB is that Cadences.due REFUSES a bare int while Config hands one back
    # for all 35 levers that declare a Clock unit (ISSUES P1-H51; recounted r4 -- exactly 35 Lever
    # declarations across the registry carry a unit that is in spine/units.py::CLOCK_KINDS).
    # Leaving it a stub kept spine.compose._periods -- and therefore
    # RUN.cadence_audit, the one statement that makes ISSUES P1-C11 visible -- unreachable
    # until P4, for no reason but symmetry with entry points that have real work to do.
    every = int(ckpt.every)
    # A NEGATIVE SAVE PERIOD IS REFUSED HERE, AT THE ONLY PLACE `every` IS READ (added 2026-09-04).
    # WHAT IT IS: not a slower save and not a second spelling of "off". RUN.Cadences.due states its
    # own contract in this tree -- "True at most once per `period` WINDOWS elapsed since this key
    # last fired", ELAPSED-SINCE-LAST-FIRE and not modulo -- so the comparison a body writing to
    # that contract makes is `step - _fired["ckpt"] >= period.n`. At every=-5 that is true on the
    # FIRST window and on every window after it: a negative CKPT_EVERY is the MAXIMUM-frequency
    # save, a checkpoint written every window, and not the absence of one. The mechanism runs
    # backwards, which is the C30 inversion arriving through a lever VALUE, and it is the same
    # ruling capacity/api.py::new_valve made on 2026-09-04 for a negative CAP_LIFT/CAP_LIFT_MIN.
    #
    # WHAT WAS THERE BEFORE, AND WHY IT WAS NOT A MEASUREMENT. The gate below printed
    # "armed, did not fire (-5 vs 1) -- CKPT_EVERY=0 with CKPT_DIR set: the only saves this run
    # makes are the FINAL one and any SIGUSR1" -- a reason naming a value the operator did not set,
    # beside a printed value that contradicts it in the same sentence, on every CKPT_EVERY < 0
    # (measured at -5 and -1). That sentence was ALSO an unverified claim about a body that does
    # not exist: NOTHING in this tree disables periodic saving at a non-positive period.
    # Cadences.due is `raise NotImplementedError`, and the one live reader of a non-positive period
    # -- spine/derive.py::cadences_that_cannot_fire -- only REPORTS it, as ("ckpt", -5, 0). So the
    # old arm asserted a behaviour no code implements while the only stated semantics in the tree
    # give the opposite one. Printing the value instead of asserting it (done below) fixes the
    # false equation; it does not fix the hazard, which is that the body P4 writes to that contract
    # checkpoints every window on a typed minus sign, silently, with this Gate saying saving is off.
    #
    # IT REMOVES NO CONFIGURATION. "Never save periodically" is CKPT_EVERY=0 -- in range, the
    # declared default, and the meaning the lever's own help text gives it ("0 disables periodic
    # saving, leaving the final save and SIGUSR1"). "Save as often as possible" is CKPT_EVERY=1.
    # The negative range spells neither, and the help text spells no meaning for it at all.
    #
    # REFUSED EVEN WHEN CKPT_DIR IS OFF, deliberately: this is a range check over CKPT's own lever,
    # not a statement about whether the run persists anything, and a value that names no mechanism
    # should not be silently accepted because a second lever happens to make it moot. That is the
    # same placement capacity's refusal takes (it precedes the CAP_TARGETS=off branch).
    #
    # WHAT THIS RULED, AND WHAT THE OWNER RULED AFTER IT (2026-09-04). This clause used to end
    # "whether that spine-wide convention should become a refusal for all five is an OWNER question
    # and is filed as one". It was filed, and the answer is YES: the other four period accessors --
    # EVAL.curve_period, DOM.manage_period, FAB.manage_period, MEM.rekey_period -- now each refuse a
    # negative value of their own lever at their own first read, in the same shape and with the same
    # switch. What remains unruled, and is NOT settled by any of the five, is the OTHER end:
    # spine/derive.py::cadences_that_cannot_fire still treats "zero or less" as ONE sentinel for
    # every package at once, while zero means something different in each -- disabled periodic
    # saving here, DISARM in memory/api.py::maintain, an unimplemented port requirement in
    # src/domains/levers.py, and nothing declared at all for EVAL and FAB. Refusing the negatives
    # narrows that reader's input to values whose meaning each package has actually written down;
    # it does not make the four zeros mean one thing.
    if REFUSE_NEGATIVE_PERIOD and every < 0:
        raise LeverError(
            f"CKPT_EVERY={every}: a save period is a count of windows ELAPSED since the last save "
            f"and may not run backwards. RUN.Cadences.due DECLARES its contract as 'True at "
            f"most once per `period` WINDOWS elapsed since this key last fired' -- its body is "
            f"still a P4 stub, so this is a statement about the contract and not about running "
            f"code -- and a body written to that contract compares `step - last_fired >= "
            f"period`, so a negative period is true on the first window and on every window after "
            f"it -- {every} does not mean 'save less often' or 'do not save', it means a "
            f"checkpoint written EVERY window, which is the opposite of what this gate reported "
            f"for it until 2026-09-05. Neither meaning is lost: CKPT_EVERY=0 is the declared "
            f"default and disables "
            f"periodic saving (the final save and SIGUSR1 remain), and CKPT_EVERY=1 saves on every "
            f"window. CKPT_DIR is not consulted here: this refuses an out-of-range value for "
            f"CKPT's own lever, whether or not a second lever makes it moot.")
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
    elif every == 0:
        # THE VALUE IS PRINTED, NOT ASSUMED, AND ZERO NOW HAS THIS ARM TO ITSELF. This reason was
        # the literal string "CKPT_EVERY=0 with CKPT_DIR set: ..." until 2026-09-04, so at any
        # CKPT_EVERY below zero the gate rendered "armed, did not fire (-5 vs 1) -- CKPT_EVERY=0
        # ..." -- a reason naming a value the operator did not set, beside a printed value that
        # contradicts it, in one sentence. Measured at -5 and at -1 before the change. Rendering
        # the value instead of spelling it fixed the EQUATION and left the SENTENCE wrong, which is
        # what this split repairs: with the value rendered, `else` still handed one claim to two
        # configurations that mean opposite things -- "the only saves are the FINAL one and any
        # SIGUSR1" is true of 0 and false of every negative, which the REFUSE_NEGATIVE_PERIOD
        # guard earlier in this same function says in as many words ("a checkpoint written EVERY
        # window"). MEASURED BEFORE THE SPLIT, with
        # REFUSE_NEGATIVE_PERIOD set False and CKPT_DIR=runs/x: at -5 and at -1 this arm rendered
        # "armed, did not fire (-5 vs 1) -- CKPT_EVERY=-5 with CKPT_DIR set: the only saves this
        # run makes are the FINAL one and any SIGUSR1", i.e. the printed value and the named value
        # agreed and the CLAIM ABOUT THE MECHANISM was the opposite of this file's own reading of a
        # negative period. The negative has its own arm below; this one is now pinned to the single
        # value it describes, and it stays an f-string so the printed number cannot drift from the
        # named one.
        gate = Gate("ckpt.periodic_armed", False, every, 1,
                    reason=f"CKPT_EVERY={every} with CKPT_DIR set: 0 is this lever's declared "
                           f"disable-periodic-saving state, so the only saves this run makes are "
                           f"the FINAL one and any SIGUSR1. A legitimate configuration, and one "
                           f"the report must SAY -- without this line it is indistinguishable "
                           f"from a run that is not saving at all.")
    else:
        # THE NEGATIVE ARM, AND IT IS REACHABLE -- WHICH WAS ESTABLISHED BY RENDERING IT RATHER
        # THAN BY READING THE GUARD. The refusal above takes every negative WHILE
        # REFUSE_NEGATIVE_PERIOD IS TRUE, so at the shipped setting nothing reaches here; but that
        # constant is a DECLARED first-class configuration (see its own docstring at the top of
        # this file, and .rework/DECISIONS.md D4), not a dead branch, and with it set False
        # `assemble.build(environ={'CKPT_EVERY': '-5', 'CKPT_DIR': 'runs/x'})` reaches this arm --
        # measured at -5 and at -1, both rendering "armed, did not fire". So this is NOT an
        # UNREACHABLE arm and must not be spelled as one: `reachable=False` here would report a
        # mechanism the operator can still configure as one no configuration reaches.
        gate = Gate("ckpt.periodic_armed", False, every, 1,
                    reason=f"CKPT_EVERY={every} with CKPT_DIR set, and this arm is reached ONLY "
                           f"with ckpt/api.py::REFUSE_NEGATIVE_PERIOD set False: a negative is NOT "
                           f"the disable state and this run is not saving less often than a "
                           f"positive one. RUN.Cadences.due DECLARES its contract as 'True at most "
                           f"once per `period` WINDOWS elapsed since this key last fired' -- its "
                           f"body IS WRITTEN and implements exactly that -- this sentence said "
                           f"'still a P4 stub, so this is a statement about the contract and not "
                           f"about running code' until 2026-09-22 -- and that body "
                           f"compares `step - last_fired >= {every}`, which is true on the FIRST "
                           f"window and on every window after it: a checkpoint EVERY window, the "
                           f"opposite of what the zero arm one step above prints. The refusal this "
                           f"switch turns off says the same thing, and the two readings may not "
                           f"share one sentence.")
    period.gates = (gate,)
    return period


# best_state_supplied / best_state_absent ARE SEEDED HERE WITH THE OTHER SIX, and the pair is what
# makes the M45 repair readable. A defaulted keyword is invisible to K10 -- nothing in the contract
# checks can tell a caller that passes `best_state` from one that does not -- so the counter is the
# only surface that separates "the composition root never wired it" from "it was wired and the
# retention had no best to record yet". fabric/api.py::grow_check carries fab.shift_notifications
# for exactly this hazard and says so in the same words.
_SAVES = {"periodic": 0, "sigusr1": 0, "best": 0, "bestN": 0, "final": 0,
          "best_state_supplied": 0, "best_state_absent": 0,
          "best_keep_by_slot": 0, "refused_off": 0}
"""The DID IT FIRE ledger for CKPT.save, SEEDED AT ZERO rather than created on first use.

A counter that appears only once it is non-zero cannot be read as "armed and it did not happen",
which is the distinction this package's whole reporting surface is built on. `refused_off` is the
one that makes "0 saves" legible: without it, a run with CKPT_DIR=off and a run whose period never
came due print the same nothing.
"""


def save(ckpt: Config, *, payload, geometry, step, epoch, reason, best_state=None, suffix=""):
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
    TWO MORE THE BODY WRITES, DECLARED HERE for the reason fabric/api.py::forward gives (a key in
    the report the contract does not admit to producing is the same defect as a declared key nothing
    writes): best_state_supplied / best_state_absent, the pair that says whether the composition
    root is passing `best_state` at all. A DEFAULTED KEYWORD IS INVISIBLE TO K10, so without these
    "nobody wired it" and "it was wired and the retention had no best yet" are one number --
    fab.shift_notifications exists for the identical hazard and is quoted in full at _SAVES.
    """
    ckpt = ckpt.owned_by("CKPT")
    if not saving_on(ckpt):
        # SIX COUNTERS, BECAUSE "0 SAVES" CANNOT DISTINGUISH "NEVER DUE" FROM "SAVING IS OFF".
        # This is the branch that makes the second one readable, and it returns False rather than
        # raising: turning saving off is a legitimate thing to ask for.
        _SAVES["refused_off"] = _SAVES.get("refused_off", 0) + 1
        return False
    if reason not in ("periodic", "sigusr1", "best", "bestN", "final"):
        raise ValueError(
            f"CKPT.save: reason={reason!r} is not one of the five recorded routes. The reason is "
            f"RECORDED so the log can name the route that fired rather than describing the "
            f"mechanism that did nothing.")

    # THE SUFFIX APPLIES TO THE WHOLE SNAPSHOT, WHICH IS P1-M46. `ck = ck + suffix` (:5335-5337)
    # suffixed the checkpoint while TOK.save(_TOK_SAVE) (:5344-5348) ALWAYS wrote the BASE
    # vocabulary path, so every later save overwrote the file a .bestN snapshot records as its own;
    # by the end of a run a .best checkpoint's recorded merge count no longer matched the file it
    # names, and resuming from it tripped the VOCABULARY MISMATCH refusal at :4380-4408. best_keep
    # multiplies that n times over. The repair is that TOK.save_vocabulary takes THE SAME suffix
    # this call takes; this function owns the checkpoint half of it and names the other half here
    # so the two cannot drift apart again.
    # A SNAPSHOT'S VOCABULARY IS PART OF THE SNAPSHOT BUT NOT PART OF `payload`: the merges live in
    # the FILE at d_vocab_save_path and build_vocabulary REPLAYS them on a resume, while
    # TOK.vocab_state carries "everything a resume needs THAT THE MERGE LIST ALONE DOES NOT CARRY".
    d = str(ckpt.dir)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "ckpt.pt" + (suffix or ""))
    tmp = dst + ".tmp"
    # `best_state` GOES IN THE BLOB, AND UNTIL 2026-09-21 THIS DICT DID NOT HAVE THE KEY AT ALL --
    # WHILE load() READ IT. ckpt/api.py::load is unambiguous: "`best_state` IS IN THE CHECKPOINT
    # (ISSUES P1-M45)", and its body does `best_state = blob.get("best_state")`, which on every
    # checkpoint this tree has ever written returned None. So Snapshot.best_state was always None,
    # new_retention(restored=None) started cold on every resume, and THE FIRST POST-RESUME PROBE
    # SATISFIED "no best yet" AND OVERWROTE THE PARENT'S BEST MODEL. That is M45 itself, live, in
    # the function whose whole job is to stop it -- and spine/compose.py's own C row says so in
    # advance: "Without it the first post-resume probe satisfies 'no best yet' and overwrites the
    # parent's best model (M45)".
    # THE SIGNATURE MOVED FOR THIS, which is a frozen-surface change and is not taken lightly. It
    # is the shape fabric/api.py::grow_check's `shift_at=None` already established: a DEFAULTED
    # keyword, so no existing caller breaks, plus a counter that says whether anyone is supplying
    # it -- because a defaulted argument is invisible to K10 and "nobody wired it" would otherwise
    # be indistinguishable from "it was wired and the retention had nothing to record yet".
    # NOT PART OF `payload`, which is the composition root's opaque per-package mapping. The C row
    # calls best_state "a FIELD OF ITS OWN and not part of payload", and Snapshot declares it as a
    # field beside payload rather than inside it, because CKPT is the package that owns retention
    # and this is the one value in the file that is CKPT's own rather than a package's.
    _k = "best_state_supplied" if best_state is not None else "best_state_absent"
    _SAVES[_k] = _SAVES.get(_k, 0) + 1
    blob = {"payload": payload, "geometry": geometry, "best_state": best_state,
            "step": int(step), "epoch": int(epoch), "reason": reason}
    # ATOMIC, AND ONE PREVIOUS GENERATION KEPT. A half-written checkpoint that replaces a good one
    # is worse than no checkpoint: torch.save straight onto `dst` leaves exactly that on any
    # interruption, and a run's whole history is in this one file.
    torch.save(blob, tmp)
    if os.path.exists(dst):
        prev = dst + ".prev"
        try:
            os.replace(dst, prev)
        except OSError:
            # A FAILED ROTATION MUST NOT LOSE THE NEW GENERATION. The replace below still runs.
            pass
    os.replace(tmp, dst)
    _SAVES[reason] = _SAVES.get(reason, 0) + 1
    if reason == "bestN":
        _SAVES["best_keep_by_slot"] = _SAVES.get("best_keep_by_slot", 0) + 1
    # RETURNS True IFF A FILE WAS WRITTEN. The caller used to assume success and printed "saved to
    # None.best".
    return True


class _SaveFlag:
    """The SIGUSR1 save flag: `kill -USR1 <pid>` sets it, the loop drains it with take().

    PRIVATE BY NAME, AND THAT IS A CONTRACT FACT RATHER THAN A STYLE ONE. install_save_signal's
    docstring calls the returned object "a Flag object with .take()", and a module-level class
    named `Flag` with a method named `take` IS a public entry point to
    tests/test_contract.py::api_signatures, which walks every public ClassDef in a package's
    api.py and records its public methods. MEASURED 2026-09-15 by spelling it `Flag` and running
    tests/test_contract.py: K1 reported `src/ckpt/api.py defines 'CKPT: Flag.take(self)', which
    the document does not declare`, and the tree's entry-point total moved. That is the same
    refusal save_period's docstring records for a new public accessor, and it lands in
    docs/04_CONTRACT.md and the entry-point counts, which a body writer may not take unilaterally.
    The OBJECT is as public as it ever was -- the composition root binds it to System.save_flag and
    the loop calls .take() on it -- it is the NAME in this module that is not an entry point.

    THE DRAIN IS A HIGH-WATER MARK, NOT A read-and-clear ASSIGNMENT, and the difference is a lost
    signal. `if self._set: self._set = False; return True` is two bytecodes with a window between
    them: CPython runs a Python-level signal handler BETWEEN bytecodes, so a SIGUSR1 arriving in
    that window sets the flag and the very next store clears it, and the operator's save never
    happens with nothing said. Counting arrivals and remembering how many have been drained closes
    it: a signal that lands after the snapshot leaves `_received` ahead of `_drained`, so the next
    take() still returns True. The handler is the only writer of `_received` and take() is the only
    writer of `_drained`, so neither races itself.

    `_received` DOUBLES AS THE DID IT FIRE COUNT for the SIGUSR1 route -- the arrivals, against
    Saves.sigusr1's writes -- which is the pair that tells "nobody pressed it" from "it was pressed
    and nothing was saved".
    """

    __slots__ = ("_received", "_drained", "armed", "gates")

    def __init__(self):
        self._received = 0
        self._drained = 0
        self.armed = False
        self.gates = ()

    def _arrive(self, signum, frame):
        """The handler. ONE integer increment and NOTHING ELSE.

        NEVER torch.save IN HERE -- reentrancy (self_organize.py:5457-5462, whose own comment says
        "never torch.save inside a handler"). A handler runs between arbitrary bytecodes, so it can
        land in the middle of the allocator, the autograd engine or a half-written .tmp file; the
        save happens at the next SAFE point, which is the loop's own drain beside the periodic
        save.
        """
        self._received += 1

    def take(self):
        """Read-and-clear: True iff at least one SIGUSR1 has arrived since the last call.

        Returns a BOOLEAN and not a count on purpose -- the loop's question is "save now?", and n
        signals between two drains are one save, which is what the old tree's `_ckpt_req["on"]`
        boolean meant (self_organize.py:7710-7712). The arrivals are not lost: `_received` keeps
        counting them for the report.
        """
        seen = self._received          # ONE read; a signal arriving after it leaves _received
        if seen == self._drained:      # ahead of _drained and is taken on the NEXT call.
            return False
        self._drained = seen
        return True


def install_save_signal():
    """Arm `kill -USR1 <pid>`: sets a flag the loop drains beside the periodic save. Returns a Flag
    object with .take() (read-and-clear).

    NOT A LEVER AND IT NEEDS NONE (:7709); recorded here so that "the only saves are the final one
    plus the cadence" is not read as complete. NEVER torch.save inside a handler -- reentrancy
    (:5457-5462).

    THE ARMING IS REPORTED, WHICH IS THE ONE THING THE OLD TREE DID NOT DO. self_organize.py:5462
    reads `try: _signal.signal(_signal.SIGUSR1, _on_usr1) except (ValueError, OSError): pass`, and
    its own trailing comment says what that costs -- "not the main thread / unsupported platform ->
    silently skip". The next four lines (:5464-5467) then PRINT, unconditionally, "checkpoint-on-
    demand: kill -USR1 <pid> -> saves to <dir> at the next step". So on exactly the configurations
    where the install had just failed, the run told the operator the mechanism was armed. That is
    the armed-but-inert collapse spine/gate.py exists to refuse, in its most expensive form: an
    operator sends the signal to a long run, the process takes the DEFAULT SIGUSR1 disposition, and
    the default disposition for SIGUSR1 is to TERMINATE. The repair is not to let the exception
    out -- a run must not die because it could not arm a convenience -- it is to SAY SO, on the
    object the root already holds.

    THE STATE IS A spine.gate.Gate ON `.gates`, WHICH IS THE TREE'S SHAPE FOR THIS AND NOT A NEW
    ONE. Five entry points already hand their gates back on an attribute of that name
    (fabric/api.py::build, capacity/api.py::new_valve, memory/api.py::open_store,
    tok/api.py::build_vocabulary, sig/api.py::warm_up as a dict), and ckpt/api.py::save_period
    attaches one to the period it returns; this is the seventh producing site and save_period's own
    count paragraph is corrected in the same edit. A private `armed`/`reason` pair instead would be
    the thirteen-private-Gate-classes shape spine/gate.py's docstring refuses in as many words.
    `.armed` IS ALSO SET, as the plain bool the loop branches on, and it is the SAME fact the gate
    renders -- one source, two readings, not two answers.

    THREE ARMS, AND THE FIRST TWO ARE NOT THE SAME STATEMENT. A platform whose `signal` module has
    no SIGUSR1 at all can never deliver one; a platform that HAS it and refuses the install (this
    is not the main thread) could deliver one to a process that arranged it differently. Both are
    UNREACHABLE for this run and both carry a reason, because Gate refuses an unreachable arm
    without one -- but a reader who sees "no SIGUSR1 on this platform" looks for a different fix
    than one who sees "not the main thread".

    NOTHING RENDERS THE GATE YET, the same residue save_period's cost (3) records: `grep -rn
    "[.]gates" src/` still finds no consumer, compose included, so this state reaches an object
    graph and not an operator until the report lands. It is on the System (spine/compose.py binds
    it to sysm.save_flag), which is where a renderer will look.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: Saves.sigusr1 counts the saves this route caused; the flag's own `_received`
                 counts the signals that ARRIVED, and the two differ exactly when a signal was
                 taken and the save was refused. The gate on `.gates` answers the prior question --
                 whether the route could be armed at all -- which nothing in the old tree asked.
    """
    flag = _SaveFlag()
    # getattr AND NOT hasattr-THEN-ACCESS: the same lookup twice is two chances to disagree, and
    # the number is wanted for the gate's printed value anyway. SIGUSR1 is absent on Windows, where
    # the signal module defines only the six ANSI C signals plus SIGBREAK.
    signum = getattr(signal, "SIGUSR1", None)
    if signum is None:
        flag.gates = (Gate("ckpt.sigusr1_armed", False, None, "SIGUSR1", reachable=False,
                           reason="this interpreter's `signal` module declares no SIGUSR1, so "
                                  "`kill -USR1` cannot be delivered to this process at all and no "
                                  "handler would be reached if one were installed. Reported "
                                  "UNREACHABLE rather than as an unmet condition, which would send "
                                  "an operator to send a signal that does not exist here. The "
                                  "periodic and final saves are unaffected."),)
        return flag
    try:
        signal.signal(signum, flag._arrive)
    except Exception as e:                  # noqa: BLE001 -- see the two sentences below
        # BROAD ON PURPOSE, AND NOT SILENT. The old tree caught (ValueError, OSError) and passed;
        # ValueError is what CPython raises off the main thread ("signal only works in main thread
        # of the main interpreter"), OSError what a platform refusal raises, and RuntimeError what
        # a sub-interpreter raises -- but the contract this arm owes is "an exception from
        # signal.signal does not escape", and naming three types is a promise about a stdlib
        # implementation rather than about this function. The TYPE AND MESSAGE ARE RENDERED into
        # the gate, so nothing that lands here is swallowed: a class nobody predicted shows up by
        # name in the report instead of as a dead mechanism.
        flag.gates = (Gate("ckpt.sigusr1_armed", False, f"{type(e).__name__}: {e}", "SIGUSR1",
                           reachable=False,
                           reason=f"signal.signal(SIGUSR1) was refused by this process with "
                                  f"{type(e).__name__}: {e} -- the usual cause is that the run was "
                                  f"started off the main thread, where CPython refuses to install "
                                  f"a handler. The run continues and the exception is NOT "
                                  f"re-raised: a run must not die because it could not arm a "
                                  f"convenience. But `kill -USR1` now takes this process's DEFAULT "
                                  f"SIGUSR1 disposition, which TERMINATES it, so an operator who "
                                  f"believes the old tree's unconditional 'checkpoint-on-demand' "
                                  f"line kills the run instead of checkpointing it. Reported "
                                  f"UNREACHABLE: the periodic and final saves are unaffected and "
                                  f"no configuration of CKPT's levers changes this arm."),)
        return flag
    flag.armed = True
    # FIRED = THE HANDLER IS INSTALLED. This gate's subject is the ARMING and not a save: its name
    # says `armed`, and the save this route causes is counted by Saves.sigusr1, which is CKPT.save's
    # surface. The printed pair is the signal number against the name, because the number is what
    # an operator's `kill -<n>` takes and it is not 10 everywhere (it is 10 on Linux/x86-64, 30 on
    # macOS, 16 on some MIPS ABIs), so rendering the name alone would be the one thing a reader
    # cannot check.
    flag.gates = (Gate("ckpt.sigusr1_armed", True, int(signum), "SIGUSR1"),)
    return flag


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
    # `.dyntok.json` to a path that already ended in `.pt` (ISSUES P1-M19). THIS COMMENT CLAIMED
    # "every later consumer -- the vocabulary read path among them -- sees one shape" and the
    # vocabulary read path never saw this function's result: spine/assemble.py computed it from the
    # raw lever, and both non-bare forms were refused for a missing parent vocabulary that was on
    # disk (driven 2026-09-24). The two now share ONE string rule, spine/derive.py::checkpoint_base,
    # which is the run base both the file below and '<base>.dyntok.json' are built from.
    if raw.endswith(".pt"):
        return raw
    base = derive.checkpoint_base(raw, file_form=True)
    return os.path.join(base, "ckpt.pt") if raw.endswith(("/", os.sep)) or os.path.isdir(base) \
        else raw


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


@dataclasses.dataclass(frozen=True)
class GeometryField:
    """One geometry knob as the composition root resolved it: the value, the direction it may move,
    the environment name to print, and why it is checked at all.

    `rule` IS THE OWNER'S AND NOT THIS PACKAGE'S, because the direction differs per field --
    MAY_WIDEN for FAB's slots and LM's vocab_slots (the tensors are preallocated and a smaller-cap
    checkpoint IS a prefix, and refusing to widen would mean a resume can never add capacity for
    the area it is adding, which is the whole exercise), EXACT for inner dimensions where no prefix
    is valid. spine/compose.py::_geometry_manifest builds these as plain 4-tuples so the rule stays
    with the root that knows it; this record is what they are read back as.
    """
    value: object
    rule: str
    env_name: str
    why: str


@dataclasses.dataclass(frozen=True)
class GeometryReport:
    """Every field the gate looked at, with its rule and BOTH values -- and the ones it could not.

    `unchecked` IS THE H22 STATE MADE VISIBLE, and it is the reason this is a record rather than a
    bool. :5365-5366 recorded six world fields and :4590 read exactly one, so five were carried in
    every checkpoint and compared by nothing, and no line anywhere said so. A field present in the
    checkpoint and ABSENT from the manifest is listed here by name.
    """
    checked: tuple
    unchecked: tuple
    widened: tuple


class GeometryRefusal(ValueError):
    """A checkpoint that cannot load into this run's shapes, raised BEFORE THE FIRST ALLOCATION.

    Its own class because the caller must be able to tell it from a torch error: the whole point of
    the gate is that "it can be failing on FAB_EMB_HID, SIG_D or D_MODEL and no prefix of it means
    anything" (:4678-4684) becomes one sentence naming one knob and both numbers.
    """


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
    recorded = dict(getattr(snapshot, "geometry", None) or {})
    checked, widened = [], []
    # DRIVEN OFF THE MANIFEST'S KEY SET, NOT OFF TRUTHINESS, AND THAT IS THE SHAPE OF THE REPAIR.
    # The fabric's three branches were each guarded on `_ck_cap and ...`, so a checkpoint with no
    # "cap" slid through all three and reached load_state_dict as the five-shape dump this gate
    # exists to replace (:4432-4441). Iterating the manifest makes `if recorded and recorded !=
    # live` -- the untrippable-guard shape -- unwritable here: a field the manifest names and the
    # checkpoint lacks is a REFUSAL, not a skip.
    def _value_of(spec):
        """The VALUE out of a manifest entry, whichever of the three shapes it arrived in.

        BOTH SIDES GO THROUGH THIS, AND THE FIRST DRAFT ONLY PUT THE LIVE SIDE THROUGH IT. The
        checkpoint stores the manifest as written -- 4-tuples -- so `recorded[field]` is
        (value, rule, env_name, why) and not a bare number, and comparing that tuple against the
        live scalar made EVERY field unequal: the gate refused LM_WIDTH for moving from 128 to 128.
        Caught by driving a checkpoint the same run had just written, which is the only comparison
        that could have caught it, since both sides are built from one manifest.
        """
        if isinstance(spec, GeometryField):
            return spec.value
        if isinstance(spec, tuple) and len(spec) == 4:
            return spec[0]
        return spec

    for field, spec in (geometry or {}).items():
        if isinstance(spec, GeometryField):
            value, rule, env_name, why = spec.value, spec.rule, spec.env_name, spec.why
        elif isinstance(spec, tuple) and len(spec) == 4:
            value, rule, env_name, why = spec
        else:
            value, rule, env_name, why = spec, "EXACT", field, "no rule recorded"
        if field not in recorded:
            raise GeometryRefusal(
                f"{env_name}: this run resolves {field}={value!r} and the checkpoint records no "
                f"{field} at all. A missing field is refused rather than skipped -- a checkpoint "
                f"with no entry used to slide past every guard that tested it for truthiness and "
                f"arrive at load_state_dict as a shape dump naming nothing. ({why})")
        was = _value_of(recorded[field])
        if was == value:
            checked.append((field, rule, was, value))
            continue
        if rule == "MAY_WIDEN" and isinstance(was, int) and isinstance(value, int) and was < value:
            # THE PREFIX DIRECTION, AND IT IS THE ONE THAT MAKES GOAL B RUNNABLE. Refusing to widen
            # would mean a resume can never add capacity for the area it is adding.
            widened.append((field, rule, was, value))
            checked.append((field, rule, was, value))
            continue
        raise GeometryRefusal(
            f"{env_name}: the checkpoint was written at {field}={was!r} and this run resolves "
            f"{value!r}. The rule for this field is {rule}"
            + (", so it may grow but not shrink." if rule == "MAY_WIDEN" else
               ", so it may not move at all -- it is an inner dimension and no prefix of it is "
               "valid.")
            + f" ({why}) Resume with the saved value, or start a new run.")
    # A FIELD THE CHECKPOINT CARRIES AND THE MANIFEST DOES NOT NAME IS REPORTED, NOT IGNORED. That
    # is H22 from the other end: six world fields were recorded and exactly one was read, and
    # nothing said which five were along for the ride.
    unchecked = tuple(sorted(set(recorded) - set(geometry or {})))
    return GeometryReport(checked=tuple(checked), unchecked=unchecked, widened=tuple(widened))


# ==================================================================================================
# THE RETENTION RECORD
# ==================================================================================================

@dataclasses.dataclass(frozen=True)
class BestAction:
    """What one held-out probe earned. Returned by Retention.consider.

    TWO INDEPENDENT ANSWERS, NOT ONE VERDICT, and the old tree ran them as two separate tests for a
    reason. The single global best is `_cm < _best_bpb[0]` -- strict improvement, one file that is
    overwritten every time. The rotation slot is the WEAKER "descent into a good region" test at
    self_organize.py:6478-6479, which is a deliberate SUPERSET of the local minima. A probe can
    earn both, either, or neither, and collapsing them into one boolean would lose the distinction
    the two levers exist to express.

    `rotate_slot` IS A SLOT NUMBER AND NOT A SUFFIX STRING. 1-based, exactly as
    self_organize.py:6480 computed it (`_slot = (len(_bkeep) % BEST_KEEP) + 1`). It stays a number
    because the same value is spliced into TWO artifact names by two different packages --
    spine/compose.py's LOOP_ORDER hands the SAME `suffix` to CKPT.save and to TOK.save_vocabulary,
    which is the whole of M46's fix -- so a Retention that returned the rendered string ".best3"
    would be deciding a spelling this package does not own, on behalf of one that does. None means
    no rotation was earned by this probe.
    """
    save_best: bool
    rotate_slot: object = None


def new_retention(ckpt: Config, *, restored=None):
    """The best-model policy. Returns Retention.

    LEVERS READ: best_keep, best_keep_tol, dir (through saving_on, for the inert_reason's
                 saving-is-off clause -- the same parenthetical save_period's LEVERS READ line
                 carries for the same reason, added 2026-09-15 when this body was written. The
                 line named two levers while spine/compose.py's `persist` row REQUIRED this
                 entry point to know whether saving is on: "it must precede new_retention, whose
                 inert_reason is populated when best_keep > 0 AND SAVING IS OFF". A LEVERS READ
                 line that omits a lever the body must read is the prose half of the same defect
                 K4 exists to catch on the other side)
    WIRES READ: none
    DID IT FIRE: Retention.counters() -> (probes_seen, new_bests, rotations, slots_used,
                 inert_reason). `inert_reason` is populated when best_keep > 0 and saving is off,
                 and when NO CURVE VALUE HAS EVER ARRIVED -- which at P3 is always, and must read
                 as armed-but-inert rather than as zero local lows.

    TWO OBLIGATIONS THE FROZEN SIGNATURES CANNOT MEET, WRITTEN DOWN RATHER THAN FAKED.

    (1) `best_saved` CANNOT MEAN "WRITTEN TO DISK" HERE, AND IT DID IN THE OLD TREE. `_best_bpb`
        was `[best, step, saved?]` (self_organize.py:4243) and the third slot was set from the
        RETURN of the save, and the rotation ring appended a slot only `if _save_ckpt(...)`
        returned True (:6481-6483) -- so the old tree's ring recorded slots that were actually
        written. In this tree CKPT.save is a separate entry point the COMPOSITION ROOT calls
        (docs/04_CONTRACT.md section 3.2: the fan-out is rows, not calls inside CKPT.save), it
        returns True iff a file was written, and NO frozen entry point on this object takes that
        answer back. So `best_saved` here means A SAVE WAS ORDERED and the ring records slots
        ORDERED, not slots on disk. WHAT WOULD CLOSE IT: one more entry point on this class --
        `Retention.note_saved(ok, slot=None)` -- called from the C rows beside CKPT.save. That is
        a contract edit (docs/04_CONTRACT.md's ```contract block, K1, K13's entry-point count and
        a LOOP_ORDER row), not a body fix, so it is REFERRED and not taken here.
    (2) THE INERT CLAUSE IS PINNED TO best_keep > 0 AND THE GAP IS ONE LEVER WIDE. At
        best_keep == 0 the single global best is equally unsaveable with CKPT_DIR off -- 0 is not
        "off", ckpt/levers.py::CKPTLevers.best_keep says 0 means exactly what BEST_TRACK=1 did, a
        single rotating .best -- but the condition this body must implement is spelled twice
        outside this file, in spine/compose.py's `persist` ASSEMBLY_ORDER row and again at the
        `retention` call site, both as "best_keep > 0 AND SAVING IS OFF". Widening it here would
        make this body and the root's own prose disagree, which is the drift the order tables are
        data to prevent. It costs nothing at P3: the second clause -- no curve value has ever
        arrived -- populates inert_reason on every configuration anyway.

    TWO REFUSALS, BOTH OVER THIS PACKAGE'S OWN LEVERS, AND NEITHER GETS A SWITCH. That is not an
    omission: REFUSE_NEGATIVE_PERIOD at the top of this file states in as many words that it is
    NOT a precedent -- "lm/api.py::resolve, opt/api.py::build and capacity/api.py::new_valve all
    refuse out-of-range lever values with no switch of any kind, and none of them grows one from
    this" -- because the owner asked for THAT refusal to be turn-off-able by name.
      * best_keep < 0. The old tree wrote `BEST_KEEP = max(0, _i("BEST_KEEP", 0))`
        (self_organize.py:4235), a coercion at read time that makes a printed number a lie: the
        report at :9615 renders `BEST_KEEP={BEST_KEEP} slots`, so an operator who typed -2 was
        shown 0 and told nothing. That is the FAB_MIN_STEPS shape this rebuild refuses by name.
      * best_keep_tol outside 0..1. spine/units.py::FRACTION is the string "fraction 0..1" and
        that IS the declared range; spine/lever.py does not enforce it (FRACTION is a label, not a
        validator -- checked by reading Lever.coerce, which has no per-unit range hook). A
        NEGATIVE tolerance inverts the lever: `best * (1 + tol)` falls BELOW the best, so the
        "how close to the best a descending probe must land" test starts demanding a probe
        strictly BETTER than the best by a margin, which is the mechanism running backwards -- the
        same reading save_period's guard gives a negative period.
    NEITHER REFUSAL CAN FIRE ON A CONFIGURATION THIS REPOSITORY SHIPS, checked rather than assumed
    on 2026-09-15: `grep -rn BEST_KEEP` over the tree finds longrun.sh:421 (BEST_KEEP=2),
    longrun.sh:430 (BEST_KEEP=4), longrun.sh:519-521 and notes/CURRENT_DEFAULTS.md
    (BEST_KEEP=0, BEST_KEEP_TOL=0.02) -- every one of them in range.
    """
    ckpt = ckpt.owned_by("CKPT")
    keep = int(ckpt.best_keep)
    tol = float(ckpt.best_keep_tol)
    if keep < 0:
        raise LeverError(
            f"CKPT_BEST_KEEP={keep}: the number of rotating .best1..bestN slots to retain is a "
            f"COUNT and there is no mechanism a negative one names. Neither meaning is lost: 0 is "
            f"the declared default and keeps the single global .best alone (it is what BEST_TRACK=1 "
            f"did before the merge), and n > 0 keeps n recent local lows on top of it. Refused "
            f"rather than clamped: self_organize.py:4235 read this lever as "
            f"`max(0, _i('BEST_KEEP', 0))` and the end-of-run report at :9615 then printed "
            f"'BEST_KEEP={{BEST_KEEP}} slots' from the clamped value, so an operator who typed a "
            f"negative was shown 0 and told nothing.")
    if not 0.0 <= tol <= 1.0:
        raise LeverError(
            f"CKPT_BEST_KEEP_TOL={tol}: the tolerance is a FRACTION OF the best held-out "
            f"bits/byte seen so far (spine/units.py::FRACTION is the string 'fraction 0..1', and "
            f"that is the declared range -- spine/lever.py::Lever.coerce does not enforce it, "
            f"which is why the refusal is here). The test is `probe <= best * (1 + tol)` "
            f"(self_organize.py:6479), so a NEGATIVE tolerance puts the admission threshold BELOW "
            f"the best and demands a probe strictly better than the best by a margin -- the "
            f"opposite of 'how close to the best a descending probe must land', which is this "
            f"lever's own help text -- and a tolerance above 1 admits anything up to twice the "
            f"best, which fills the rotation with the warmup weights ckpt/levers.py::CKPTLevers."
            f"best_keep_tol says this lever exists to keep out. 0.0 admits only a probe at or "
            f"below the best itself; the shipped default is 0.02.")
    # saving_on IS CALLED, NOT RE-TYPED. The six spellings of off live in one predicate in this
    # file, and re-testing them at a call site is the defect that wrote a directory literally
    # named `0` into the repository root. The ROOT already computed this value one stage earlier
    # (spine/compose.py's `persist` row records it on the System as sysm.saving) and this call is
    # a SECOND evaluation of the same pure predicate over the same frozen Config -- not a second
    # source of truth, because Config is frozen after spine.assemble.build returns, so the two
    # calls cannot disagree. The alternative -- a `saving` parameter -- is a frozen-signature
    # change to an entry point docs/04_CONTRACT.md declares.
    return Retention(keep=keep, tol=tol, saving=saving_on(ckpt), restored=restored)


class Retention:
    """The best-model policy object. Constructed by new_retention().

    STATE ROUND-TRIPS AS PLAIN PYTHON, NOT AS SPINE OBJECTS. state() is written into the
    checkpoint as Snapshot.best_state and read back by torch.load; a units.Windows or a Gate in
    that blob would make the FILE depend on this tree's import path, so every number that crosses
    the disk boundary is an int, a float, a bool or None. The KIND is not lost, it is asserted at
    the door instead: consider() refuses a `step` that is not units.Windows.
    """

    __slots__ = ("_keep", "_tol", "_saving", "_best_bpb", "_best_step", "_best_saved",
                 "_prev_probe", "_slots", "_ordered", "_probes_seen", "_new_bests", "_rotations")

    # THE FIVE FIELDS state() WRITES AND new_retention(restored=) READS BACK, in one place, because
    # a restore that quietly accepts a blob missing one of them is M45 arriving through the repair
    # for M45: the first post-resume probe would satisfy "no best yet" and overwrite the parent's
    # best-by-held-out snapshot with the Adam re-warm bump.
    _STATE_FIELDS = ("best_bpb", "best_step", "best_saved", "prev_probe", "ring")

    def __init__(self, *, keep, tol, saving, restored=None):
        self._keep = keep
        self._tol = tol
        self._saving = saving
        # THE COLD START IS THE OLD TREE'S, FIELD FOR FIELD: `_best_bpb = [None, -1, False]`
        # (self_organize.py:4243) and `_prev_probe = [None]` (:4244). -1 and not 0 for the step,
        # because 0 is a step a run actually reaches and "no best yet" must not be readable as
        # "the best was at the very first window".
        self._best_bpb = None
        self._best_step = -1
        self._best_saved = False
        self._prev_probe = None
        self._slots = {}          # {slot: (bpb, step)} -- the resident ring contents
        self._ordered = 0         # rotations ORDERED, i.e. self_organize.py:6480's len(_bkeep)
        self._probes_seen = 0
        self._new_bests = 0
        self._rotations = 0
        if restored is None:
            return
        # A RESTORE THAT CANNOT BE READ IS A REFUSAL, NOT A COLD START. `restored` is
        # Snapshot.best_state, and the entire reason that field is in the checkpoint is M45: a
        # resume that started the best-so-far cold overwrote the PARENT's best model with the
        # first post-resume probe. Falling back to the cold start on an unrecognised blob would
        # reproduce M45 exactly, silently, on every resume from a checkpoint this code cannot
        # read. A checkpoint written BEFORE best_state existed carries None and takes the cold
        # path above -- that is the one legitimate absence, and it is spelled as None.
        if not isinstance(restored, dict):
            raise ValueError(
                f"CKPT.new_retention(restored=...): Snapshot.best_state is "
                f"{type(restored).__name__}, not the mapping CKPT.Retention.state() returns. "
                f"Accepting it and starting cold would be M45 -- the first post-resume probe "
                f"satisfies 'no best yet' and overwrites the parent's best-by-held-out snapshot "
                f"with the Adam re-warm bump -- arriving through the field that exists to fix it. "
                f"A checkpoint written before best_state existed carries None, which IS handled "
                f"and starts cold.")
        missing = [f for f in self._STATE_FIELDS if f not in restored]
        if missing:
            raise ValueError(
                f"CKPT.new_retention(restored=...): Snapshot.best_state is missing "
                f"{missing!r}. CKPT.Retention.state() writes all of {list(self._STATE_FIELDS)!r}; "
                f"a partial one cannot be told from a corrupted one here, and guessing a default "
                f"for a missing best is M45.")
        self._best_bpb = None if restored["best_bpb"] is None else float(restored["best_bpb"])
        self._best_step = int(restored["best_step"])
        self._best_saved = bool(restored["best_saved"])
        self._prev_probe = None if restored["prev_probe"] is None else float(restored["prev_probe"])
        ring = restored["ring"] or {}
        # THE RING CARRIES ITS POINTER AND NOT ONLY ITS CONTENTS, which is why `ring` is a mapping
        # and not the bare {slot: ...} the phrase "rotation ring" first suggests. The slot a low
        # lands in is `(rotations_ordered % keep) + 1`, so once the ring has wrapped, len(contents)
        # is keep and no longer says where the next one goes: a resume that recomputed the pointer
        # from the contents would restart the rotation at slot 1 and overwrite the OLDEST
        # surviving low first on a ring that is already full -- rotating, but not in the order the
        # mechanism claims.
        self._ordered = int(ring.get("ordered", 0))
        self._slots = {int(s): (float(v["bpb"]), int(v["step"]))
                       for s, v in dict(ring.get("slots") or {}).items()}

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

        NO CALLER EXISTS AND THIS BODY DOES NOT CREATE ONE. spine/compose.py's
        DEFERRED_ENTRY_POINTS names this entry point "P5, WITH EVAL.curve_probe": nothing in the
        tree produces `curve_bpb`, because eval/api.py::curve_probe is itself deferred for want of
        units_by_domain and logits_fn. The deferral is about the ROW, not the body -- and writing
        the body is what lets counters() tell "armed and no probe has ever arrived" from "probes
        arrived and none qualified", which is the exact statement that same table demands
        ("Retention.counters() must report inert_reason='no curve value has ever arrived' rather
        than a bare zero").

        `step` MUST BE units.Windows AND A BARE int IS REFUSED. docs/04_CONTRACT.md's producer
        table says this argument IS RunClock.step, which train/api.py::RunClock carries as a
        units.Windows, and the number is RECORDED -- it goes into the checkpoint as best_step and
        into the report as the window the best model was at. A Flushes or a Steps arriving under
        the same name is the pin_tick defect with nothing to catch it, because this function makes
        no cross-kind comparison that units.py could raise on.

        A NON-FINITE PROBE IS REFUSED, AND THE COST OF ACCEPTING ONE WAS MEASURED (2026-09-15,
        python3 over the two comparisons this body makes). `-inf < best` is True, so a single
        divergent probe becomes the global best and NOTHING CAN EVER BEAT IT: 2.4, 1.9, 0.5 and
        0.0 all compare False against a best of -inf, so the one file that holds the good model --
        which ckpt/levers.py::<module> says is the only copy of it that exists, 1.1-1.3 b/B better
        than the model the report generates from -- is frozen at garbage for the rest of the run
        and the run says nothing. A NaN is milder and still silent: `nan < best` and
        `nan < prev - 1e-6` are both False, so the probe itself is inert, and the NEXT probe's
        descent test runs against a NaN predecessor and is False too -- exactly one rotation
        opportunity lost, invisibly. Refused here rather than reported, because this is an input
        that is not a measurement; the DIVERGENCE it signals is EVAL's to alarm on
        (derive.blowup_stale), which is the same division of labour the blow-up paragraph above
        states.
        """
        if not isinstance(step, U.Windows):
            raise U.UnitError(
                f"CKPT.Retention.consider: step is {type(step).__name__}({step!r}), not "
                f"units.Windows. docs/04_CONTRACT.md's producer table says this argument is "
                f"RunClock.step, which train/api.py::RunClock carries as units.Windows, and the "
                f"value is RECORDED -- it becomes best_step in the checkpoint and the window the "
                f"report names the best model at. A bare int carries no kind, so a Flushes count "
                f"arriving here would be off by the batch width with nothing to raise on it.")
        cm = float(curve_bpb)
        # `cm != cm` IS THE NaN TEST WITHOUT AN IMPORT. math.isnan would do as well; the pair of
        # comparisons below is the whole check and both arms are cited in the docstring.
        if cm != cm or cm in (float("inf"), float("-inf")):
            raise ValueError(
                f"CKPT.Retention.consider: curve_bpb={curve_bpb!r} is not a finite bits/byte "
                f"measurement. Measured 2026-09-15: at -inf the global best is captured "
                f"permanently -- 2.4, 1.9, 0.5 and 0.0 all lose to it -- so the .best snapshot, "
                f"which is the only copy of the good model this run will hold, is frozen at a "
                f"divergent probe with nothing said; at NaN both comparisons this body makes are "
                f"False, so the probe is inert AND the next probe's descent test is lost. The "
                f"divergence itself is EVAL's to alarm on (spine/derive.py::blowup_stale), not "
                f"this policy's to absorb.")
        self._probes_seen += 1
        # BOTH TESTS READ THE STATE AS IT WAS BEFORE THIS PROBE. Snapshotting `prev` and `best`
        # here is not defensive style, it is what makes the two arms independent of the order they
        # are written in: the tolerance arm compares against `_best_bpb`, and updating the best
        # first would compare a new best against ITSELF. It happens to admit the same probes
        # either way -- if cm is a new best then cm <= cm * (1 + tol) for any tol >= 0, and
        # cm <= best_old * (1 + tol) too since cm < best_old -- but "the answer is the same" is a
        # property of today's rule, not of the shape, and the shape should not depend on it.
        prev, best = self._prev_probe, self._best_bpb
        save_best = False
        rotate_slot = None
        if best is None or cm < best:
            self._best_bpb = cm
            self._best_step = int(step)
            self._new_bests += 1
            # ORDERED ONLY WHERE THERE IS SOMEWHERE TO WRITE. With CKPT_DIR off the NUMBER is
            # still tracked -- the report must be able to say what the best was even on a run that
            # saved nothing -- but ordering a save that CKPT.save would refuse as refused_off
            # would put a save this run did not make into BestAction, and Saves.refused_off exists
            # precisely so "0 saves" can name which route was never taken.
            save_best = self._saving
            self._best_saved = save_best
        if (self._keep > 0 and self._saving and prev is not None and best is not None
                and cm < prev - 1e-6 and cm <= best * (1.0 + self._tol)):
            # 1-BASED AND ROUND-ROBIN OVER ORDERS, NOT OVER RESIDENTS: self_organize.py:6480 is
            # `_slot = (len(_bkeep) % BEST_KEEP) + 1`, and _bkeep grows by one per low TAKEN. The
            # difference from the old tree is owned in new_retention's obligation (1): _bkeep grew
            # only when the save RETURNED True, and nothing hands that answer back here, so this
            # pointer counts orders.
            rotate_slot = (self._ordered % self._keep) + 1
            self._slots[rotate_slot] = (cm, int(step))
            self._ordered += 1
            self._rotations += 1
        # THE PREVIOUS PROBE IS UPDATED ON EVERY PROBE, QUALIFYING OR NOT (self_organize.py:6487,
        # `_prev_probe[0] = _cm`, which sits OUTSIDE the keep block). The descent test asks whether
        # the curve went down since the LAST reading, not since the last reading that qualified.
        self._prev_probe = cm
        return BestAction(save_best=save_best, rotate_slot=rotate_slot)

    def state(self):
        """The retention state for the checkpoint: (best_bpb, best_step, best_saved, prev_probe,
        rotation ring). Restored by new_retention(restored=...). This is the M45 fix.

        A MAPPING AND NOT THE FIVE-TUPLE THE LINE ABOVE READS LIKE. The parenthesised list names
        the CONTENTS, the way this file's other record lines do (Saves(periodic, sigusr1, best,
        best_keep_by_slot, final, refused_off); Resume(attempted, loaded, ...)). It is a dict for
        two reasons that are not taste: this value is written to disk and read back by
        new_retention in a LATER PROCESS, possibly built from a different commit, and a positional
        tuple turns any added field into a silent re-binding of the wrong value rather than the
        named refusal __init__ raises; and every DID IT FIRE surface in this tree that has a body
        -- RUN.RunClock.counters, RUN.Cadences.ledger, CAP.Valve.counters -- is a name->value
        mapping, so a report that reads them all reads one shape.

        `best_saved` MEANS "A SAVE WAS ORDERED", NOT "A FILE EXISTS". See new_retention's obligation
        (1): CKPT.save returns True iff a file was written and no frozen entry point carries that
        answer back to this object. The same caveat governs the ring's contents.
        """
        return {
            "best_bpb": self._best_bpb,
            "best_step": self._best_step,
            "best_saved": self._best_saved,
            "prev_probe": self._prev_probe,
            # THE POINTER TRAVELS WITH THE CONTENTS -- see __init__'s ring comment: once the ring
            # has wrapped, the number of resident slots no longer says where the next low goes.
            "ring": {"ordered": self._ordered,
                     "slots": {s: {"bpb": b, "step": st}
                               for s, (b, st) in sorted(self._slots.items())}},
        }

    def counters(self):
        """(probes_seen, new_bests, rotations, slots_used, inert_reason) -- the DID IT FIRE surface
        for the retention half of this package.

        A MAPPING, for the reason state() gives: the five written counters()/ledger() surfaces in
        this tree are all name->value mappings, and a positional five-tuple read at a report site
        is how a count gets printed under the wrong label.

        `inert_reason` IS COMPUTED HERE AND NOT FROZEN AT CONSTRUCTION, because one of its two
        clauses is about a RUNTIME fact -- whether any probe has ever arrived -- and a reason
        computed at build time would say "no curve value has ever arrived" for the whole run,
        including after one had.

        `rotations` COUNTS ORDERS, `slots_used` COUNTS RESIDENTS, and the two differ once the ring
        wraps: self_organize.py:9612-9615 printed exactly this pair -- "N local low(s) taken, M
        still on disk ... earlier ones were overwritten" -- and the second number is len() of the
        slot map, not of the history.
        """
        return {
            "probes_seen": self._probes_seen,
            "new_bests": self._new_bests,
            "rotations": self._rotations,
            "slots_used": len(self._slots),
            "inert_reason": self._inert_reason(),
        }

    def _inert_reason(self):
        """The armed-but-inert sentence, or "" when the mechanism has actually been exercised.

        TWO CLAUSES, BOTH OF WHICH CAN HOLD AT ONCE, so they are joined rather than chosen between.
        The old tree printed one of them and only under `if BEST_KEEP:` (self_organize.py:9620-9622,
        "BEST-KEEP: ARMED ... and took NOTHING ... Either the run never improved after its first
        probe, or SAVE_CKPT is off so every save returned False") -- an OR of two causes it had not
        distinguished, on a line a run with best_keep == 0 never reached at all. These are two
        separate statements and each is only made when it is true.

        THIS IS NOT A spine.gate.Gate, deliberately. `inert_reason` is the name the frozen
        docstring on new_retention and both mentions in spine/compose.py's DEFERRED_ENTRY_POINTS
        give it ("Retention.counters().inert_reason must report 'no curve value has ever
        arrived'"), and it is a FIELD OF counters(), not a separate DID IT FIRE channel. A Gate
        beside it would be a second, differently-shaped answer to one question.
        """
        clauses = []
        if self._keep > 0 and not self._saving:
            clauses.append(
                f"CKPT_BEST_KEEP={self._keep} with CKPT_DIR off: the rotation is armed and there "
                f"is nowhere to write, so no probe can earn a slot however good it is. Raising "
                f"CKPT_BEST_KEEP changes nothing; setting CKPT_DIR does.")
        if self._probes_seen == 0:
            clauses.append(
                "no curve value has ever arrived: CKPT.Retention.consider has not been called "
                "once, so 0 new bests and 0 rotations are not a measurement of this run's curve. "
                "EVAL.curve_probe is deferred (spine/compose.py::DEFERRED_ENTRY_POINTS -- nothing "
                "produces units_by_domain or logits_fn), which is the whole reason the event "
                "cannot arrive.")
        return " ".join(clauses)
