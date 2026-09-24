"""FAB's repaired behaviour, exercised: real forward and backward passes over a real assembled Config.

    python3 tests/test_fabric.py          # PASS/FAIL per check with counts; non-zero exit on any FAIL

WHY THIS FILE EXISTS. Every other file in tests/ checks src/ without ever entering a PACKAGE:
tests/test_ownership.py walks src/ with `ast` and does not execute it, tests/test_census.py and
tests/test_contract.py read the tree and compare it against itself, tests/test_derive.py replays a
captured table through pure functions, tests/test_couplings.py runs each declared coupling's `compute`
and tests/test_determinism.py replays spine/rng.py and spine/derive.py in fresh subprocesses -- the last
two do EXECUTE code, and an earlier draft of this line called them all static. None of them calls
FAB.forward or FAB.build -- and the gap is wider than that, measured rather than grepped:
running each of the SEVEN pre-existing files under runpy leaves `"fabric.api" in sys.modules` FALSE for
every one, so no test had ever imported FAB's entry points, let alone called one. THE PACKAGE ITSELF IS
imported, and an earlier draft of this paragraph said otherwise: the same measurement leaves `fabric`
AND `fabric.levers` in sys.modules after FIVE of the seven -- tests/test_assemble.py,
tests/test_census.py, tests/test_contract.py, tests/test_couplings.py and tests/test_ownership.py --
because assemble.build imports every package's levers module through the registry. The two that leave
nothing are tests/test_derive.py and tests/test_determinism.py. This one sentence has now carried a
wrong count in three consecutive rounds (two files, then four, and it is five), so it is written with
the measurement beside it: `runpy.run_path` each of the seven and read sys.modules after.
It is `fabric.api` that nothing reached, which is the claim that matters and the one that stands.
(grep alone is misleading here: tests/ carries 15 `from fabric...` lines outside this file -- ownership
12, couplings 2, contract 1, and 12+2+1 is 15. It was published as 17 one round ago; 17 is the total
WITH this file's own 2. Every one of the 15 is inside a triple-quoted source fixture the AST checks
parse, or a comment. The count is eight files in tests/ counting this one, seven without it;
tests/test_determinism.py is one of the seven and an earlier draft of this paragraph omitted it.)
Meanwhile fabric/api.py has taken the most behaviourally delicate repairs in the project, and until this
file every one of them was protected by nothing -- a static check cannot see a NaN, cannot see a
gradient that went to zero, and cannot see a counter that reads 1 over a term that reaches no parameter.
WHAT IS ACTUALLY UNIQUE ABOUT THIS FILE IS NARROWER THAN "the only one here that RUNS things", and it is
the measured form: no src/<pkg>/api.py module is in sys.modules after ANY of the seven, so this is the
only file in tests/ that enters a package entry point at all. It is not the only one that executes src/
-- test_couplings and test_determinism do -- and not the only one that imports torch, which
test_determinism also does, lazily, inside its activation probe.

WHAT IT COVERS AND WHAT IS LEFT. FAB has eleven public entry points and eight of them still raise
NotImplementedError (`grep -n "raise NotImplementedError" src/fabric/api.py` -> 8 sites: observe,
contribution, manage, grow_check, own_lr_scale, counters, state_dict, load_state_dict). The three with
bodies are `build`, `forward` and `manage_period`, and all three are exercised here -- so this file is
not a sample of FAB's behaviour, it is all of the behaviour FAB currently has.

THE NINE REPAIRS EACH CHECK STANDS OVER, and what each one cost when it was absent (the measurements
are in .rework/audits/r_fabric.json, x_fabric.json, y_fabric.json and z_fabric.json, taken at wider
widths than these; the reproductions below are re-taken here at the smallest widths that still exercise
the mechanism, and every number this file asserts on is either analytic or a comparison between two
runs):

  F1  src/fabric/api.py::_var_cov returned NaN at one live expert -- torch's var(dim=0) is UNBIASED, so
      it divided by n-1 = 0, one line ABOVE a guard written for the covariance and placed below it. The
      NaN reached aux_loss at step 0 and ALL 28 LM tensors and ALL 20 FAB tensors by step 1, and
      FAB_EMB_VAR could not switch it off because NaN * 0 is NaN.
  F2  src/fabric/api.py::_identities let a pass that cannot carry a graph WRITE the identity cache. One
      no_grad pass -- a leave-one-out counterfactual, and separately an ordinary EVAL pass -- stamped a
      graphless tensor under the current window, and the next TRAINING pass was handed it: grad|A|max
      EXACTLY 0.0 on the arms where the ae round trip is off, i.e. the one gradient channel that reaches
      every live expert deleted by a pass that was only looking, with every counter and every gate
      reading exactly as before.
  F3  fab.balance_nonzero -- THE C2 ALARM, whose whole job is to say "the load-balance term is
      multiplying a zero" -- went blind when the aux_loss repair (F5) gave its accumulator's seed a
      graph. Its test, `bal.grad_fn is not None`, became true by construction and it reported a
      genuinely dead balance term as live.
  F4  Eleven negative magnitude levers are refused. Three of them -- FAB_BALANCE, FAB_PONDER,
      FAB_EMB_VAR -- multiply their terms UNGUARDED, so a negative did not switch the mechanism off,
      it ran it BACKWARDS; the other eight are guarded at `> 0.0` and a negative was bit-identical to
      0.0 while the gate printed the operator's negative beside a reason asserting the value was 0.
      THE SUBJECT SPLIT ON 2026-09-14 AND THIS CHECK SPLIT WITH IT: src/fabric/levers.py gave
      FAB_DISCOVER `domain=(0.0, 2.0)`, a domain is checked at the FIRST read, and
      src/fabric/api.py::build's entry for that one lever could never fire again -- so the entry was
      RETIRED and ten of the eleven are refused there while the eleventh is refused by its own
      declaration. The check no longer asserts "the refusal under test is FAB's". It asserts WHICH
      LAYER owns which lever, reads that split off the declarations rather than off a list typed in
      this file, and drives it at BOTH doors: the environment, and a Config built directly, which is
      the one path a declaration does not stand in.
  F5  FabricOut.aux_loss must be "ONE scalar with a graph -- never a float and never a freshly allocated
      zero" (its own frozen docstring). Both switched-off arms returned exactly the freshly allocated
      zero it names, and the composition root SUMS this field into the objective it backwards, so a
      graphless summand is an error at neither end.
  F6  Two gradient-carrying training passes at one step_windows are refused by name. Before the refusal
      they raised torch's bare "Trying to backward through the graph a second time" at FAB_ROUTE_LEARN=1
      and raised NOTHING at FAB_ROUTE_LEARN=0, silently applying one window's ponder anneal, balance
      anneal, spawn test and halt EMA twice.
  F7  Nine gate reasons asserted "FAB_<LEVER>=0" instead of printing the value they read. A Gate
      printing a FALSE EQUATION is worse than one printing nothing.
  F8  manage_period exists because Config hands back a bare int for every lever that declares a clock
      unit while RUN's Cadences.due refuses one, and a negative cadence is refused TWICE on the way
      to a reader -- once in spine/derive.py::flush_period_windows during assembly, once at FAB's own
      read under the switch src/fabric/api.py::REFUSE_NEGATIVE_PERIOD (.rework/DECISIONS.md D4).
      Nothing had called manage_period at all, and no check held either refusal, or the switch's OFF
      position, to meaning anything. ZERO joined the assembly's half on 2026-09-14: it was carrying
      three simultaneous answers -- Flushes(1) from the coupling, Windows(0) from the accessor and
      "cannot fire" from spine/derive.py::cadences_that_cannot_fire -- with no declared meaning to
      protect, and this check required Windows(0) of it until then.
  F9  src/fabric/api.py's fab.cull_gate printed a VERDICT WORD AND A PAIR OF NUMBERS THAT DISAGREE in
      one rendered line, and shipped that way for six rounds because nothing compared a verdict against
      its own arithmetic. spine/derive.py::cull_gate_open is two clauses -- a floor on the live
      population and an occupancy test -- and the pair printed the second one alone, so at FAB_N0=2
      FAB_SLOTS=2 FAB_PRESSURE=0.45 the line read "armed, did not fire (2/2=1.000 vs 0.45)": a value
      meeting its own printed threshold beside the words reserved for a condition that WAS tested and
      was not met. A second, narrower shape does the same thing with no floor involved -- the ratio is
      rounded to three places for printing, so at FAB_N0=4 FAB_SLOTS=6 FAB_PRESSURE=0.6667 the digits
      shown (0.667) sit on the other side of the setpoint from the ratio compared (0.6666...).

EVERY CHECK WAS SEEN TO FAIL. A test never seen to fail is not known to test anything, and the survey of
the old tree counted 60 guards whose condition could not be satisfied. Each check here was run against a
scratch mirror of src/ OUTSIDE this repository with its own repair reverted -- the guard moved back below
the arithmetic, `write=learn` back to `write=solo` with the class guard deleted, the alarm back on
`bal.grad_fn`, the LeverError block deleted, `h[:0].sum()` back to `h.new_zeros(())`, the learn_window
refusal deleted, one reason's equation re-hardcoded -- and each one FAILED there, on its own check and
on no other, and passes here. EIGHTEEN mirrors over the nine repairs -- 12 over the first eight, because
two of those eight are not one line in one file, 3 for F9, because the reason it stands over has two
arms and each was reverted alone as well as together, and 3 more for F4 on 2026-09-14, because its
subject became a SPLIT between two layers and one revert proves a third of it; 12 + 3 + 3 = 18. The
breakdown is written beside the total because a breakdown reading 12+2+1 was published as 17 in this
file one round ago:
  * THE IDENTITY CACHE HAS TWO DOORS, shut in different rounds, and they were reverted separately:
    `write=solo` reopens the eval door and trips F2's inserted-eval half, `write=True` reopens the
    leave-one-out door too and trips its inserted-counterfactual half. One revert would have left the
    other half unproved.
  * THE NEGATIVE CADENCE IS REFUSED BY TWO PACKAGES, so F8 was proved over a four-mirror matrix rather
    than one revert: derive's refusal off (PASS, and the report correctly names FAB as the layer that
    caught it), both off (FAIL), derive off with the switch off (PASS, Windows(-5) returned, which is
    D4's OFF honoured), and derive off with the switch off and FAB's guard ignoring it (FAIL). Two
    pass and two fail, each for its own reason, which is what makes the check a statement about the
    path rather than about one line.
  * F4'S SUBJECT IS A SPLIT BETWEEN TWO LAYERS and one revert proves one half of it, so it was driven
    over FOUR mirrors, each red for its own reason and each red on F4 and on no other check here:
    the LeverError block deleted (ten levers BUILT at -0.5 at BOTH doors, and the report says so
    lever by lever); FAB_DISCOVER's entry put BACK into that block with its domain kept, which is the
    untrippable-guard state itself (red on the direct-Config door, where that clause still fires, and
    tests/test_ownership.py::check_o15_domain_agrees_with_read_site goes red beside it on the same
    lever -- the behavioural and the static halves of one fact agreeing); the DOMAIN DROPPED with the
    entry left out (nothing refuses FAB_DISCOVER=-0.5 at either door and 2.0000001 resolves); and the
    tree as it stood before 2026-09-14, entry present and no domain -- a CONSISTENT tree whose ruling
    this file's census tuple contradicts, red on the census row and on the empty declaration column,
    which is the report saying the tuple must move rather than saying the tree is broken.
  * F9'S REASON HAS TWO ARMS -- the floor and the rounded render -- and three mirrors, because one
    revert would have left the other arm unproved: the reason deleted outright (F9 FAILS on all four
    contradicting rows, and on no other check), the floor arm alone kept (FAILS on the two ROUNDING
    rows only), and the rounding arm alone kept (FAILS on the two FLOOR rows only). Its census was
    proved from the other side, in this file rather than in src/: dropping the contradicting rows from
    CULL_ROWS FAILS on "no row in this sweep produced a line whose pair disagrees with its own
    verdict", and dropping the agreeing rows FAILS on the converse.
THE MOST USEFUL RESULT OF DOING THIS WAS A TEST OF MINE THAT DID NOT FAIL. F7's first version compared
the printed number to the Config numerically; F4 refuses every negative, so 0.0 is the only value those
nine branches can now be entered at, and the mirror with `FAB_EC_W=0` re-hardcoded passed it -- exit 0,
everything green, over the exact defect the check was written for. It is the 61st instance of the class
this suite carries 60 records of, and only the revert found it. The reverts, the widths and the numbers
they produced are recorded in .rework/audits/f_fabtests.json.
AND THE SECOND VERSION FAILED THE SAME WAY, WHICH IS WHY THERE IS A THIRD. The answer to that untrippable
comparison was a TEXT test -- the printed token had to appear in the arithmetic the same Gate printed --
and .rework/audits/g_fab-tests.json refuted it. Reproduced here before it was touched, by planting the
historical defect on each of the nine gates one at a time: a hardcoded bare `0` was UNDETECTED on five of
the nine (fab.balance, fab.explore, fab.discover, fab.breadth_cap, fab.identity_round_trip -- unrelated
standalone zeros such as "0 row(s) swapped" and the literal threshold "> 0" satisfied the search), a
hardcoded `0.0` was undetected on ALL NINE, and a CORRECT reason reformatted to `{ec_w:g}` was FAILED.
The third version does not search text at all: it widens the DOMAIN, because `fabric/api.py::build`
refuses at `v < 0.0` and -0.0 is not less than 0.0, so a twelfth arm reads all nine levers at NEGATIVE
ZERO and the comparison keeps the sign. 27 constants planted (nine gates x `0`, `0.0`, `-0.0`), 27
caught; both reformats pass; and dropping either zero arm makes F7 FAIL rather than pass. The grids are
in .rework/audits/h_fabtests.json.
THE OTHER FOUR REPAIRS OF THAT SAME ROUND WERE EACH RE-PROVED BY THEIR OWN REVERT, on mirrors of src/
outside this repository, because a widened check that has not been seen to fail is the same class again:
  * F1's new n=2 analytic cell -- `_var_cov`'s n>=2 variance term multiplied by 0.0 (Z_dead) and the
    n>=2 estimator switched from unbiased to biased (Z_biased): both exit 0 on the file as it was and
    exit 1 now, each naming which of the two it caught.
  * F2's middle-branch row -- the guard `write = bool(write) and torch.is_grad_enabled()` deleted, and
    separately ONLY the middle write site left unguarded (`if write: pop.ident_graph = None` forced to
    fire): the second is exit 0 on the file as it was and exit 1 now. Collapsing the three rows back
    onto two cache states also FAILS, on the branch census rather than on a behaviour.
  * F4's directed-adjacency naming test -- the lever names stripped out of `build`'s generated refusal
    list: 8 of the 11 rows reported before, 11 of 11 now.
  * F8's second door -- `REFUSE_NEGATIVE_PERIOD` flipped to False, and FAB's guard replaced by
    `if False:`: both exit 0 on the file as it was and exit 1 now. And the other direction: rewording
    the historical anecdote inside spine/derive.py's refusal, a correct edit in a file FAB does not own,
    used to make F8 FAIL and no longer does.
  * THE RUNNER ITSELF -- a check forced vacuous printed "PASS ... (VACUOUS: 0 examined)" and exited 0;
    it now FAILS, which is what the sentence in _report's own docstring always claimed.

HOW THIS FILE KEEPS ITSELF CHEAP AND STABLE, because a slow test is a test nobody runs:
  * ONE torch import, and the widths are the smallest that still exercise the mechanism -- d_model=16,
    sig_d=12, batch 2, length 4, vocab 11, FAB_N0=4 in a pool of 8, rank and dk at their defaults. The
    audits measured at d_model=32/sig_d=64/N0=8/SLOTS=16; every effect reproduces here.
  * EVERY configuration comes from a real spine.assemble.build() over a dict, never a hand-rolled
    object, so what these checks exercise is what a run would get -- including the coupling table and
    the frozen Config. spine/lever.py::_reopen_assembly and spine/rng.py::reset_issued are called before
    each one because the assembly LATCHES after one build.
  * RUN_SEED and RUN_DEVICE are pinned, torch's global seed is set before every population, and every
    tensor is drawn from an explicitly seeded torch.Generator.
  * ASSERTIONS ARE ON PROPERTIES, not on float digits: a gradient is nonzero, a value is finite, two
    runs compare EQUAL to each other, a refusal is raised naming its lever. The three places a number is
    asserted are analytic and are justified where they are used -- 1 - sqrt(1e-4) is the variance hinge
    at its maximum for a single point, exactly 0.0 is the sum of no elements, and 0.0 is the gradient of
    a constant.

WHAT THIS FILE CANNOT CATCH. It is not a training test: it runs single passes and never an optimizer, so
it says nothing about whether the population LEARNS anything, which is INV-R2-1's question and is
measured end to end in the audits rather than here. It exercises one hop_mode (`soc`; `transition` is
refused at build by Q-FAB-1), one device (cpu) and one dtype. FAB.observe, FAB.grow_check,
FAB.own_lr_scale, FAB.counters, FAB.contribution and the checkpoint pair are not covered here, and this
file's count will not notice on its own; FAB.manage is driven once per F9 row, for the cull gate's line
only. (This paragraph said they all "raise NotImplementedError" -- all but FAB.contribution have had
bodies for weeks. tests/test_fabric_internals.py drives manage's selection pass, grow_check's shift
stamp and the row events OPT.remap_rows consumes, since 2026-09-24.) It is also not a substitute for the static checks: whether a counter is
DECLARED, whether a citation opens, and whether a lever is owned are tests/test_ownership.py's,
tests/test_contract.py's and tests/test_census.py's.
"""
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import torch                                                            # noqa: E402
from torch import nn                                                    # noqa: E402
from torch.nn import functional as TF                                   # noqa: E402

from spine import assemble                                              # noqa: E402
from spine import lever                                                 # noqa: E402
from spine import rng                                                   # noqa: E402
from spine import registry                                              # noqa: E402
from spine.lever import LeverError                                      # noqa: E402
from spine import units as U                                            # noqa: E402

from fabric import api as FAB                                           # noqa: E402

MAX_SHOWN = 12

# The widths. Small enough that the whole file is seconds, large enough that every mechanism is real:
# B*L rows to route, more than one live expert so topk, the load-balance term and the leave-one-out
# candidate all mean something, and a pool with room to spawn into.
D_MODEL, SIG_D, BATCH, LEN, VOCAB = 16, 12, 2, 4, 11
BASE = {"RUN_SEED": "7", "RUN_DEVICE": "cpu", "FAB_N0": "4", "FAB_SLOTS": "8"}


def _report(tag, title, ok, detail, findings, vacuous=False):
    """One check's verdict, in tests/test_couplings.py's shape. The size of the examined population is
    always printed: a green tick over an empty set is this project's most repeated defect, and the only
    honest way to report one is to say how big the set was."""
    # A GREEN TICK OVER AN EMPTY SET IS NOT A PASS, IT IS THE DEFECT -- so `vacuous` FAILS the check
    # rather than annotating it. It used to only append the string below: a check that examined
    # nothing printed "PASS ... (VACUOUS: 0 examined)" and still returned 0, which is a sentence
    # contradicting itself in the one file whose whole purpose is assurance. None of the eight can go
    # vacuous today, and that is exactly when the runner has to be right about it.
    ok = bool(ok) and not vacuous
    mark = "PASS" if ok else "FAIL"
    note = "  (VACUOUS: 0 examined -- a check that examined nothing FAILS here)" if vacuous else ""
    print(f"{mark}  {tag}  {title}{note}")
    print(f"      {detail}")
    for f in findings[:MAX_SHOWN]:
        print(f"      - {f}")
    if len(findings) > MAX_SHOWN:
        print(f"      ... and {len(findings) - MAX_SHOWN} more")
    return 0 if ok else 1


# ==================================================================================================
# The harness. One real assembly per configuration; one seeded population and input draw per pass.
# ==================================================================================================

def cfg(**env):
    """A real, frozen FAB Config from a real assemble.build over a dict environment.

    THE ASSEMBLY LATCHES AFTER ONE BUILD, so both reopeners are called here rather than remembered by
    each caller: spine/lever.py::_reopen_assembly and spine/rng.py::reset_issued run on every entry.
    The environment is a DICT and not os.environ -- spine/lever.py is the only file permitted to name
    os.environ, and passing the mapping keeps every configuration in this file independent of the
    shell that ran it.
    """
    lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    configs, _wires, warnings = assemble.build(e)
    if warnings:                        # a typo in a lever name here would silently test the default
        raise AssertionError(f"assemble.build warned on {e}: {warnings}")
    return configs


def population(c, *, d_model=D_MODEL, sig_d=SIG_D, seed=1234):
    """One built population on cpu, from the package RNG stream the entry point is declared to receive."""
    return FAB.build(c["FAB"], d_model=d_model, signature_dim=sig_d,
                     device=torch.device("cpu"), generator=rng.rng_for("fabric", seed))


def draw(seed=5, d_model=D_MODEL, sig_d=SIG_D, h_fill=None):
    """One seeded input draw plus a decode head. Returns (head, X) with X = (h, signature, novelty,
    targets). `h` requires grad so a check can measure what the aux term hands back to the LM."""
    torch.manual_seed(seed)                       # nn.Linear draws from the GLOBAL generator
    head = nn.Linear(d_model, VOCAB)
    g = torch.Generator().manual_seed(seed)
    if h_fill is None:
        h = torch.randn(BATCH, LEN, d_model, generator=g, requires_grad=True)
    else:
        h = torch.full((BATCH, LEN, d_model), float(h_fill)).requires_grad_(True)
    s = torch.randn(BATCH, sig_d, generator=g)
    s = s / s.norm(dim=-1, keepdim=True)          # SIG.encode hands back a normalised signature
    nov = torch.rand(BATCH, generator=g)
    targets = torch.randint(0, VOCAB, (BATCH, LEN), generator=g)
    return head, (h, s, nov, targets)


def forward(c, pop, head, X, step, *, training=True, hold_out=None):
    h, s, nov, targets = X
    return FAB.forward(c["FAB"], pop, h=h, signature=s, novelty=nov, head=head, targets=targets,
                       step_windows=step, domain_id=0, live_domains=3, training=training,
                       hold_out=hold_out)


def composed_loss(out, head, X):
    """THE OBJECTIVE THE COMPOSITION ROOT BACKWARDS, named because a gradient is a gradient OF
    something: spine/compose.py's OPT.scaled_backward row is "LM.lm_loss's mean + LM.anchor_term's
    already-weighted term + FabricOut.aux_loss + WORLD's loss". Here that is a cross-entropy over the
    decoded representation PLUS aux_loss. Measuring aux_loss alone is a different measurement -- it is
    the probe this tree never runs -- and .rework/audits/z_fabric.json records the two disagreeing on
    grad|B| by four orders of magnitude, which is why this function exists instead of `out.aux_loss`.
    """
    lg = out.logits if out.logits is not None else head(out.hidden)
    ce = TF.cross_entropy(lg.reshape(-1, lg.size(-1)), X[3].reshape(-1))
    return ce + out.aux_loss


def every_parameter(pop, head, X):
    """Everything a FAB-side term could possibly reach: both adapter banks, the learned halt prior,
    every shared module's parameters, the decode head's, and the incoming representation."""
    ps = [pop.A, pop.B, pop.halt_b]
    ps += [p for m in pop.modules.values() for p in m.parameters()]
    ps += list(head.parameters())
    ps += [X[0]]
    return [p for p in ps if p.requires_grad]


def absmax_sum(loss, params):
    """sum of |g|max over every parameter -- one number that is nonzero iff SOMETHING moved, and that
    compares bit-for-bit between two passes that differ only in a lever."""
    gs = torch.autograd.grad(loss, params, allow_unused=True, retain_graph=True)
    return sum(0.0 if g is None else float(g.abs().max()) for g in gs)


# Every standalone number in a string, whatever its spelling. The lookarounds stop it reading a number
# out of `n_live=4` as `live=4` or splitting `1e-3`; every comparison below is NUMERIC and never
# textual, so `-0`, `-0.0` and `-0.0e0` are one value and a reformatted field is not a finding.
_NUMBER = re.compile(r"(?<![\w.])(-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)(?![\w.])")


# A sentence boundary, and a token shaped like any lever name. Both are used to bound the span
# between a lever name and the number it is claimed to have read -- see _names_lever_and_value.
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
_ANY_LEVER_NAME = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b")


def _names_lever_and_value(message, lever_name, value):
    """Does this message name the lever AS THE THING IT READ THIS VALUE FROM -- or somewhere else?

    THE DISTINCTION IS NOT PEDANTRY, IT IS THE ONLY THING THAT MAKES THE ASSERTION TRIPPABLE. Two
    refusals in this tree carry long static paragraphs that mention lever names: FAB's own build
    refusal always prints "FAB_BALANCE, FAB_PONDER and FAB_EMB_VAR multiply their terms UNGUARDED"
    and "(measured at FAB_BALANCE=-1.0: ...)" whichever of the eleven was actually refused, and
    spine/derive.py::flush_period_windows always prints "FAB_MANAGE_EVERY=-500 built
    FAB.d_manage_period=Flushes(1)" whichever lever's wire it was computing. A plain
    `lever_name in message` is therefore satisfied by prose for those levers no matter what the
    refusal read, and .rework/audits/g_fab-tests.json proved both cases by stripping the readings
    out and watching the assertions stay green.

    IT IS NOT A CHARACTER GAP ANY MORE, AND THAT WAS THE SAME DEFECT ONE LEVEL DOWN. The first
    trippable version required the name to end within FOUR characters of the value, which is a
    SPELLING rule wearing a consistency rule's name -- exactly what this file indicted in F7's second
    version and then committed here. .rework/audits/i_fab-tests.json measured the cost: of six
    rewordings of build's generated list, every one of them correct, five passed and
    "FAB_BALANCE was read as -0.5" turned F4 RED on all eleven rows, because 13 > 4. The boundary was
    arbitrary in a way the docstring did not admit -- "the operator set FAB_BALANCE to -0.5" passed
    at exactly 4.

    THE RULE IS NOW A STATEMENT ABOUT THE SENTENCE INSTEAD, and it is three clauses, each of which
    rejects one of the shapes actually in this tree:
      1. the value must be the FIRST standalone number after the name. "FAB_MANAGE_EVERY=-500 built
         ..." names the lever beside -500, so at a read of -5 it is prose, whatever else the
         paragraph goes on to say.
      2. no SENTENCE BOUNDARY between them. A name in one sentence and a number in the next are two
         statements, not a reading.
      3. no OTHER lever name between them. That is what rejects the value-quoted-elsewhere shape --
         "REVERSED AND APPLIED: -0.5 -- FAB_BALANCE, FAB_PONDER and FAB_EMB_VAR multiply their terms
         UNGUARDED" -- where the name is read out of a fixed list that names all three whichever one
         was refused; FAB_PONDER stands between FAB_BALANCE and any later number.
    Directedness is kept: the number must come AFTER the name. Every one of the six rewordings now
    passes, and both prose shapes are still rejected -- measured, not argued, and the six rows are in
    the audit file .rework/audits/j_fabric.json.
    """
    numbers = [(m.start(), m.group(1)) for m in _NUMBER.finditer(message)]
    for m in re.finditer(re.escape(lever_name), message):
        after = m.end()
        nxt = next(((pos, tok) for pos, tok in numbers if pos >= after), None)
        if nxt is None or nxt[1] != str(value):
            continue                          # clause 1: the name is beside some OTHER number
        span = message[after:nxt[0]]
        if _SENTENCE_END.search(span):
            continue                          # clause 2
        if _ANY_LEVER_NAME.search(span):
            continue                          # clause 3
        return True
    return False


# ==================================================================================================
# F1 -- the NaN that reached every tensor in the model
# ==================================================================================================

def check_f1_var_cov_at_one_expert():
    """src/fabric/api.py::_var_cov must be FINITE at every population size it can be called at.

    THE DEFECT WAS ORDER, NOT ARITHMETIC. `std = torch.sqrt(z.var(0) + 1e-4)` ran ABOVE `if n < 2:`,
    and torch's var(dim=0) is unbiased, so at one live expert it divided by zero and returned NaN --
    which `emb_var` could not switch off, because NaN * 0 is NaN. n_live=1 is reachable today:
    FAB_N0=1 is accepted with no complaint, and with the pool full the spawn cannot rescue n before
    _ae_loss reads it.

    TWO HALVES, because either alone would be a weaker statement. The DIRECT half calls the function
    over a grid of shapes and demands finite values AND a finite gradient. The END-TO-END half runs
    the real routed pass at FAB_N0=1 with FAB_SLOTS=1 and demands a finite aux_loss and a finite
    gradient into A and B -- and asserts fab.ident_trained, so the round trip that reads this function
    is known to have run rather than assumed to have.
    """
    findings, examined = [], 0

    # -- direct: the shape grid. n=1 is the repaired cell; the rest must stay finite beside it.
    for n in (1, 2, 3, 5, 8):
        for d in (1, 4, 16):
            examined += 1
            g = torch.Generator().manual_seed(100 * n + d)
            z = torch.randn(n, d, generator=g, requires_grad=True)
            var, cov = FAB._var_cov(z)
            grad = torch.autograd.grad(var + cov, [z], allow_unused=True)[0]
            if not torch.isfinite(var.detach()).all() or not torch.isfinite(cov.detach()).all():
                findings.append(f"n={n} d={d}: _var_cov returned var={float(var.detach())} "
                                f"cov={float(cov.detach())}; "
                                f"a non-finite loss term multiplies into aux_loss and from there into "
                                f"every parameter the optimizer touches.")
            elif grad is not None and not torch.isfinite(grad).all():
                findings.append(f"n={n} d={d}: the VALUE is finite and dL/dz is not "
                                f"({float(grad.abs().max())}). That is the same poisoning one step "
                                f"later, and it is invisible to a check that reads only the loss.")

    # -- the one analytic number in this check. A single point centres to exactly 0, so its biased
    # variance is 0, std = sqrt(0 + 1e-4) = 0.01, and the hinge relu(1 - std) sits at its maximum
    # 1 - sqrt(1e-4) = 0.99. That is not a measured float: it is what the formula evaluates to for
    # ANY single row at ANY width, so it is asserted to 1e-6 rather than to a recorded digit string.
    for d in (1, 4, 16):
        examined += 1
        z = torch.randn(1, d, generator=torch.Generator().manual_seed(d), requires_grad=True)
        var, cov = FAB._var_cov(z)
        grad = torch.autograd.grad(var + cov, [z], allow_unused=True)[0]
        want = 1.0 - math.sqrt(1e-4)
        if abs(float(var.detach()) - want) > 1e-6:
            findings.append(f"n=1 d={d}: var={float(var.detach())}, expected {want} = 1 - sqrt(1e-4), "
                            f"the hinge at its maximum. One embedding has zero spread and that is the "
                            f"true "
                            f"reading; anything else means the n<2 branch is computing something "
                            f"other than the mean squared deviation from the mean.")
        if float(cov.detach()) != 0.0:
            findings.append(f"n=1 d={d}: cov={float(cov.detach())}; one point has no covariance and the "
                            f"contract for this branch is that the term is HALVED, not estimated.")
        if grad is not None and float(grad.abs().max()) != 0.0:
            findings.append(f"n=1 d={d}: dL/dz absmax={float(grad.abs().max())}, expected exactly 0. "
                            f"Nothing a single point does can change its own spread, so a nonzero "
                            f"gradient here is the term pushing on an input it cannot inform.")

    # -- THE SECOND ANALYTIC NUMBER, AND IT IS HERE BECAUSE THE TWELVE n>=2 SHAPE CELLS ABOVE ASSERT
    # FINITENESS AND NOTHING ELSE. 0.0 is finite; so is the biased estimator; so is any wrong answer
    # that does not overflow. .rework/audits/g_fab-tests.json measured both: multiplying the n>=2
    # variance term by 0.0 -- deleting the anti-collapse pressure this whole function exists for,
    # against a measured nearest-neighbour distance of 0.000 -- left the suite at 8 checks 0 failing,
    # and so did silently switching `z.var(0)` from unbiased to biased, which the n<2 branch's own
    # comment says must stay distinguishable. Reproduced here before this cell was written.
    # THE NUMBER IS ANALYTIC, like the n=1 one, and not a recorded float: at n=2 with z = [[+a],[-a]]
    # the rows are already centred, so the UNBIASED variance is 2a^2 and the biased one is a^2. At
    # a=0.5 that is 0.5 against 0.25, and the hinge relu(1 - sqrt(var + 1e-4)) separates them by 0.207
    # -- 1 - sqrt(0.5001) = 0.2928 against 1 - sqrt(0.2501) = 0.4999 -- while a deleted term reads
    # 0.0. One assertion tells all three apart. a=0.5 is chosen because at a=1.0 the hinge floors at
    # 0.0 under BOTH estimators and the cell would be green over the difference it exists to see.
    examined += 1
    z2 = torch.tensor([[0.5], [-0.5]])
    var2, cov2 = FAB._var_cov(z2)
    want2 = 1.0 - math.sqrt(2 * 0.25 + 1e-4)
    if abs(float(var2.detach()) - want2) > 1e-6:
        biased = 1.0 - math.sqrt(0.25 + 1e-4)
        findings.append(f"n=2 d=1 at z=[[0.5],[-0.5]]: var={float(var2.detach())}, expected {want2} = "
                        f"relu(1 - sqrt(2a^2 + 1e-4)) at a=0.5, the UNBIASED reading. "
                        + (f"{biased} is what the biased estimator returns and the two differ by "
                           f"{abs(want2 - biased):.4f}; " if abs(float(var2.detach()) - biased) <= 1e-6
                           else "")
                        + f"0.0 is what a deleted variance term returns. The twelve finiteness cells "
                          f"above cannot tell any of these apart, which is why this one is here.")
    if float(cov2.detach()) != 0.0:
        findings.append(f"n=2 d=1: cov={float(cov2.detach())}; a single feature has no off-diagonal "
                        f"to decorrelate, so the covariance term is exactly 0 at d=1 whatever n is.")

    # -- end to end at the reachable configuration. FAB_SLOTS=1 pins cap at 1 so the spawn cannot
    # rescue n before _ae_loss reads it; this is the arm r_fabric.json measured NaN on at step 0.
    for name, env in (("FAB_N0=1 with the pool full (FAB_SLOTS=1)", {"FAB_N0": 1, "FAB_SLOTS": 1}),
                      ("FAB_N0=1 with the shipped pool and a declining spawn test",
                       {"FAB_N0": 1, "FAB_SPAWN_FLOOR": 1.5})):
        examined += 1
        c = cfg(**env)
        pop = population(c)
        head, X = draw()
        out = forward(c, pop, head, X, 3)
        loss = composed_loss(out, head, X)
        if int(pop.n_live) != 1:
            findings.append(f"{name}: n_live={int(pop.n_live)}, so this arm never reached the n=1 "
                            f"branch and the check over it is VACUOUS.")
            continue
        if not pop.counters.get("fab.ident_trained"):
            findings.append(f"{name}: fab.ident_trained is 0, so _ae_loss -- the only caller of "
                            f"_var_cov -- did not run and this arm proves nothing about it.")
        if not torch.isfinite(out.aux_loss.detach()).all():
            findings.append(f"{name}: aux_loss={float(out.aux_loss.detach())}. This is the reading "
                            f"that took all 28 LM tensors and all 20 FAB tensors to NaN by step 1.")
        gs = torch.autograd.grad(loss, [pop.A, pop.B], allow_unused=True, retain_graph=True)
        for tag, g in zip(("A", "B"), gs):
            if g is not None and not torch.isfinite(g).all():
                findings.append(f"{name}: dL/d{tag} is not finite. The optimizer writes this into the "
                                f"bank on the next step and every later pass reads NaN.")

    detail = (f"{examined} case(s): 15 shape cells of _var_cov (n in 1,2,3,5,8 x d in 1,4,16) with "
              f"value AND gradient -- FINITENESS only, which 0.0 and a biased estimator both satisfy "
              f"-- 3 analytic n=1 cells against 1 - sqrt(1e-4), 1 analytic n=2 cell against "
              f"1 - sqrt(2a^2 + 1e-4) that separates the unbiased estimator from the biased one and "
              f"from a deleted term, and 2 end-to-end routed passes at n_live=1")
    return _report("F1", "_var_cov is finite at one live expert, and so is the run around it",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F2 -- the write door: a pass that cannot carry a graph may not write the identity cache
# ==================================================================================================

def _grads_around_an_inserted_pass(env, inserted):
    """train@5 -> [optionally one no_grad pass at 6] -> train@6, and what A and B got at window 6.

    `inserted` is None, "eval" (training=False) or "holdout" (a leave-one-out candidate). Both of the
    latter are legitimate no_grad instruments and neither may change what the training pass sees.
    """
    c = cfg(**env)
    pop = population(c)
    head, X = draw()
    composed_loss(forward(c, pop, head, X, 5), head, X).backward()
    if inserted is not None:
        with torch.no_grad():
            if inserted == "eval":
                forward(c, pop, head, X, 6, training=False)
            else:
                forward(c, pop, head, X, 6, hold_out=0)
    out = forward(c, pop, head, X, 6)
    loss = composed_loss(out, head, X)
    gA, gB = torch.autograd.grad(loss, [pop.A, pop.B], allow_unused=True, retain_graph=True)
    return ((0.0 if gA is None else float(gA.abs().max())),
            (0.0 if gB is None else float(gB.abs().max())),
            int(pop.counters.get("fab.ident_refreshed", 0)))


def _branch_map(branches):
    """The branch -> rows map as one line, for a finding that has to name what was NOT entered."""
    return "; ".join(f"{b} <- {', '.join(rows)}" for b, rows in sorted(branches.items()))


def check_f2_no_grad_pass_cannot_write_the_cache():
    """A no_grad pass may READ the identity cache and may not WRITE it, whatever the caller passed.

    THE MEASURED COST: one inserted no_grad EVAL pass took the next training pass's grad|A|max to
    EXACTLY 0.0 on every arm where the ae round trip is off -- all of A's gradient, deleted by a pass
    that was only looking -- and to 11% of its value on the shipped arm, with fab.ident_refreshed
    reading the same number either way so the ledger could not see it. src/fabric/api.py::_identities
    now disarms `write` against torch.is_grad_enabled() on the first line of its body, which covers
    all three write sites including the middle branch's `pop.ident_graph = None` clear.

    THE CLASS CLAIM IS TESTED DIRECTLY AND NOT INFERRED. A direct `_identities(..., write=True)` under
    torch.no_grad() must leave all four cache fields IDENTICAL -- that is the property, and the two
    behavioural arms below are two of its consequences.

    NON-VACUITY MATTERS MORE HERE THAN ANYWHERE ELSE IN THIS FILE: "the two runs agree" is satisfied
    perfectly by 0.0 == 0.0, which is the defect. So each arm also asserts the clean grad|A|max is
    NONZERO, which is the reading the poisoning destroyed.

    BOTH INSERTED PASSES ARE HERE BECAUSE THERE ARE TWO DOORS AND THEY WERE SHUT IN DIFFERENT ROUNDS:
    an eval pass (training=False, solo) and a leave-one-out candidate (hold_out set). Reverting the
    call site to `write=solo` reopens only the first; reverting it to `write=True` reopens both. Each
    half fails on its own revert, so neither is riding on the other.
    """
    findings, examined = [], 0

    # -- the class claim, over ALL THREE BRANCHES of the body, each identified by WHAT IT HANDED
    #    BACK and not by the label on the row. The rows used to be labelled "same window as the
    #    cache" / "inside the emb_every cadence" / "a later window" and run at steps 5, 5 and 9 with
    #    emb_every_n=1 -- and the first two are the SAME state: after a training pass at window 5 the
    #    cache is live at 5, so both enter the same-window branch, which RETURNS BEFORE ANY WRITE
    #    SITE. Two branches were covered by three rows, and the one that was missed is the MIDDLE
    #    one, the only branch carrying a write of its own (`pop.ident_graph = None`, the clear the
    #    docstring above calls "the cheaper half"). It is unreachable at emb_every_n=1 after a pass
    #    at the same window -- `step_n - pop.ident_step < emb_every_n` cannot hold for a later step
    #    when the cadence is 1 -- so it gets its own configuration rather than a relabelled row.
    fields = ("ident_graph", "ident", "ident_step", "ident_live")
    branches = {}
    for emb_every, rows in ((1, ((5, "the window the cache was written at"),
                                 (9, "a later window, past the cadence"))),
                            (4, ((6, "a later window INSIDE the emb_every cadence"),))):
        c = cfg(FAB_EMB_EVERY=emb_every)
        pop = population(c)
        head, X = draw()
        composed_loss(forward(c, pop, head, X, 5), head, X).backward()
        if pop.ident_graph is None or pop.ident_graph.grad_fn is None:
            findings.append(f"at FAB_EMB_EVERY={emb_every} the training pass at window 5 left no live "
                            f"ident_graph, so every row below starts from a cache that is already "
                            f"empty and 'the no_grad call did not clear it' proves nothing.")
        for step, label in rows:
            examined += 1
            before = tuple(getattr(pop, f) for f in fields)
            with torch.no_grad():
                keys, refreshed = FAB._identities(pop, int(pop.n_live), step, emb_every, write=True)
            after = tuple(getattr(pop, f) for f in fields)
            # WHICH BRANCH RAN, read off the RETURNED OBJECT rather than re-deriving the predicate
            # here: the same-window branch hands back `pop.ident_graph` itself, the cadence branch
            # hands back the detached `pop.ident`, and the recompute branch hands back a tensor that
            # is neither. A test that restated the condition would agree with a wrong condition.
            branch = ("same-window (the live graph itself is handed back)" if keys is before[0]
                      else "cadence (the detached copy is handed back, and this is the branch that "
                           "clears the live graph)" if keys is before[1]
                      else "recompute (a fresh embedding)")
            branches.setdefault(branch, []).append(f"FAB_EMB_EVERY={emb_every} at step {step}")
            if refreshed:
                findings.append(f"_identities(write=True) under no_grad at step {step} ({label}, "
                                f"FAB_EMB_EVERY={emb_every}) reported refreshed=True. A pass with no "
                                f"graph to give refreshed nothing.")
            moved = [f for f, a, b in zip(fields, before, after) if a is not b]
            if moved:
                findings.append(f"_identities(write=True) under no_grad at step {step} ({label}, "
                                f"FAB_EMB_EVERY={emb_every}, {branch}) CHANGED "
                                f"{', '.join(moved)} -- pop.ident_step is now "
                                f"{pop.ident_step!r} and pop.ident_graph carries a grad_fn: "
                                f"{pop.ident_graph is not None and pop.ident_graph.grad_fn is not None}. "
                                f"The next training pass at that step is handed the graphless tensor "
                                f"this call stamped in, or no cache at all, and the one gradient "
                                f"channel that reaches every live expert drops out of its backward.")
        if pop.ident_graph is None or pop.ident_graph.grad_fn is None:
            findings.append(f"at FAB_EMB_EVERY={emb_every}, after the no_grad calls the surviving "
                            f"ident_graph is gone or has no grad_fn, so the comparisons above "
                            f"compared two broken states and prove nothing.")
    # THE COVERAGE OF THE THREE BRANCHES IS ITSELF ASSERTED, because the defect this half found last
    # round was not a wrong answer, it was three rows standing over two states while the detail line
    # said three. If a future edit collapses them again, this FAILS rather than quietly narrowing.
    if len(branches) != 3:
        findings.append(f"the direct no_grad writes entered {len(branches)} distinct branch(es) of "
                        f"_identities, not 3: {_branch_map(branches)}. `write` is disarmed once for the whole "
                        f"body, so a branch nothing enters is a write site nothing holds -- and the "
                        f"middle branch is the one carrying `pop.ident_graph = None`.")

    # -- the behavioural arms. FAB_AE_W=0 and FAB_SPAWN=0 each remove the ae round trip, which is A's
    # OTHER route to the loss; those are the arms where the poisoning read EXACTLY 0.0.
    arms = (("shipped", {}),
            ("FAB_AE_W=0 (the ae round trip off)", {"FAB_AE_W": 0}),
            ("FAB_SPAWN=0 (the ae round trip off by the other lever)", {"FAB_SPAWN": 0}),
            ("both off", {"FAB_AE_W": 0, "FAB_SPAWN": 0}))
    for label, env in arms:
        clean = _grads_around_an_inserted_pass(env, None)
        if clean[0] == 0.0:
            findings.append(f"{label}: grad|A|max is 0.0 with NO pass inserted, so this arm cannot "
                            f"detect the deletion it exists to detect -- the comparison below would "
                            f"be 0.0 == 0.0.")
        for inserted in ("eval", "holdout"):
            examined += 1
            got = _grads_around_an_inserted_pass(env, inserted)
            if got[0] != clean[0] or got[1] != clean[1]:
                findings.append(
                    f"{label}: one inserted no_grad {inserted} pass at window 6 moved the TRAINING "
                    f"pass's gradients -- grad|A|max {clean[0]} -> {got[0]}, grad|B|max {clean[1]} -> "
                    f"{got[1]}. A pass that only looks must be invisible to the pass that learns.")
            if got[2] != clean[2]:
                findings.append(f"{label}: fab.ident_refreshed differs ({clean[2]} vs {got[2]}) with a "
                                f"{inserted} pass inserted, so the arms are not comparable.")

    detail = (f"{examined} case(s): 3 direct no_grad writes covering {len(branches)} distinct "
              f"branch(es) of _identities, named by what each handed back rather than by its label "
              f"-- {_branch_map(branches)} -- and 8 gradient comparisons (4 arms x {{eval, leave-one-out}} "
              f"inserted at window 6), each against the same two training passes with nothing "
              f"inserted")
    return _report("F2", "a no_grad pass cannot write the identity cache or move the next backward",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F3 -- the C2 alarm reads the balance term, not its accumulator's seed
# ==================================================================================================

def _balance_probe(env):
    """One routed training pass: the alarm's reading, and an independent gradient measurement of
    whether the balance term reaches ANY parameter."""
    c = cfg(**env)
    pop = population(c)
    head, X = draw()
    out = forward(c, pop, head, X, 3)
    params = every_parameter(pop, head, X)
    return (pop.counters.get("fab.balance_nonzero"),
            float(out.aux_loss.detach()),
            absmax_sum(out.aux_loss, params))


def check_f3_c2_alarm_agrees_with_the_gradient():
    """fab.balance_nonzero must read 0 exactly when the load-balance term reaches nothing.

    THE C2 FAILURE MODE, in the tree's own words: FAB_BALANCE, BAL_FLOOR and BAL_WARM were read,
    printed and reasoned about for the whole life of the old tree while multiplying a freshly
    allocated zero. fab.balance_nonzero is the alarm that exists to say so. It went blind when
    `zero` became `h[:0].sum()` for F5's sake: `bal_acc` is seeded from `zero`, so `bal.grad_fn is
    not None` -- the alarm's own test -- became TRUE BY CONSTRUCTION on every training pass.

    THE DEAD ARM IS PROVED DEAD RATHER THAN ASSUMED. At FAB_ROUTE_LEARN=0 the entry logits are a
    region cosine over the DETACHED signature against `cent`, which is not a Parameter, and at
    FAB_HALT=0 the halt column is pinned -- so the routing distribution `w` reaches no parameter and
    the balance term built from it cannot move one. This check does not take that on trust: it
    measures the gradient of aux_loss over EVERY parameter at FAB_BALANCE 0, 0.01 and 5.0 and
    requires the three to be identical while aux itself moves. An alarm reading 1 there is reporting
    a live term over a dead one.

    AND THE OTHER DIRECTION, so the check is not "the alarm never fires": three arms where the term
    IS live must read 1, and each is confirmed live by the same gradient measurement MOVING between
    FAB_BALANCE=0 and FAB_BALANCE=0.01.
    """
    findings, examined = [], 0

    dead = {"FAB_ROUTE_LEARN": 0, "FAB_HALT": 0}
    base = _balance_probe(dict(dead, FAB_BALANCE=0.0))
    for w in (0.01, 5.0):
        examined += 1
        alarm, aux, grad = _balance_probe(dict(dead, FAB_BALANCE=w))
        if grad != base[2]:
            findings.append(f"dead arm at FAB_BALANCE={w}: the gradient over every parameter MOVED "
                            f"({base[2]} -> {grad}), so the term is not dead here and this arm is the "
                            f"wrong control. The check below cannot be read.")
            continue
        if aux == base[1]:
            findings.append(f"dead arm at FAB_BALANCE={w}: aux did not move either ({aux}), so the "
                            f"term is not being ADDED and there is nothing for the alarm to be wrong "
                            f"about.")
        if alarm != 0:
            findings.append(
                f"dead arm at FAB_BALANCE={w}: fab.balance_nonzero={alarm}. aux moved "
                f"{base[1]} -> {aux} and the gradient over A, B, halt_b, every shared module, the "
                f"head and h did NOT ({grad}), so the term is multiplying a zero -- which is the one "
                f"reading this counter exists to produce, and it produced the opposite.")

    live = (("shipped", {}),
            ("FAB_ROUTE_LEARN=0 with halt on (the term is live through halt_b)", {"FAB_ROUTE_LEARN": 0}),
            ("FAB_HALT=0 with route_learn on", {"FAB_HALT": 0}))
    for label, env in live:
        examined += 1
        alarm, _aux, grad = _balance_probe(dict(env, FAB_BALANCE=0.01))
        _a0, _x0, grad0 = _balance_probe(dict(env, FAB_BALANCE=0.0))
        if grad == grad0:
            findings.append(f"live arm '{label}': the gradient is identical at FAB_BALANCE 0 and 0.01 "
                            f"({grad}), so the term is NOT live here and this row is the wrong "
                            f"control -- the alarm reading 1 would be the defect, not the check.")
        elif alarm != 1:
            findings.append(f"live arm '{label}': fab.balance_nonzero={alarm} while the gradient over "
                            f"every parameter moves with FAB_BALANCE ({grad0} -> {grad}). The alarm is "
                            f"calling a live load-balance term dead, which suppresses the one report "
                            f"C2 is the record of.")

    detail = (f"{examined} arm(s): 2 dead-arm readings (FAB_ROUTE_LEARN=0 + FAB_HALT=0 at FAB_BALANCE "
              f"0.01 and 5.0), each cross-checked against the gradient of aux_loss over every "
              f"parameter at FAB_BALANCE=0, and 3 live arms each confirmed live by that gradient "
              f"moving")
    return _report("F3", "fab.balance_nonzero (THE C2 ALARM) agrees with the gradient in both directions",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F4 -- eleven negative magnitude levers refused: TEN by FAB.build, ONE by its own declaration
# ==================================================================================================

REVERSED = ("FAB_BALANCE", "FAB_PONDER", "FAB_EMB_VAR")
GUARDED_OFF = ("FAB_EC_W", "FAB_EXPLORE", "FAB_DIV_W", "FAB_HOP_SUP",
               "FAB_IND_W", "FAB_AE_W", "FAB_DOM_FRAC")
# THE ELEVENTH OF THE SAME RULING, AND ITS ROW MOVED RATHER THAN DISAPPEARING. src/fabric/levers.py
# declares FAB_DISCOVER with `domain=(0.0, 2.0)` -- a COSINE DISTANCE, whose ceiling is 2.0 and not
# the 1.0 its U.FRACTION label invites -- and spine/lever.py::Lever.coerce checks a domain at the
# FIRST read, before a Config exists. The entry src/fabric/api.py::build carried for this lever was
# RETIRED on 2026-09-14 instead of being left there unable to fire: one fact standing in two places
# is the untrippable-guard family this project's founding census counts 60 of, and
# tests/test_ownership.py::check_o15_domain_agrees_with_read_site fails on exactly that shape.
# THIS TUPLE IS A CENSUS AND NOT THE SOURCE OF TRUTH. The declarations are, and `_declared_refusals`
# below reads them off the live Config, so a domain added to or dropped from any of the eleven is
# REPORTED here as a disagreement rather than quietly changing what this check means.
RETIRED_TO_DECLARATION = ("FAB_DISCOVER",)
THE_ELEVEN = REVERSED + GUARDED_OFF + RETIRED_TO_DECLARATION


def _fab_fields(base):
    """{env name: field} over FAB's own levers, GENERATED by the spine rather than typed here --
    spine/lever.py::Config.lever hands back the same `env_name` the resolver used."""
    fab = base["FAB"]
    return {fab.lever(k).env_name: k for k in fab.keys() if not k.startswith("d_")}


def _declared_refusals(base, value, names):
    """Which of `names` have a declared domain that refuses `value` at the first read.

    Read off spine/lever.py::LeverView.domain, which is the pair as declared. The comparison is the
    one spine/lever.py::Lever.coerce makes -- BOTH ENDS INCLUSIVE, an end of None meaning no bound on
    that side -- so this cannot drift from the rule it predicts without coerce drifting with it.
    """
    fab = base["FAB"]
    out = set()
    for env_name, field in _fab_fields(base).items():
        if env_name not in names:
            continue
        dom = fab.lever(field).domain
        if dom is None:
            continue
        if (dom[0] is not None and value < dom[0]) or (dom[1] is not None and value > dom[1]):
            out.add(env_name)
    return out


def config_the_declaration_did_not_produce(base, field, value):
    """A FAB Config with one field written AFTER coerce -- THE OTHER DOOR INTO FAB.build.

    A declared domain is checked in exactly one place, spine/lever.py::Lever.coerce, and coerce runs
    on a STRING arriving from the environment. A Config built directly never passes through it:
    spine/lever.py's own header says a Config is an ordinary object that does not know who is holding
    it, and tests/test_couplings.py builds one this way today. So this is the path on which
    src/fabric/api.py::build's hand-written refusal is the only thing standing, and it is the path
    that tells a retired clause apart from a clause that is merely unreachable from a shell.

    Every number here is the one a real assembly resolved, every wire is the one the coupling table
    computed, and exactly one field is replaced -- so a refusal raised on this Config is a refusal
    about that field and not about a half-built object.
    """
    owner = registry.all_sets()["FAB"]
    real = base["FAB"]
    vals = {k: getattr(real, k) for k in real.keys() if not k.startswith("d_")}
    vals[field] = value
    c = lever.Config(owner, vals, {})
    for k in real.keys():
        if k.startswith("d_"):
            c._wire(k, getattr(real, k))
    return c._freeze()


def check_f4_negative_magnitude_levers_refused():
    """Eleven negative magnitude levers are refused, TEN by src/fabric/api.py::build and ONE by its
    declaration, each naming the lever AND the value it read -- and this check says which is which.

    THE TWO GROUPS AND WHY BOTH ARE REFUSED. FAB_BALANCE, FAB_PONDER and FAB_EMB_VAR multiply their
    loss terms with no `> 0.0` in front of them, so a negative does not switch the mechanism off, it
    runs it BACKWARDS -- the population is paid to collapse onto one expert, the charge on routed
    depth becomes a subsidy, and the anti-collapse term becomes a pro-collapse one. The other eight
    are guarded and a negative is bit-identical to 0.0, so the refusal removes NO configuration an
    operator can ask for and makes a false gate reason impossible rather than correct once. The
    ground is src/capacity/api.py::new_valve's refusal of a negative CAP_LIFT.

    WHY THE SUBJECT MOVED, AND WHAT MOVING IT WOULD HAVE BEEN IF IT HAD BEEN DONE DISHONESTLY. One
    of the eleven, FAB_DISCOVER, now carries `domain=(0.0, 2.0)` on its declaration, so its negative
    is refused a layer earlier and src/fabric/api.py::build's entry for it could never run again.
    The repair that would have been WRONG is the small one: leave this check driving -0.5 and quietly
    accept whatever raised, or move the value until it reaches FAB.build again. Both keep the row
    green while it has stopped looking at the interesting case, which is the untrippable-guard family
    arriving in the test file. WHAT IS ASSERTED INSTEAD IS WHICH LAYER OWNS WHICH LEVER, at BOTH
    doors, with the expectation read off the DECLARATIONS rather than typed here:
      * THE ENVIRONMENT DOOR -- a real assemble.build then a real FAB.build. Every one of the eleven
        must be refused at -0.5 by name and beside the value; the layer that answered must be the
        layer the declared domains predict; and NEITHER layer's population may be empty, because a
        check that proves one door and calls it two is the defect it exists to catch.
      * THE DOOR A DECLARATION DOES NOT STAND IN -- FAB.build handed a Config built directly, with no
        coerce behind it. The ten that kept the hand-written clause must still be refused there. The
        one that retired must NOT be, and that half is the assertion that a retired clause was really
        retired rather than left in place where O15 would keep reporting it.
    A lever that gains a domain covering its negative side moves from one column to the other and the
    census tuple above is checked against the declarations, so the move is reported and not silent.

    THE PREMISE OF THE FIRST GROUP IS MEASURED HERE, not quoted. src/fabric/api.py::_ae_loss takes
    emb_var as a plain argument, so the sign reversal is directly observable: at -1.0 the term is
    SUBTRACTED by exactly the amount +1.0 ADDS. That is the whole claim -- a negative is not "off" --
    and it stays testable after the refusal is in place, which the forward-path version does not.

    AND THE REFUSAL MUST NOT OVERREACH: 0.0 and 1.0 build for every one of the eleven, and
    FAB_BALANCE=5.0 -- a large pressure, still the pressure the lever names -- builds too. U.FRACTION
    is a label the census renders, not a bound. FAB_DISCOVER's own pair is driven at BOTH endpoints
    and at the shipped default for the same reason, and one step above its ceiling is driven because
    that refusal is the thing the retired clause never had: the clause covered (-inf, 0.0), the
    declaration covers (-inf, 0.0) U (2.0, inf), and dropping the pair to keep the line would have
    re-admitted FAB_DISCOVER=3.0.

    WHAT THIS CANNOT CATCH, said here rather than left to the report. It is about the SPELLING of a
    negative and about which layer refuses it. It says nothing about the values either layer admits:
    FAB_DISCOVER=1.9 is inside the pair and recruits on material pointing away from every region,
    FAB_BALANCE=5.0 is asserted to BUILD here, and src/fabric/api.py's own sweep records FAB_ALPHA at
    1e26 leaving 15 of 23 gradient tensors non-finite behind an ordinary-looking loss pair. Nothing
    below makes any lever safe, bounded or validated.
    """
    findings, examined = [], 0
    base = cfg()
    fields = _fab_fields(base)
    declared = _declared_refusals(base, -0.5, THE_ELEVEN)

    # -- the census above, against the declarations themselves --------------------------------
    examined += 1
    if declared != set(RETIRED_TO_DECLARATION):
        gained = sorted(declared - set(RETIRED_TO_DECLARATION))
        lost = sorted(set(RETIRED_TO_DECLARATION) - declared)
        findings.append(
            f"RETIRED_TO_DECLARATION is stale. src/fabric/levers.py declares a domain refusing -0.5 "
            f"on {sorted(declared)} and this file names {sorted(RETIRED_TO_DECLARATION)}"
            + (f"; NEWLY DECLARED: {gained} -- each of these is now refused before "
               f"src/fabric/api.py::build sees it, so its entry in that function's table is an "
               f"untrippable guard until it is retired, and the tuple above must say so" if gained
               else "")
            + (f"; NO LONGER DECLARED: {lost} -- if the domain was dropped, the read-site clause has "
               f"to be back in src/fabric/api.py::build or NOTHING refuses these" if lost else ""))

    by_declaration, by_build = [], []
    for name in THE_ELEVEN:
        examined += 1
        layer = msg = None
        try:
            c = cfg(**{name: -0.5})
        except LeverError as e:
            layer, msg = "the declaration", str(e)
        except Exception as e:                                # noqa: BLE001 -- reported, never swallowed
            findings.append(f"{name}=-0.5: assemble.build raised {type(e).__name__} rather than "
                            f"LeverError ({e}). A refusal in this tree is a LeverError naming the "
                            f"lever, whichever layer makes it.")
            continue
        if layer is None:
            try:
                population(c)
                findings.append(f"{name}=-0.5 BUILT, refused by NEITHER layer. "
                                + ("This lever multiplies its term unguarded, so the mechanism now "
                                   "runs with its sign reversed and the objective pays for the "
                                   "opposite of what the lever names." if name in REVERSED else
                                   "This lever is guarded at `> 0.0`, so the run is bit-identical to "
                                   "0.0 while its gate prints the negative beside a reason "
                                   "asserting the value is 0."))
                continue
            except LeverError as e:
                layer, msg = "FAB.build", str(e)
            except Exception as e:                            # noqa: BLE001
                findings.append(f"{name}=-0.5 raised {type(e).__name__} rather than LeverError: {e}")
                continue

        # WHICH LAYER ANSWERED, against what the declarations predict. Getting this wrong in either
        # direction is a real finding and not bookkeeping: a lever answered by the declaration when
        # no domain bounds it means some other rule is firing and this check has stopped testing what
        # it names, and a lever answered by FAB.build when a domain DOES bound it means coerce did
        # not run on the path this check drives.
        if layer == "the declaration" and name not in declared:
            findings.append(f"{name}=-0.5 was refused before FAB.build could refuse it, and "
                            f"src/fabric/levers.py declares no domain over this lever that refuses "
                            f"-0.5. Something other than the declared pair is answering first, so "
                            f"the row this check calls FAB's is not FAB's: {msg[:160]}")
        elif layer == "FAB.build" and name in declared:
            findings.append(f"{name}=-0.5 reached FAB.build although src/fabric/levers.py declares a "
                            f"domain that refuses it at the first read. The declared pair did not "
                            f"fire on the assembly path, which is where spine/lever.py::Lever.coerce "
                            f"is supposed to run.")

        # NAMING IT IS TESTED AS ADJACENCY TO THE VALUE READ, not as `name in msg`. FAB.build's
        # message carries a static paragraph -- "FAB_BALANCE, FAB_PONDER and FAB_EMB_VAR multiply
        # their terms UNGUARDED ... (measured at FAB_BALANCE=-1.0: ...)" -- that is emitted whenever
        # ANY of the three is refused, so `name in msg` could not fail for those three whatever the
        # refusal read: strip every name out of the generated list and the assertion still passed for
        # FAB_BALANCE, FAB_PONDER and FAB_EMB_VAR while failing for the other eight. Three of the
        # eleven rows were untrippable and the check said eleven. The requirement is the same on
        # BOTH layers, which is the point of asserting it here rather than per-layer: a refusal that
        # moves earlier may not name its lever less precisely for having moved.
        if not _names_lever_and_value(msg, name, -0.5):
            findings.append(f"{name}=-0.5 was refused by {layer} and the message does not name it "
                            f"BESIDE the value it read. The name may appear elsewhere in the prose "
                            f"-- FAB.build's refusal names all three unguarded levers in a fixed "
                            f"sentence whichever one it refused -- and prose is not a reading: "
                            f"{msg[:160]}")
        if "-0.5" not in msg:
            findings.append(f"{name}=-0.5 was refused by {layer} without printing the value it read. "
                            f"A refusal names the lever AND the value that made it fire.")
        (by_declaration if layer == "the declaration" else by_build).append(name)

    # -- NEITHER LAYER MAY BE EMPTY. This check is a statement about two doors; a door with no lever
    #    behind it is a row that has stopped looking, which is the whole failure this repair is about.
    examined += 1
    if not by_declaration or not by_build:
        findings.append(f"one of the two layers refused NOTHING at -0.5 -- by the declaration: "
                        f"{sorted(by_declaration)}; by FAB.build: {sorted(by_build)}. Both halves of "
                        f"this check must have a population or it is proving one door and claiming "
                        f"two.")

    # -- THE OTHER DOOR: FAB.build handed a Config no declaration produced --------------------------
    for name in THE_ELEVEN:
        examined += 1
        c = config_the_declaration_did_not_produce(base, fields[name], -0.5)
        rng.reset_issued()
        try:
            FAB.build(c, d_model=D_MODEL, signature_dim=SIG_D, device=torch.device("cpu"),
                      generator=rng.rng_for("fabric", 1234))
            refused = None
        except LeverError as e:
            refused = str(e)
        except Exception as e:                                # noqa: BLE001
            findings.append(f"{name}=-0.5 on a Config no declaration produced raised "
                            f"{type(e).__name__} rather than LeverError or nothing: {e}")
            continue
        if name in declared and refused is not None:
            findings.append(
                f"{name}: its declaration refuses -0.5 at the first read AND src/fabric/api.py::build "
                f"refuses it again here. That is ONE FACT IN TWO PLACES, and the second can never run "
                f"from an environment -- a guard a future reader trusts and a future edit silently "
                f"breaks. tests/test_ownership.py::check_o15_domain_agrees_with_read_site reports the "
                f"same pair statically and states the fork: retire the clause and carry its "
                f"measurement to the declaration, or drop the domain and leave the ruling where it "
                f"was argued. Not both. This check does not say which.")
        elif name not in declared and refused is None:
            findings.append(
                f"{name}=-0.5 BUILT on a Config no declaration produced, and no declared domain "
                f"bounds this lever either, so NOTHING refuses this value on this path. "
                + ("The term is multiplied unguarded, so the objective now pays for the opposite of "
                   "what the lever names." if name in REVERSED else
                   "The gate will print this negative beside a reason asserting the value is 0."))
        elif name not in declared and not _names_lever_and_value(refused, name, -0.5):
            findings.append(f"{name}=-0.5 was refused on the direct-Config path and the message does "
                            f"not name it beside the value it read: {refused[:160]}")

    # -- the pair that took the ruling over does MORE than the clause it retired, and that is the
    #    argument for the direction this repair went. Both ends of a CLOSED interval, the shipped
    #    default, and one step above the ceiling the retired clause never had.
    for v in ("0.0", "2.0", "0.35"):
        examined += 1
        try:
            population(cfg(FAB_DISCOVER=v))
        except Exception as e:                                # noqa: BLE001
            findings.append(f"FAB_DISCOVER={v} was refused ({type(e).__name__}: {e}). The declared "
                            f"domain is (0.0, 2.0) with BOTH ENDS INCLUSIVE and 0.35 is the shipped "
                            f"default; a pair that refuses its own endpoints or its own default "
                            f"removes a configuration the mechanism evaluates.")
    examined += 1
    try:
        cfg(FAB_DISCOVER="2.0000001")
        findings.append("FAB_DISCOVER=2.0000001 resolved. The ceiling is the half of this ruling the "
                        "retired read-site clause never had -- it covered (-inf, 0.0) only -- and it "
                        "is why the domain was kept and the clause retired rather than the other way "
                        "round. A cosine distance runs over [0, 2] and nothing above 2.0 is a reading "
                        "of `1.0 - best`.")
    except LeverError as e:
        if not _names_lever_and_value(str(e), "FAB_DISCOVER", 2.0000001):
            findings.append(f"FAB_DISCOVER=2.0000001 was refused and the message does not name the "
                            f"lever beside the value it read: {str(e)[:160]}")
    except Exception as e:                                    # noqa: BLE001
        findings.append(f"FAB_DISCOVER=2.0000001 raised {type(e).__name__} rather than LeverError: {e}")

    for name in THE_ELEVEN:
        for v in ("0.0", "1.0"):
            examined += 1
            try:
                population(cfg(**{name: v}))
            except Exception as e:                            # noqa: BLE001
                findings.append(f"{name}={v} was refused ({type(e).__name__}: {e}). The refusal is on "
                                f"NEGATIVE values only; it must remove no configuration an operator "
                                f"can ask for.")
    examined += 1
    try:
        population(cfg(FAB_BALANCE="5.0"))
    except Exception as e:                                    # noqa: BLE001
        findings.append(f"FAB_BALANCE=5.0 was refused ({type(e).__name__}: {e}). Nothing ABOVE these "
                        f"levers is refused by FAB.build -- a large pressure is still the pressure "
                        f"the lever names.")

    # -- the premise: a negative on an unguarded weight is applied, not ignored.
    examined += 1
    c = cfg()
    pop = population(c)
    n = int(pop.n_live)
    at0 = float(FAB._ae_loss(pop, n, 0.0).detach())
    neg = float(FAB._ae_loss(pop, n, -1.0).detach())
    pos = float(FAB._ae_loss(pop, n, 1.0).detach())
    if not (neg < at0 < pos):
        findings.append(f"_ae_loss at emb_var -1.0 / 0.0 / 1.0 reads {neg} / {at0} / {pos}; the "
                        f"anti-collapse term must be SUBTRACTED at a negative and ADDED at a "
                        f"positive. If a negative were merely 'off' these three would not be ordered, "
                        f"and the first half of F4's ruling would have no premise.")
    elif abs((at0 - neg) - (pos - at0)) > 1e-6 * max(1.0, abs(pos - at0)):
        findings.append(f"_ae_loss moves by {at0 - neg} downward and {pos - at0} upward around 0.0; "
                        f"the term is `emb_var * (var + cov)` and the two must be the same magnitude. "
                        f"They are not, so something else in this function depends on emb_var's sign.")

    detail = (f"{examined} case(s): {len(THE_ELEVEN)} levers refused alone at -0.5 with the lever and "
              f"the value named -- {len(by_build)} by src/fabric/api.py::build "
              f"({', '.join(sorted(by_build)) or 'NONE'}) and {len(by_declaration)} by a declared "
              f"domain one layer earlier ({', '.join(sorted(by_declaration)) or 'NONE'}), the split "
              f"checked against the declarations and not against a list typed here; the same 11 "
              f"driven again at -0.5 through FAB.build on a Config no declaration produced, where the "
              f"{len(THE_ELEVEN) - len(declared)} that kept the read-site clause must still be "
              f"refused and the {len(declared)} that retired must not; FAB_DISCOVER at both closed "
              f"endpoints, at the shipped 0.35 and at 2.0000001 (refused by the pair, which is the "
              f"half the retired clause never covered); the same 11 built at 0.0 and at 1.0, "
              f"FAB_BALANCE=5.0 built, and _ae_loss measured at emb_var -1.0 / 0.0 / +1.0")
    return _report("F4", "eleven negative magnitude levers are refused -- ten by FAB.build, one by "
                         "its declaration -- and nothing else is",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F5 -- aux_loss carries a graph on both switched-off arms
# ==================================================================================================

def check_f5_aux_loss_has_a_graph_on_the_off_arms():
    """FabricOut.aux_loss is "ONE scalar with a graph -- never a float and never a freshly allocated
    zero" -- on the FAB_ON=0 and FAB_NORM_ONLY=1 arms as much as on the routed one.

    WHY A GRAPHLESS ZERO IS NOT HARMLESS. The composition root SUMS this field into the objective it
    backwards, so a summand with no grad_fn is an error at neither end: backward() walks past it and
    the run reports normally. That is the C2 failure mode with the loss itself as the subject, and it
    is why the record type forbids it BY NAME.

    THE NON-FINITE ARM IS PART OF THE CHECK AND NOT A CURIOSITY. `h.sum() * 0.0` would also carry a
    graph and would be NaN whenever h is non-finite -- making FAB the apparent source of the LM's
    blow-up. `h[:0].sum()` is the sum of NO elements: exactly 0.0 for every h, including an infinite
    one. So this check runs both arms twice, once on an ordinary draw and once on an h of inf.
    """
    findings, examined = [], 0
    arms = (("FAB_ON=0", {"FAB_ON": 0}, "fab.forward_identity"),
            ("FAB_NORM_ONLY=1", {"FAB_NORM_ONLY": 1}, "fab.norm_only_passes"))
    for label, env, counter in arms:
        for fill_label, fill in (("an ordinary draw", None), ("h = inf", float("inf"))):
            examined += 1
            c = cfg(**env)
            pop = population(c)
            head, X = draw(h_fill=fill)
            out = forward(c, pop, head, X, 3)
            a = out.aux_loss
            if not pop.counters.get(counter):
                findings.append(f"{label} / {fill_label}: {counter} is 0, so this arm was not taken "
                                f"and the readings below are of some other path.")
            if not torch.is_tensor(a):
                findings.append(f"{label} / {fill_label}: aux_loss is {type(a).__name__}, not a "
                                f"tensor. A float summand cannot be backwarded at all.")
                continue
            if a.grad_fn is None:
                findings.append(f"{label} / {fill_label}: aux_loss has NO grad_fn. The composition "
                                f"root adds this into the objective and backwards it; a graphless "
                                f"summand is silently dropped and nothing reports it.")
            if float(a.detach()) != 0.0:
                findings.append(f"{label} / {fill_label}: aux_loss={float(a.detach())}, expected "
                                f"exactly 0.0. Every FAB-side term on this arm is ABSENT, not "
                                f"nonzero, and the gates say so.")
            if not torch.isfinite(a.detach()).all():
                findings.append(f"{label} / {fill_label}: aux_loss is not finite. `h.sum() * 0.0` "
                                f"reads NaN here and would make FAB the apparent source of a blow-up "
                                f"that happened upstream.")
            try:
                g = torch.autograd.grad(a, [X[0]], allow_unused=True)[0]
            except Exception as e:                            # noqa: BLE001
                findings.append(f"{label} / {fill_label}: backward through aux_loss raised "
                                f"{type(e).__name__}: {e}")
                continue
            if g is not None and float(g.abs().max()) != 0.0:
                findings.append(f"{label} / {fill_label}: d(aux_loss)/dh absmax={float(g.abs().max())}, "
                                f"expected exactly 0. The zero carries h's graph so it can be summed; "
                                f"it must not push on h.")

    # -- the control: the routed arm has a graph too, so the check above is not measuring a constant
    # that every arm would satisfy.
    examined += 1
    c = cfg()
    pop = population(c)
    head, X = draw()
    out = forward(c, pop, head, X, 3)
    if out.aux_loss.grad_fn is None or float(out.aux_loss.detach()) == 0.0:
        findings.append(f"the ROUTED arm reads aux_loss={float(out.aux_loss.detach())} with grad_fn "
                        f"{out.aux_loss.grad_fn is not None}. If the routed arm is also a graphless "
                        f"zero then the two off arms above prove nothing.")

    detail = (f"{examined} case(s): 2 switched-off arms x {{ordinary draw, h = inf}} on value, grad_fn, "
              f"finiteness and d/dh, plus the routed arm as a nonzero control")
    return _report("F5", "aux_loss is a differentiable exact zero on the FAB_ON=0 and FAB_NORM_ONLY=1 arms",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F6 -- one gradient-carrying training pass per window
# ==================================================================================================

def check_f6_one_learning_pass_per_window():
    """A SECOND gradient-carrying training pass at one step_windows is refused by name.

    WHAT IT REPLACES. At FAB_ROUTE_LEARN=1 the second pass raised torch's "Trying to backward through
    the graph a second time" out of the identity cache's same-window branch -- naming no lever, no
    clock and no caller. At FAB_ROUTE_LEARN=0 it raised NOTHING and applied one window's ponder
    anneal, balance anneal, spawn test, centroid EMA and halt EMA twice. The refusal is on the CLOCK,
    where the caller error is, and not on the cache, where it happened to show -- so it must fire at
    BOTH values of that lever, which is what makes it a guard rather than an accident.

    AND IT MUST REFUSE ONLY THAT. Three legal shapes are run beside it: two training passes at
    CONSECUTIVE windows, and an eval pass and a leave-one-out pass at the SAME window as a training
    pass -- the two the raised message explicitly promises not to refuse.
    """
    findings, examined = [], 0

    for label, env in (("FAB_ROUTE_LEARN=1 (shipped)", {}), ("FAB_ROUTE_LEARN=0", {"FAB_ROUTE_LEARN": 0})):
        examined += 1
        c = cfg(**env)
        pop = population(c)
        head, X = draw()
        forward(c, pop, head, X, 6)
        try:
            forward(c, pop, head, X, 6)
            findings.append(f"{label}: a second gradient-carrying training pass at step_windows=6 was "
                            f"ACCEPTED. This window's ponder anneal, balance anneal, spawn test and "
                            f"halt EMA are now applied twice for one window of data.")
        except ValueError as e:
            msg = str(e)
            # Three things the message must carry, each as a GROUP of acceptable spellings so this
            # check is on what the refusal says and not on one agent's wording of it.
            for what, spellings in (("the index it read", ("step_windows=6",)),
                                    ("the clock that advances it", ("RunClock",)),
                                    ("what it does NOT refuse", ("hold_out", "leave-one-out"))):
                if not any(sp in msg for sp in spellings):
                    findings.append(f"{label}: the refusal names none of {spellings} and so does not "
                                    f"say {what}. A refusal that does not print the value that made "
                                    f"the arm unreachable is the bare torch error with better "
                                    f"grammar: {msg[:200]}")
        except RuntimeError as e:
            findings.append(f"{label}: the second pass raised torch's own {str(e)[:90]!r} instead of a "
                            f"refusal naming the clock. That is the bare error the guard replaces.")

    def _consecutive(c, pop, head, X):
        forward(c, pop, head, X, 7)
        forward(c, pop, head, X, 8)

    def _eval_then_train(c, pop, head, X):
        with torch.no_grad():
            forward(c, pop, head, X, 9, training=False)
        forward(c, pop, head, X, 9)

    def _holdout_then_train(c, pop, head, X):
        with torch.no_grad():
            forward(c, pop, head, X, 9, hold_out=0)
        forward(c, pop, head, X, 9)

    for label, body in (("two training passes at CONSECUTIVE windows", _consecutive),
                        ("an eval pass at the same window as a training pass", _eval_then_train),
                        ("a leave-one-out pass at the same window as a training pass",
                         _holdout_then_train)):
        examined += 1
        c = cfg()
        pop = population(c)
        head, X = draw()
        try:
            body(c, pop, head, X)
        except Exception as e:                                # noqa: BLE001
            findings.append(f"{label} was refused ({type(e).__name__}: {str(e)[:140]}). The guard is on "
                            f"a second LEARNING pass at one window index and on nothing else.")

    detail = (f"{examined} case(s): the second learning pass refused at FAB_ROUTE_LEARN=1 and at "
              f"FAB_ROUTE_LEARN=0, with the message required to name the index, the clock and the two "
              f"passes it does not refuse; plus 3 legal shapes that must still run")
    return _report("F6", "a second gradient-carrying training pass at one window is refused by name",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F7 -- a Gate reason may not print an equation it did not read
# ==================================================================================================

# {gate name: (the lever its reason opens with, WHICH of the two arithmetic fields renders that lever)}.
# The nine reasons z_fabric.json found asserting "FAB_<LEVER>=0" over an operator's own negative. They
# are listed so this check cannot go vacuous: if a refactor stops these gates printing their equations,
# the check FAILS rather than passing over an empty set.
# THE SECOND HALF IS NOT BOOKKEEPING, IT IS THE HALF THAT MAKES THE ARITHMETIC CROSS-CHECK BITE. The
# check used to search `f"{gate.value} {gate.threshold}"` as ONE bag of numbers and ask whether ANY of
# them read the same, so a literal in one field was excused by a correct reading in the other:
# hardcoding fab.expert_choice's value to the string 'ec_w=-0.0' -- a real defect of exactly the class
# F7 exists for -- left the suite at 8 checks, 0 failing, because the threshold's own 'sum(use)=0.0'
# supplied a numerically matching token on the +0.0 arm. Naming the field is a SECOND declaration of
# something the source already says, and that is deliberate: if a gate moves its lever from `value` to
# `threshold` this check FAILS and says so, which is the same contract the coverage census below runs
# on -- 'has either regressed or moved without this list being updated'.
EQUATION_GATES = {
    "fab.balance": ("FAB_BALANCE", "value"), "fab.expert_choice": ("FAB_EC_W", "value"),
    "fab.explore": ("FAB_EXPLORE", "threshold"), "fab.discover": ("FAB_DISCOVER", "threshold"),
    "fab.distinctness": ("FAB_DIV_W", "value"), "fab.breadth_cap": ("FAB_DOM_FRAC", "threshold"),
    "fab.hop_sup": ("FAB_HOP_SUP", "value"), "fab.independence": ("FAB_IND_W", "value"),
    "fab.identity_round_trip": ("FAB_AE_W", "value"),
}

# A reason's LEADING equation is the reading that justifies the gate's verdict; anything later in the
# prose is discussion and may legitimately name another arm's value ("what makes this arm different from
# FAB_ON=0"). Only the leading one is a claim about what this pass read, so only it is checked.
_LEADING_EQUATION = re.compile(r"^FAB_([A-Z][A-Z0-9_]*)=(-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)"
                               r"(?=[:,) ]|$)")

def _reads_the_same(printed, actual):
    """Did these two print the SAME READING? Numeric, and -0.0 IS NOT 0.0.

    THE SIGN OF A ZERO IS THE WHOLE DISCRIMINATOR IN THIS CHECK, so it is compared here and not
    thrown away by `==`. Python's float comparison says -0.0 == 0.0, which is right for arithmetic
    and wrong for the question this file asks: `math.copysign` is the only way to ask which of the
    two a reader was handed. Non-numeric values (a str lever like FAB_HOP_MODE, a bool printed as
    `True`) fall back to a string comparison, which is what they were always compared with."""
    try:
        p, a = float(printed), float(actual)
    except (TypeError, ValueError):
        return str(printed) == str(actual)
    if p != a:
        return False
    if p == 0.0:
        return math.copysign(1.0, p) == math.copysign(1.0, a)
    return True


def _reading_key(actual):
    """A hashable identity for one reading, under the same rule: +0.0 and -0.0 are two readings, and
    False and 0 are one (a reason printing `FAB_HALT=0` over False is a correct reading)."""
    try:
        a = float(actual)
    except (TypeError, ValueError):
        return ("s", str(actual))
    return ("z", math.copysign(1.0, a)) if a == 0.0 else ("n", a)


def check_f7_gate_reasons_print_what_they_read():
    """Every gate reason that opens with FAB_<LEVER>=<value> must print the value the pass actually read.

    THE DEFECT THIS STANDS OVER: nine reasons hardcoded a 0 -- "ec_w=-1.0" printed in the gate's own
    `value` field, and one line below it "FAB_EC_W=0: allocation by loss pressure only". A Gate
    printing a FALSE EQUATION is worse than one printing nothing, because a reader who checks the
    arithmetic is checking a number nobody read.

    THE CHECK IS THE CLASS AND NOT THE NINE INSTANCES: it sweeps twelve configurations, parses the
    leading equation out of every reason any gate emitted, and compares it against the field on the
    frozen Config that the environment name resolves to (spine/lever.py generates PREFIX_FIELD, so
    FAB_EC_W is the field `ec_w`). Any new reason of the same shape is covered the day it is written.
    Booleans compare numerically -- FAB_HALT=0 against False is the same reading.

    WHY A NUMERIC COMPARISON ALONE WAS UNTRIPPABLE, AND WHAT MAKES IT TRIPPABLE AGAIN. F4 refuses
    every negative, so for a long while 0.0 was the ONLY value these nine `<= 0.0` branches could be
    entered at -- and a reason that hardcodes `=0` is then numerically IDENTICAL to one that prints
    what it read, on every arm. An earlier version answered that by also requiring the printed token
    to appear as text in the arithmetic the same Gate printed; .rework/audits/g_fab-tests.json refuted
    that answer and this file reproduced the refutation before repairing it: a hardcoded bare `0`
    survived on five of the nine (fab.balance, fab.explore, fab.discover, fab.breadth_cap,
    fab.identity_round_trip -- their arithmetic carries unrelated standalone zeros such as
    "0 row(s) swapped" and the literal threshold "> 0"), a hardcoded `0.0` survived on ALL NINE, and a
    CORRECT reason merely reformatted to `{ec_w:g}` was FAILED. Undersensitive to the defect,
    oversensitive to a reformat: a spelling test wearing a consistency test's name.

    THE REPAIR IS TO WIDEN THE DOMAIN, NOT TO TIGHTEN THE STRING, AND IT COUPLES THIS CHECK TO A
    REFUSAL IN ANOTHER FILE -- which is now written down at BOTH ends, beside `v < 0.0` in
    fabric/api.py::build as well as here, because a check that depends on a value continuing to be
    admitted and says so in only one of the two files is a trap for whoever tightens the other.
    `fabric/api.py::build` refuses a magnitude lever at `v < 0.0`, and -0.0 IS NOT LESS THAN 0.0 --
    so FAB_<LEVER>=-0.0 assembles, the frozen Config really holds -0.0 (checked here, per field,
    before anything is compared), and the
    `<= 0.0` branch really is entered with a NEGATIVE ZERO to print. That makes the reachable domain
    of all nine branches EXACTLY TWO VALUES, +0.0 and -0.0, and both are swept. Any constant typed
    into any of the nine reasons is therefore wrong on at least one of those two arms, whichever
    constant is chosen -- provided the comparison does not throw the sign away, which is why
    _reads_the_same exists. The arithmetic cross-check is KEPT, because it is the only thing holding
    the gate's own `value`/`threshold` fields to the same standard, but it now compares NUMBERS with
    that same signed-zero rule instead of searching for a text token: a reformatted field passes, and
    a hardcoded one fails, because nothing else in a Gate's arithmetic prints a negative zero. IT IS
    THE ONE FIELD THAT RENDERS THE LEVER AND NOT BOTH, which is what stops a literal in one field
    being excused by a correct reading in the other -- see the table above; that hole was live and is
    reproduced in this file's revert set.

    WHAT IT DOES NOT CATCH, PRINTED IN ITS OWN DETAIL LINE RATHER THAN LEFT TO THIS DOCSTRING. The
    argument above is a property of the SWEEP, not of the parser: a constant is only detectable where
    two arms read the field at two different values. That is guaranteed for the nine (and asserted --
    if a future edit drops the -0.0 arm, or stops one of the nine printing on it, this check FAILS
    rather than quietly losing its teeth). It is NOT true of the other pairs the sweep happens to
    cover -- fab.route_learned/FAB_ROUTE_LEARN, fab.halt/FAB_HALT and the rest print their reason
    ONLY when the lever is off, so they are read at one value and a constant there is invisible to
    this check. The detail line names every such pair by name.
    """
    findings, examined = [], 0
    # THE LAST TWO ARMS ARE THE PAIR THAT MAKES A CONSTANT DETECTABLE: the same nine levers at +0.0
    # and at -0.0, which is the entire reachable domain of the nine branches under F4's refusal.
    # Removing either one does not make this check greener -- it makes it FAIL on the required-pair
    # census below, which is the point: coverage of the nine is the assertion, not the tick.
    SOCIETY_NINE = ("FAB_EC_W", "FAB_EXPLORE", "FAB_DISCOVER", "FAB_DIV_W", "FAB_HOP_SUP",
                    "FAB_IND_W", "FAB_AE_W", "FAB_DOM_FRAC", "FAB_BALANCE")
    arms = (
        {}, {"FAB_ON": 0}, {"FAB_NORM_ONLY": 1}, {"FAB_SOCIETY": 1}, {"FAB_HALT": 0},
        {"FAB_ROUTE_LEARN": 0}, {"FAB_SPAWN": 0}, {"FAB_HOP_VOTE": 0}, {"FAB_GROW": 0},
        {"FAB_SOCIETY": 1, **{k: 0 for k in SOCIETY_NINE}},
        {"FAB_SOCIETY": 1, **{k: 0.5 for k in SOCIETY_NINE}},
        {"FAB_SOCIETY": 1, **{k: "-0.0" for k in SOCIETY_NINE}},
    )
    covered, readings = set(), {}
    for env in arms:
        c = cfg(**env)
        fab = c["FAB"].owned_by("FAB")
        # THE ARM IS ONLY EVIDENCE IF THE CONFIG REALLY HOLDS WHAT WAS ASKED FOR. A signed zero is
        # exactly the kind of value a parser flattens on the way in, and if it did, every conclusion
        # this check draws from that arm would be void while it stayed green.
        for name, want in env.items():
            if str(want) == "-0.0":
                got = getattr(fab, name[4:].lower())
                if not _reads_the_same("-0.0", got):
                    findings.append(f"the negative-zero arm asked for {name}=-0.0 and the frozen "
                                    f"Config reads {name}={got!r}. The sign was flattened somewhere "
                                    f"between the environment and the Config, so this arm no longer "
                                    f"discriminates a hardcoded 0 from a printed reading and the "
                                    f"nine reasons below are being checked against nothing.")
        pop = population(c)
        head, X = draw()
        out = forward(c, pop, head, X, 3)
        for gate in out.gates:
            m = _LEADING_EQUATION.match(gate.reason or "")
            if m is None:
                continue
            examined += 1
            env_name, printed, field = "FAB_" + m.group(1), m.group(2), m.group(1).lower()
            covered.add((gate.name, env_name))
            try:
                actual = getattr(fab, field)
            except LeverError:
                # NOT `if not hasattr(fab, field)`, WHICH IS THE UNTRIPPABLE-GUARD CLASS THIS FILE
                # INDICTS 60 INSTANCES OF, COMMITTED INSIDE THE CHECK. spine/lever.py::Config's
                # __getattr__ raises LeverError for a name its owner never declared, LeverError is
                # NOT a subclass of AttributeError (measured: issubclass(LeverError, AttributeError)
                # is False), and hasattr() catches only AttributeError -- so the test PROPAGATED the
                # error instead of ever being True. Planting FAB_HOP_SUPX= in one gate's reason on a
                # mirror killed the whole run with a traceback: F7 never reported, F8 never ran, and
                # there was no "=== N checks, M failing ===" line at all. The designed finding below
                # could not be reached from any tree.
                findings.append(f"gate {gate.name} prints {env_name}={printed} and the FAB Config has "
                                f"no field {field!r}. The equation names a lever this package does not "
                                f"own or that does not exist.")
                continue
            readings.setdefault((gate.name, env_name), set()).add(_reading_key(actual))
            if not _reads_the_same(printed, actual):
                findings.append(f"gate {gate.name} on arm {env or 'shipped'} prints "
                                f"'{env_name}={printed}' and the Config reads {env_name}={actual!r}. "
                                f"A reason asserting a value nobody read is a false equation, and a "
                                f"reader who checks it is checking nothing. (-0.0 and 0.0 are two "
                                f"different readings here and are reported as such: that is what "
                                f"makes a hardcoded zero visible at all.)")
            spec = EQUATION_GATES.get(gate.name)
            if spec is not None and spec[0] == env_name:
                # THE ONE FIELD THAT RENDERS THIS LEVER, not both of them bagged together -- see the
                # comment on EQUATION_GATES. The gate's own arithmetic, which the repair never
                # touched, carries the same number in that field.
                where = spec[1]
                arithmetic = str(getattr(gate, where))
                if not any(_reads_the_same(printed, t) for t in _NUMBER.findall(arithmetic)):
                    findings.append(
                        f"gate {gate.name} on arm {env or 'shipped'} prints '{env_name}={printed}' in "
                        f"its reason and no number equal to it -- compared numerically, with the sign "
                        f"of a zero kept -- in the arithmetic field that renders that lever, its "
                        f"{where}= ('{arithmetic}'). The two are the same lever read at the same "
                        f"instant, so a disagreement means one of them is a literal -- which is the "
                        f"defect exactly: 'ec_w=-1.0' printed one line above 'FAB_EC_W=0'. (The other "
                        f"field is NOT searched: it used to be, and a literal in one field was then "
                        f"excused by a correct reading in the other.)")

    for gate_name, (env_name, _rendered_in) in sorted(EQUATION_GATES.items()):
        # `.get`, AND ON BOTH READS. `covered` is added to BEFORE the equation is resolved against the
        # Config and `readings` only after it, so a pair recorded as covered whose field does not
        # exist reaches this loop with no reading at all -- and a subscript here raised KeyError from
        # inside the finding this branch exists to print. Reproduced on a mirror: with one gate's
        # reason printing FAB_HOP_SUPX= and this table naming the same pair, the run died at
        # `sorted(readings[...])` with no "=== N checks ===" line.
        seen = readings.get((gate_name, env_name), set())
        if (gate_name, env_name) not in covered:
            findings.append(f"gate {gate_name} never printed a leading '{env_name}=<value>' equation on "
                            f"any of the {len(arms)} arms swept. It is one of the nine that asserted a "
                            f"hardcoded 0, so a reason that no longer prints its reading has either "
                            f"regressed or moved without this list being updated.")
        elif len(seen) < 2:
            findings.append(f"gate {gate_name} printed '{env_name}=<value>' on {len(arms)} arm(s) but "
                            f"at ONE reading only ({sorted(seen)}). A "
                            f"constant typed into that reason is then numerically indistinguishable "
                            f"from a correct read on every arm swept, and this check would be green "
                            f"over the exact defect it exists for. The sweep must read {env_name} at "
                            f"two distinct values; +0.0 and -0.0 are the two that fabric/api.py::build "
                            f"leaves reachable for a `<= 0.0` branch, and the last two arms are them.")

    unpinned = sorted(f"{g}/{e}" for (g, e), v in readings.items()
                      if len(v) < 2 and (g not in EQUATION_GATES or EQUATION_GATES[g][0] != e))
    detail = (f"{examined} leading equation(s) parsed from gate reasons over {len(arms)} configuration(s), "
              f"each compared against the frozen Config field its environment name resolves to and, for "
              f"the {len(EQUATION_GATES)} repaired reasons, against the ONE arithmetic field of "
              f"their own Gate that renders that lever (its value= or its threshold=, per the table, "
              f"never the two searched as one bag) -- both comparisons NUMERIC and both treating "
              f"-0.0 and 0.0 as two readings; "
              f"{len(covered)} distinct (gate, lever) pair(s), and all {len(EQUATION_GATES)} of the "
              f"repaired reasons required to appear AND required to be read at two distinct values, so "
              f"no constant satisfies both arms\n      WHAT THIS CANNOT CATCH, said here rather than "
              f"left to the docstring: {len(unpinned)} other pair(s) were read at ONE value on every "
              f"arm -- {', '.join(unpinned) or 'none'} -- because those reasons are emitted only when "
              f"the lever is off. A constant equal to that one reading is invisible to this check and "
              f"is NOT claimed to be caught")
    return _report("F7", "no gate reason prints an equation the pass did not read",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F8 -- manage_period: the typed cadence, and the refusal that is kept WITH A SWITCH
# ==================================================================================================

NEGATIVE_CADENCES = (-5, -7)


def _period_refusal(every, *, couplings=None):
    """(layer, message, value) for FAB_MANAGE_EVERY=<every> -- who refused it, what they said, and
    what came back if nobody did.

    TWO DOORS, AND ONLY ONE OF THEM IS OPEN THROUGH THE ROOT. spine/derive.py::flush_period_windows
    refuses a negative period_windows inside the FAB.d_manage_period coupling's compute, so
    assemble.build raises BEFORE any Config is frozen -- which means FAB's own guard, and both
    positions of src/fabric/api.py::REFUSE_NEGATIVE_PERIOD, are unreachable through the ordinary
    call and a check that only tries it holds the switch to NOTHING (flipping it to False, or
    deleting FAB's guard outright, changes nothing such a check can see). `couplings=[]` is the
    other door: it is a parameter of spine/assemble.py::build, not a private one, and
    src/fabric/api.py::manage_period's own comment names this exact call as the only way left to
    hand FAB's guard a frozen Config carrying a negative. Both are run here."""
    lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e["FAB_MANAGE_EVERY"] = str(every)
    kw = {} if couplings is None else {"couplings": couplings}
    try:
        configs, _wires, warnings = assemble.build(e, **kw)
    except Exception as exc:                      # noqa: BLE001 -- classified below, not swallowed
        # THE LAYER IS READ OFF THE EXCEPTION, NOT ASSERTED BESIDE IT. This block returned the
        # string "the assembly (spine/derive.py::flush_period_windows, via the FAB.d_manage_period
        # coupling)" as a LITERAL until 2026-09-15, so the one thing F8 claims to establish -- that
        # the report names the layer that actually stopped the value -- was a sentence this helper
        # wrote rather than a fact it observed. Any other failure inside assemble.build (a different
        # coupling's compute, an unrelated derive refusal, a typo in the environment dict) would
        # have been reported under flush_period_windows' name, and the check would have passed while
        # describing a mechanism that never ran. The FAB door below was already honest -- it catches
        # LeverError and names FAB.manage_period because that is the only thing that raises there --
        # and the asymmetry between the two halves is what made this one easy to miss.
        tb = exc.__traceback__
        frame = None
        while tb is not None:                     # the DEEPEST frame is the one that raised
            frame = tb.tb_frame
            tb = tb.tb_next
        where = "unknown"
        if frame is not None:
            mod = frame.f_globals.get("__name__", "?").replace(".", "/")
            where = f"{mod}.py::{frame.f_code.co_name}"
        return f"the assembly ({where})", str(exc), None
    if warnings:
        raise AssertionError(f"assemble.build warned on {e}: {warnings}")
    try:
        return None, "", FAB.manage_period(configs["FAB"])
    except LeverError as exc:
        return "FAB.manage_period", str(exc), None


def check_f8_manage_period_kind_and_refusal():
    """The third FAB entry point with a body, and nothing had ever called it either.

    THE KIND is why the accessor exists at all: Config hands back a bare int for every lever that
    declares a Clock unit, and RUN's Cadences.due refuses an int -- so `manage_period` must return a
    units.Windows, and a plain int here is the defect the accessor was written to end. It is a
    CONSTRUCTION and not a conversion, so the number must come back unchanged.

    THE NEGATIVE IS CHECKED AS A PROPERTY OF THE PATH AND NOT OF ONE FILE'S LINE, because the tree
    moved while this file was being written and that is exactly the case a per-line test gets wrong.
    There are now TWO refusals between the environment and a cadence reader, in different packages:
    spine/derive.py::flush_period_windows refuses a negative period_windows, and it runs inside the
    coupling compute for FAB.d_manage_period, so it fires during spine.assemble.build -- BEFORE any
    Config exists; and src/fabric/api.py::manage_period refuses one at its own read, governed by
    src/fabric/api.py::REFUSE_NEGATIVE_PERIOD, which .rework/DECISIONS.md D4 makes a first-class
    configuration ("make OFF a first-class configuration"). What this check demands is the property
    both exist for -- a negative cadence never reaches a reader -- and it REPORTS which layer did the
    refusing, in the detail line, so that the day one of them moves the report says so instead of the
    check quietly going green over the other. Measured on the tree as it stands: the ASSEMBLY refuses
    first through the ordinary call, which means FAB's own guard cannot be reached through a plain
    assemble.build at all today; that is filed for FAB's owner rather than failed here, because the
    value IS refused and refused early.

    AND THAT IS WHY THERE ARE TWO DOORS AND NOT ONE. Trying only the ordinary call held D4's switch to
    NOTHING: with the assembly raising first, the entire limb that reads REFUSE_NEGATIVE_PERIOD is dead
    under the test, and .rework/audits/g_fab-tests.json showed the consequence -- flipping the switch to
    False, and deleting FAB's guard outright, each left this check GREEN. Reproduced here before it was
    repaired. So the negative is pushed at BOTH doors: the composition root, which proves the value
    never reaches a reader in a real run, and `assemble.build(..., couplings=[])`, which is a parameter
    of spine/assemble.py::build and the call src/fabric/api.py::manage_period's own comment names as the
    only way left to hand FAB's guard a frozen Config carrying a negative. On the second door the switch
    binds in both positions and FAB's guard is load-bearing again.

    THE NAMING HALF IS MEASURED PER LAYER RATHER THAN ASSERTED OF ALL OF THEM, because the old form of
    it passed for the wrong reason. `'FAB_MANAGE_EVERY' in message` was satisfied on the assembly's path
    by a HISTORICAL EXAMPLE about a different value -- "FAB_MANAGE_EVERY=-500 built
    FAB.d_manage_period=Flushes(1)", 249 characters from the number actually read -- so rewording that
    one sentence, in a file FAB does not own, broke this check while nothing about the refusal changed.
    What is asserted now is (a) that every refusal names the value it READ, tested by making the value
    MOVE -- two negatives are pushed, and each message must carry its own as a standalone number and
    must NOT carry the other -- and (b) that SOME layer on the path names the lever BESIDE that value.
    Which layers do and which do not is printed in the detail line every run: today FAB's own refusal
    does, and spine/derive.py::flush_period_windows does not, because a generic conversion is not handed
    the name of the lever whose wire it is computing. That is a real gap and it is filed as one; it is
    not a thing this check can assert into existence from another package.
    AND (b) IS ASSERTED ONLY WHERE THE PROMISE EXISTS, which the first version of it got wrong in a way
    that made a DECLARED-LEGAL configuration un-green. FAB's refusal is the only satisfier of (b) on
    this path, so with REFUSE_NEGATIVE_PERIOD off -- where D4 says FAB must not refuse at all -- (b)
    could not be met by any behaviour FAB is permitted to have, and flipping the switch and changing
    nothing else turned this check RED on (b) alone. In the OFF position (b) is now REPORTED on the
    detail line and not asserted, while (a), the kind, the Windows(every) contract and "the value never
    reaches a reader" all still bind. Measured both ways: with the switch ON and FAB's refusal reworded
    so it no longer names the lever beside the value it read, this check still FAILS.

    THE ONE THING THAT WOULD FAIL IT is the value arriving at a reader. If assembly accepts a
    negative and manage_period hands back a period, then either FAB's switch is on and its refusal
    did not bind, or the switch is off and OFF must mean exactly the pre-refusal behaviour,
    Windows(-5) -- and anything else is a third answer for one number.

    ZERO IS NOW REFUSED BY THE ASSEMBLY AND THIS CHECK HOLDS IT TO THAT, WHICH IS THE OPPOSITE OF
    WHAT IT HELD UNTIL 2026-09-14 -- so the argument is rewritten and not flipped. The earlier
    ruling here was that 0 must assemble and return Windows(0), on the ground that no meaning for 0
    had been declared for this lever and a guard that quietly folded it in would be deciding a
    question nobody ruled on. THE FIRST HALF OF THAT IS STILL TRUE AND IS NOW THE REASON FOR THE
    REFUSAL RATHER THAN AGAINST IT. Nothing declares 0 here: fabric/levers.py::FABLevers.manage_every
    gives it no meaning, src/fabric/api.py::manage_period gives it none, and FAB has no `manage`
    flag -- DOM has one, and in the frozen tree the off switch for BOTH management passes was the
    FLAG MANAGE ("MANAGE=0 -> ABLATION: no merge/cull", self_organize.py:954), which the package
    split gave to DOM alone. The cadence itself is read there as `step % MANAGE_EVERY == 0` at
    :6716, :6764 and :6768 with no max(1, ...) anywhere, so 0 is an integer modulo by zero on the
    first window and not an ablation -- which is the ruling domains/levers.py::DOMLevers.manage_every
    already wrote down, in those words, for the sibling lever this one was SPLIT FROM.

    WHAT CHANGED IS THAT "NOBODY RULED ON IT" STOPPED BEING TRUE OF THE RUNNING TREE: three readers
    were answering it at once, measured by building this tree at that value --
        the FAB.d_manage_period coupling floored it to Flushes(1), manage on EVERY flush and the
        tightest cadence the system has; FAB.manage_period returned Windows(0); and
        spine/derive.py::cadences_that_cannot_fire reported ('fab.manage', 0, 0), a gate that
        CANNOT FIRE.
    That is the same three-way split, reader for reader, that FAB_MANAGE_EVERY=-5 carried until the
    negative was refused on 2026-09-05. An undeclared value with three simultaneous answers is not
    an open question being respected, it is the defect the refusal exists for. So
    spine/derive.py::flush_period_windows refuses a period below one, and what this check requires
    at 0 is the refusal and no longer Windows(0).

    THE SECOND DOOR IS MEASURED AND REPORTED, NOT ASSERTED, AND THAT ASYMMETRY IS DELIBERATE. With
    the coupling table emptied, 0 still reaches FAB's own guard -- which is `< 0`, not `< 1` -- and
    comes back Windows(0). Widening that guard is FAB's edit in FAB's own file, and this file may
    not assert a refusal another package has not written. Both doors are printed on the detail line
    every run, so the day FAB widens it the report says so instead of a check going quietly greener.

    AND THE ARM IS SHARED, WHICH IS ALSO MEASURED HERE RATHER THAN LEFT IN AN AUDIT FILE. Three
    coupling rows reach spine/derive.py::flush_period_windows and two of them carry CAP_PIN_WINDOWS,
    so the same `< 1` refuses CAP_PIN_WINDOWS=0 -- a THRESHOLD and not a cadence, in
    capacity/levers.py::CAPLevers.pin_windows's own words. That is CAP's range question, not FAB's
    to assert; it is driven once here and printed, so the collateral of the refusal this check
    depends on is visible in the same report as the refusal.
    """
    findings, examined = [], 0

    for every in (1, 500):
        examined += 1
        got = FAB.manage_period(cfg(FAB_MANAGE_EVERY=every)["FAB"])
        if not isinstance(got, U.Windows):
            findings.append(f"FAB_MANAGE_EVERY={every}: manage_period returned {got!r} "
                            f"({type(got).__name__}). RUN's Cadences.due refuses a bare int, and the "
                            f"whole reason this accessor exists is to attach the kind the lever "
                            f"declares.")
        elif int(got.n) != every:
            findings.append(f"FAB_MANAGE_EVERY={every}: manage_period returned {got!r}. It is a "
                            f"CONSTRUCTION and not a conversion -- nothing here may cross clock kinds.")

    # ----------------------------------------------------------------------------------------------
    # ZERO, AT BOTH DOORS. It used to be the third member of the loop above, required to come back
    # Windows(0); the docstring says why it is a refusal now. THE NAMING HALF IS NOT ASSERTED HERE
    # and the reason is the one this check makes elsewhere: the refusal's message is full of the
    # digit 0 in prose about other levers, so `'0' in spoken` is untrippable -- it cannot tell a
    # reading from a sentence, which is exactly the failure the negative half was rebuilt to avoid.
    # What is asserted is the property: 0 does not reach a reader through the composition root.
    # ----------------------------------------------------------------------------------------------
    zero_lines = []
    examined += 1
    z_layer, _z_message, z_value = _period_refusal(0)
    zero_lines.append(f"through the composition root: {z_layer or 'nobody'}")
    if z_layer is None:
        findings.append(
            f"FAB_MANAGE_EVERY=0 reached a reader as {z_value!r} through the composition root. Zero "
            f"carried THREE answers in this tree at once -- Flushes(1) from the FAB.d_manage_period "
            f"coupling (manage on EVERY flush), Windows(0) from FAB.manage_period, and "
            f"('fab.manage', 0, 0) from spine/derive.py::cadences_that_cannot_fire (a gate that "
            f"cannot fire) -- while nothing declares a meaning for it: FAB has no `manage` flag, and "
            f"the frozen source reads the knob as `step % MANAGE_EVERY == 0` with no max(1, ...), "
            f"where 0 is an integer modulo by zero. spine/derive.py::flush_period_windows refuses a "
            f"period below one so that an undeclared value with three readings cannot reach any of "
            f"them, and this is that refusal not happening.")

    examined += 1
    z2_layer, _z2_message, z2_value = _period_refusal(0, couplings=[])
    zero_lines.append("with the coupling table emptied: "
                      + (z2_layer or f"nobody -- FAB's own guard is `< 0` and returned {z2_value!r}, "
                                     f"which is FAB's to widen and is NOT asserted here"))

    # THE COLLATERAL OF THE ARM THIS CHECK DEPENDS ON, DRIVEN RATHER THAN DESCRIBED. Two of the three
    # coupling rows that reach spine/derive.py::flush_period_windows carry CAP_PIN_WINDOWS, so the
    # `< 1` above is also a refusal of CAP_PIN_WINDOWS=0. Reported, not asserted: CAP's domain is
    # CAP's, and this file's business is that the consequence is not invisible.
    examined += 1
    try:
        _c = cfg(CAP_PIN_WINDOWS=0)
        cap_zero = (f"NOT refused -- it built FAB.d_cap_lift_period="
                    f"{_c['FAB'].d_cap_lift_period!r}")
    except U.UnitError as exc:                    # noqa: BLE001 -- reported below, not swallowed
        cap_zero = f"refused by the same arm ({str(exc).split('.')[0]})"

    switch = bool(FAB.REFUSE_NEGATIVE_PERIOD)
    verdicts, lines = {}, []
    for every in NEGATIVE_CADENCES:
        for where, couplings in (("through the composition root", None),
                                 ("with the coupling table emptied", [])):
            examined += 1
            layer, message, value = _period_refusal(every, couplings=couplings)
            verdicts[(where, every)] = (layer, message, value)
            if layer is None:
                if switch:
                    findings.append(
                        f"{where}: REFUSE_NEGATIVE_PERIOD is True and FAB_MANAGE_EVERY={every} "
                        f"reached a reader as {value!r}. Cadences.due fires when "
                        f"`step - last_fired >= period`, so a negative period is true on the first "
                        f"window and every window after -- the cull, the spares, replication and the "
                        f"staged-depth check on EVERY window, while "
                        f"spine/derive.py::cadences_that_cannot_fire reports the same value as a gate "
                        f"that cannot fire.")
                elif not isinstance(value, U.Windows) or int(value.n) != every:
                    findings.append(
                        f"{where}: REFUSE_NEGATIVE_PERIOD is False and FAB_MANAGE_EVERY={every} "
                        f"returned {value!r}. OFF is a configuration, and D4 makes it the PRE-REFUSAL "
                        f"behaviour exactly, which was Windows({every}). A third answer for one "
                        f"number is the defect the refusal was written to end, not a milder version "
                        f"of it.")
            elif layer == "FAB.manage_period" and not switch:
                findings.append(
                    f"{where}: REFUSE_NEGATIVE_PERIOD is False and FAB.manage_period refused anyway. "
                    f"The switch is the second half of the owner's ruling and it does not bind, so "
                    f"OFF is not a configuration -- which is the code path D4 exists to keep from "
                    f"rotting.")
            else:
                # THE VALUE MUST BE A READING AND NOT PROSE, which is tested by making it MOVE: the
                # message raised over -5 must carry -5 as a standalone number and must NOT carry -7,
                # and the other way round. The old test asked only `'-5' in message`, which a
                # sentence about a different value satisfies -- and on the assembly's path that is
                # exactly what satisfied it (`FAB_MANAGE_EVERY=-500` in a historical example).
                spoken = {t for t in _NUMBER.findall(message)}
                others = {str(o) for o in NEGATIVE_CADENCES if o != every}
                if str(every) not in spoken:
                    findings.append(f"{where}: the refusal from {layer} at FAB_MANAGE_EVERY={every} "
                                    f"names no standalone {every} anywhere in its message, so it does "
                                    f"not say what it read: {message[:160]}")
                if spoken & others:
                    findings.append(f"{where}: the refusal from {layer} at FAB_MANAGE_EVERY={every} "
                                    f"also names {sorted(spoken & others)}, the OTHER value this "
                                    f"check pushes at it. The number in the message is then not a "
                                    f"reading of this read and cannot be told from prose.")

    # DOES ANY REFUSAL ON THE PATH NAME THE LEVER *AND* THE VALUE IT READ, TOGETHER? That is the
    # spine's rule for an unreachable arm, and the honest way to test it is JOINTLY -- a lever name
    # 249 characters away from the number, inside a paragraph about a different value, is prose that
    # happens to contain the right word. Each layer's verdict is REPORTED below whatever it is; what
    # is ASSERTED is that the path as a whole produces one refusal that says both.
    joint = {}
    for (where, every), (layer, message, _v) in sorted(verdicts.items()):
        if layer is None:
            continue
        joint[(layer, every)] = _names_lever_and_value(message, "FAB_MANAGE_EVERY", every)
    named = sorted({lay for (lay, _e), ok in joint.items() if ok})
    prose = sorted({lay for (lay, _e), ok in joint.items() if not ok})
    # ASSERTED WHERE THE PROMISE EXISTS, REPORTED WHERE IT DOES NOT. FAB.manage_period is the only
    # layer on this path that names the lever beside the value it read, and with REFUSE_NEGATIVE_PERIOD
    # OFF it does not refuse at all -- by design: .rework/DECISIONS.md D4 makes OFF the pre-refusal
    # behaviour exactly, and the pre-refusal behaviour named nothing because there was no refusal. So
    # the unconditional form reported a DECLARED-LEGAL configuration as a defect, in a message that is
    # true but is a statement about spine/derive.py's wording rather than about anything the operator
    # did or FAB failed to do: flipping the switch and changing nothing else turned this check RED
    # (measured -- exit 1, "=== 8 checks, 1 failing ===", this finding the only one).
    # THIS IS NOT THE ASSERTION GOING AWAY. In the shipped position it is unchanged and is the thing
    # that fails if FAB's refusal stops naming both; in the OFF position the naming gap belongs to
    # spine/derive.py::flush_period_windows, is FAB's to report and not FAB's to fix, and is printed
    # on the detail line either way. What the OFF position still asserts is one door up: that FAB did
    # not refuse (the `layer == "FAB.manage_period" and not switch` finding above) and that it handed
    # back Windows(every).
    if switch and joint and not named:
        findings.append(f"no refusal on this path names FAB_MANAGE_EVERY beside the value it read. "
                        f"The layers that refused were {prose} and each of them names the lever, if "
                        f"at all, somewhere other than beside the number -- which is prose, not a "
                        f"reading. An unreachable arm names the lever AND the value that made it so.")

    for where, every in (("through the composition root", NEGATIVE_CADENCES[0]),
                         ("with the coupling table emptied", NEGATIVE_CADENCES[0])):
        lay, _m, _v = verdicts[(where, every)]
        lines.append(f"{where}: {lay or 'nobody'}")

    detail = (f"{examined} case(s): manage_period at FAB_MANAGE_EVERY 1 and 500 required to return "
              f"units.Windows carrying that number; 0 required to be REFUSED before it reaches any "
              f"reader -- {'; '.join(zero_lines)}; the SAME arm driven on the other lever that "
              f"reaches it, CAP_PIN_WINDOWS=0: {cap_zero} (reported, not asserted -- CAP's domain "
              f"is CAP's); and {list(NEGATIVE_CADENCES)} pushed at TWO doors "
              f"-- {'; '.join(lines)} (REFUSE_NEGATIVE_PERIOD={switch}). The second door is what holds "
              f"D4's switch to meaning something: the assembly refuses first through the root, so "
              f"FAB's own guard and both positions of its switch are DEAD to a check that only tries "
              f"that door\n      WHO NAMES WHAT, measured per layer rather than asserted: "
              + ("; ".join(f"{lay} names the lever beside the value it read" for lay in named) or "none")
              + (("; " + "; ".join(f"{lay} does NOT -- it names the value it read but the lever only "
                                   f"as prose elsewhere in the message (a generic conversion cannot "
                                   f"know whose lever it was handed), so THAT half is reported here "
                                   f"and not claimed" for lay in prose)) if prose else "")
              + ("" if switch else
                 "\n      REFUSE_NEGATIVE_PERIOD IS OFF, so the joint-naming assertion is REPORTED "
                 "above and not asserted: D4 makes OFF the pre-refusal behaviour, in which FAB does "
                 "not refuse and therefore names nothing, and the only refusal left is the "
                 "assembly's, whose wording is spine/derive.py's to fix and not FAB's. What is still "
                 "asserted in this position is that FAB did NOT refuse and returned Windows(every)"))
    return _report("F8", "a management cadence below one never reaches a reader, and the report says "
                         "which layer stopped it",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F9 -- a rendered Gate line may not contradict the arithmetic it prints
# ==================================================================================================

# {gate name: the relation that OPENS it, over the pair it prints as (value vs threshold)}.
# ONE MEMBER, AND THE TABLE IS THE WHOLE OF WHAT MAKES THIS CHECK SOUND. spine/gate.py::Gate.line
# prints NO OPERATOR, so a rendered pair cannot say on its own whether a gate is a `>=` or a `<` --
# tests/test_contract.py::check_k16_verdicts_follow_their_printed_pair refuses to guess it and says so
# in its own report line, and a rule reading "fired implies value >= threshold" over every Gate in the
# tree would call correct `<` and `!=` gates defects. What this file has that a static reader does not
# is an AUTHOR: fab.cull_gate's pair is the occupancy against FAB_PRESSURE and
# spine/derive.py::cull_gate_open opens at `not (ratio < pressure)`, so `>=` is the relation and it is
# written down here rather than inferred. Most FAB gates are NOT in this table and must not be: their
# pair is DESCRIPTIVE -- fab.explore prints "0 row(s) swapped ... vs explore=0.15, computed=4 of
# n_live=4" -- and inviting arithmetic is exactly what those pairs do not do. The count of gates seen
# and skipped is on the report line, so the size of what is not judged is visible rather than implied.
ARITHMETIC_GATES = {"fab.cull_gate": ">="}

# (FAB_N0, FAB_SLOTS, FAB_PRESSURE, why this row is here). The last two are the ROUNDING shape, which
# needs no floor at all: `.3f` of the ratio can land on the other side of the setpoint from the ratio
# itself, in both directions, and both are reachable from the lever space at these widths.
CULL_ROWS = (
    (2, 2, 0.45,   "floor shuts it while the printed occupancy 1.000 meets the printed 0.45"),
    (2, 4, 0.45,   "floor shuts it while the printed occupancy 0.500 meets the printed 0.45"),
    (2, 100, 0.45, "floor AND occupancy both shut it, and the printed pair agrees with the verdict"),
    (3, 4, 0.45,   "above the floor and over the setpoint: FIRED, and the pair says so"),
    (5, 8, 0.45,   "above the floor and over the setpoint at the base widths"),
    (4, 6, 0.6667, "ROUNDING: shut at ratio 0.6666..., and the printed 0.667 meets the printed 0.6667"),
    (5, 6, 0.8333, "ROUNDING: FIRED at ratio 0.8333..., and the printed 0.833 is under 0.8333"),
)


def _rendered_pair(gate):
    """The two numbers a READER takes off the rendered line, or None if the pair is not two numbers.

    The value field is a rendering of a quantity -- "2/2=1.000" -- and what the reader compares is
    what is rendered, so the number after the LAST `=` is taken and the working before it is not.
    A field that carries no number at all is not an arithmetic and this check leaves it alone.
    """
    shown = str(gate.value)
    shown = shown.rsplit("=", 1)[-1] if "=" in shown else shown
    try:
        return float(shown), float(gate.threshold)
    except (TypeError, ValueError):
        return None


def check_f9_rendered_gate_lines_agree_with_their_own_arithmetic():
    """A Gate line that prints a verdict word beside a pair of numbers may not have them disagree.

    THE DEFECT THIS STANDS OVER, and it shipped for six rounds in the file this check covers.
    spine/gate.py::Gate says `value` and `threshold` are printed so the reader can do the arithmetic
    themselves, and spine/gate.py::Gate.line prints the verdict word, that pair, and -- only when a
    reason is set -- the reason. src/fabric/api.py's fab.cull_gate had no reason, and its verdict is
    spine/derive.py::cull_gate_open, which is TWO clauses: a FLOOR on the live population and the
    occupancy test. The pair renders the occupancy test alone, so at FAB_N0=2 FAB_SLOTS=2
    FAB_PRESSURE=0.45 the line read

        Gate fab.cull_gate: armed, did not fire (2/2=1.000 vs 0.45)

    -- 1.000 meets 0.45, beside the words reserved for a condition that ran and was not met. A reader
    who does the arithmetic the line invites gets the opposite answer from the line.

    IT IS TWO SHAPES AND NOT ONE, which is why this sweeps rather than plants a single case. The floor
    is one; the other needs no floor and no second clause at all -- the occupancy is printed through
    `.3f`, and a rounded ratio can land on the other side of the setpoint from the ratio actually
    compared, in EITHER direction. Both are in CULL_ROWS above, both were measured on the lever space
    before they were written down, and the FIRED direction (5/6 at FAB_PRESSURE=0.8333, printed 0.833)
    is the one no floor argument reaches.

    WHICH LINE IS READ (2026-09-24). At build fab.cull_gate is now a PREDICTION reported UNREACHABLE
    -- no fab.manage pass has run, so no cull was evaluated, and a default 80-window run printed it
    FIRED beside a manage ledger of 0 fires -- so each row asserts that, then drives ONE FAB.manage
    pass and reads the verdict that pass leaves on pop.gates, which is the line a report prints.

    WHAT IS ASSERTED. For every gate in ARITHMETIC_GATES, on every row: read the rendered line, take
    the pair off it, apply the relation the table declares, and compare that answer with the verdict
    word the same line prints. WHERE THEY DISAGREE THE LINE MUST CARRY A REASON -- that is the whole
    rule, and it is the runtime half of K16 --
    tests/test_contract.py::check_k16_verdicts_follow_their_printed_pair -- which reads the SOURCE
    and therefore sees the floor clause but cannot see a rounded render at all. A reason is NOT
    required where the pair justifies the verdict; a caveat there is legitimate and
    spine/gate.py::Gate.line says so.

    WHAT IS NOT ASSERTED, said here and printed in the detail line rather than left to a docstring:
    whether the reason NAMES the clause that actually decided. That is prose, this check does not read
    it, and a reason saying anything at all exempts the line here -- the same limit K16 states for the
    same reason. Nor is the DIRECTION of any gate outside ARITHMETIC_GATES judged; the pair of every
    other FAB gate is descriptive and is counted, not read.

    THE CENSUS IS PART OF THE ASSERTION. The sweep must produce BOTH kinds of row -- at least one
    where the pair contradicts the verdict and at least one where it does not -- or the check is
    reporting on a population that cannot show the defect, which is this suite's own most repeated
    finding about other people's checks.
    """
    findings, examined = [], 0
    contradicting, agreeing, descriptive = 0, 0, 0

    build_predictions = 0
    for n0, slots, pressure, why in CULL_ROWS:
        c = cfg(FAB_N0=n0, FAB_SLOTS=slots, FAB_PRESSURE=pressure)
        pop = population(c)
        # AT BUILD fab.cull_gate IS A PREDICTION REPORTED UNREACHABLE (no manage pass has run, so no
        # cull was evaluated -- 2026-09-24); the VERDICT is FAB.manage's, which replaces it by name.
        # So the build line is required to be UNREACHABLE with a reason, and the arithmetic is read
        # off the gate one manage pass leaves -- the line every report after the first pass prints.
        _pred = [g for g in pop.gates if g.name == "fab.cull_gate"]
        if not (_pred and not _pred[0].reachable and _pred[0].reason):
            findings.append(f"FAB_N0={n0} FAB_SLOTS={slots}: the build-time fab.cull_gate is "
                            f"{_pred[0].line() if _pred else 'absent'!r}; before any manage pass it "
                            f"must be UNREACHABLE with its prediction in the reason.")
        else:
            build_predictions += 1
        FAB.manage(c["FAB"], pop, step_windows=U.Windows(int(c["FAB"].manage_every)),
                   flush_loss=None)
        for gate in pop.gates:
            relation = ARITHMETIC_GATES.get(gate.name)
            if relation is None:
                descriptive += 1
                continue
            line = gate.line()
            head = line.split(": ", 1)[1]
            if head.startswith("UNREACHABLE"):
                # THE THIRD STATE IS NOT THIS CHECK'S SUBJECT: spine/gate.py::Gate refuses to be
                # built unreachable without a reason, so that arm already carries one by construction.
                continue
            pair = _rendered_pair(gate)
            if pair is None:
                descriptive += 1
                continue
            examined += 1
            value_n, threshold_n = pair
            pair_says_open = value_n >= threshold_n if relation == ">=" else value_n > threshold_n
            fired_printed = head.startswith("FIRED")
            if pair_says_open == fired_printed:
                agreeing += 1
                continue
            contradicting += 1
            if not (gate.reason and gate.reason in line):
                findings.append(
                    f"FAB_N0={n0} FAB_SLOTS={slots} FAB_PRESSURE={pressure} ({why}): the line reads "
                    f"{line!r}. The pair on it is {value_n} {relation} {threshold_n}, which is "
                    f"{pair_says_open}, and the verdict word printed beside it says fired="
                    f"{fired_printed}. Nothing else is on the line, so a reader who does the "
                    f"arithmetic spine/gate.py::Gate invites them to do gets the opposite answer "
                    f"from the gate. Name the clause that actually decided in a `reason` on the arm "
                    f"it decides -- or, if the mechanism could not run here, in `reachable=`.")

    if not contradicting:
        findings.append(f"no row in this sweep produced a line whose pair disagrees with its own "
                        f"verdict, so the rule was never exercised: {len(CULL_ROWS)} row(s) all "
                        f"agreed. A check that examined only the easy half of its population is "
                        f"green over the defect it exists for -- the sweep must keep at least one "
                        f"configuration in each state, and CULL_ROWS names why each row is there.")
    if not agreeing:
        findings.append(f"every row in this sweep contradicted itself, which means the sweep is not "
                        f"distinguishing anything: a rule that fires on the whole population says "
                        f"nothing about any member of it.")

    detail = (f"{build_predictions} build-time prediction(s) UNREACHABLE with a reason; "
              f"{examined} rendered manage-pass line(s) read over {len(CULL_ROWS)} configuration(s) for the "
              f"{len(ARITHMETIC_GATES)} gate(s) whose printed pair IS an arithmetic the reader is "
              f"invited to do ({', '.join(f'{g} opens at {r}' for g, r in sorted(ARITHMETIC_GATES.items()))}); "
              f"{contradicting} line(s) where the pair disagrees with the verdict word and each one "
              f"required to carry a reason, {agreeing} where it agrees and none required to; "
              f"{descriptive} gate line(s) seen and NOT judged because their pair is descriptive "
              f"rather than a comparison\n      WHAT THIS CANNOT CATCH: whether an exempting reason "
              f"actually names the clause that decided -- the reason is prose and is not read here -- "
              f"and the direction of any gate not in the table above, which spine/gate.py::Gate.line "
              f"prints no operator for and which this file declares rather than infers")
    return _report("F9", "no rendered gate line prints a verdict its own numbers contradict",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# The runner
# ==================================================================================================

CHECKS = (
    check_f1_var_cov_at_one_expert,
    check_f2_no_grad_pass_cannot_write_the_cache,
    check_f3_c2_alarm_agrees_with_the_gradient,
    check_f4_negative_magnitude_levers_refused,
    check_f5_aux_loss_has_a_graph_on_the_off_arms,
    check_f6_one_learning_pass_per_window,
    check_f7_gate_reasons_print_what_they_read,
    check_f8_manage_period_kind_and_refusal,
    check_f9_rendered_gate_lines_agree_with_their_own_arithmetic,
)


def main():
    print("=== fabric: what FAB.build, FAB.forward and FAB.manage_period actually do, run ===")
    print(f"torch {torch.__version__} on cpu; Python {sys.version.split()[0]}; "
          f"d_model={D_MODEL} sig_d={SIG_D} batch={BATCH} len={LEN} vocab={VOCAB}; "
          f"base environment {BASE}")
    print()
    failed = 0
    for check in CHECKS:
        failed += check()
        print()
    print(f"=== {len(CHECKS)} checks, {failed} failing ===")
    print("These are REAL forward and backward passes over a real assembled Config, so a green tick")
    print("here is evidence about behaviour and not about the text of the tree. It is not evidence")
    print("that the population LEARNS -- no optimizer runs in this file -- and it covers one hop arm,")
    print("one device and one dtype. FAB.observe, FAB.grow_check and the checkpoint pair are not")
    print("exercised here; FAB.manage runs once per F9 row for the cull gate's line, and")
    print("tests/test_fabric_internals.py drives its selection pass.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
