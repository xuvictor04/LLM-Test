"""FAB's repaired behaviour, exercised: real forward and backward passes over a real assembled Config.

    python3 tests/test_fabric.py          # PASS/FAIL per check with counts; non-zero exit on any FAIL

WHY THIS FILE EXISTS. Every other file in tests/ is a STATIC check: tests/test_ownership.py walks src/
with `ast` and does not execute it, tests/test_census.py and tests/test_contract.py read the tree and
compare it against itself, tests/test_derive.py replays a captured table through pure functions. None of
them calls FAB.forward or FAB.build -- and the gap is wider than that, measured rather than grepped:
running each of the six under runpy leaves `"fabric.api" in sys.modules` FALSE for every one, so nothing
in tests/ had imported this package at all. (grep alone is misleading here: tests/ carries twenty-odd
`from fabric...` lines and every one of them outside this file is inside a triple-quoted source fixture
the AST checks parse, or a comment.) Meanwhile fabric/api.py has taken the most behaviourally delicate
repairs in the project, and until this file every one of them was protected by nothing -- a static check
cannot see a NaN, cannot see a gradient that went to zero, and cannot see a counter that reads 1 over a
term that reaches no parameter. tests/test_couplings.py is the precedent for a file in this directory
that RUNS things; this is the second, and it runs torch.

WHAT IT COVERS AND WHAT IS LEFT. FAB has eleven public entry points and eight of them still raise
NotImplementedError (`grep -n "raise NotImplementedError" src/fabric/api.py` -> 8 sites: observe,
contribution, manage, grow_check, own_lr_scale, counters, state_dict, load_state_dict). The three with
bodies are `build`, `forward` and `manage_period`, and all three are exercised here -- so this file is
not a sample of FAB's behaviour, it is all of the behaviour FAB currently has.

THE EIGHT REPAIRS EACH CHECK STANDS OVER, and what each one cost when it was absent (the measurements
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
  F4  src/fabric/api.py::build refuses eleven negative magnitude levers. Three of them -- FAB_BALANCE,
      FAB_PONDER, FAB_EMB_VAR -- multiply their terms UNGUARDED, so a negative did not switch the
      mechanism off, it ran it BACKWARDS; the other eight are guarded at `> 0.0` and a negative was
      bit-identical to 0.0 while the gate printed the operator's negative beside a reason asserting the
      value was 0.
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
      position, to meaning anything.

EVERY CHECK WAS SEEN TO FAIL. A test never seen to fail is not known to test anything, and the survey of
the old tree counted 60 guards whose condition could not be satisfied. Each check here was run against a
scratch mirror of src/ OUTSIDE this repository with its own repair reverted -- the guard moved back below
the arithmetic, `write=learn` back to `write=solo` with the class guard deleted, the alarm back on
`bal.grad_fn`, the LeverError block deleted, `h[:0].sum()` back to `h.new_zeros(())`, the learn_window
refusal deleted, one reason's equation re-hardcoded -- and each one FAILED there, on its own check and
on no other, and passes here. TWELVE mirrors over the eight repairs, because two of the eight are not
one line in one file:
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
THE MOST USEFUL RESULT OF DOING THIS WAS A TEST OF MINE THAT DID NOT FAIL. F7's first version compared
the printed number to the Config numerically; F4 refuses every negative, so 0.0 is the only value those
nine branches can now be entered at, and the mirror with `FAB_EC_W=0` re-hardcoded passed it -- exit 0,
everything green, over the exact defect the check was written for. It is the 61st instance of the class
this suite carries 60 records of, and only the revert found it. The reverts, the widths and the numbers
they produced are recorded in .rework/audits/f_fabtests.json.

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
refused at build by Q-FAB-1), one device (cpu) and one dtype. FAB.observe, FAB.manage, FAB.grow_check,
FAB.own_lr_scale, FAB.counters, FAB.contribution and the checkpoint pair are not covered because they
raise NotImplementedError; the day any of them grows a body it needs a check here, and this file's count
will not notice on its own. It is also not a substitute for the static checks: whether a counter is
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
    mark = "PASS" if ok else "FAIL"
    note = "  (VACUOUS: 0 examined)" if vacuous else ""
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
              f"value AND gradient, 3 analytic n=1 cells against 1 - sqrt(1e-4), and 2 end-to-end "
              f"routed passes at n_live=1")
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

    # -- the class claim, over all three cache states the body can be in.
    c = cfg()
    pop = population(c)
    head, X = draw()
    composed_loss(forward(c, pop, head, X, 5), head, X).backward()
    for label, step in (("same window as the cache", 5), ("inside the emb_every cadence", 5),
                        ("a later window", 9)):
        examined += 1
        fields = ("ident_graph", "ident", "ident_step", "ident_live")
        before = tuple(getattr(pop, f) for f in fields)
        with torch.no_grad():
            _keys, refreshed = FAB._identities(pop, int(pop.n_live), step, 1, write=True)
        after = tuple(getattr(pop, f) for f in fields)
        if refreshed:
            findings.append(f"_identities(write=True) under no_grad at step {step} ({label}) reported "
                            f"refreshed=True. A pass with no graph to give refreshed nothing.")
        moved = [f for f, a, b in zip(fields, before, after) if a is not b]
        if moved:
            findings.append(f"_identities(write=True) under no_grad at step {step} ({label}) CHANGED "
                            f"{', '.join(moved)} -- pop.ident_step is now "
                            f"{pop.ident_step!r} and pop.ident_graph carries a grad_fn: "
                            f"{pop.ident_graph is not None and pop.ident_graph.grad_fn is not None}. "
                            f"The next training pass at that step is handed the graphless tensor this "
                            f"call stamped in, and the one gradient channel that reaches every live "
                            f"expert drops out of its backward.")
    if pop.ident_graph is None or pop.ident_graph.grad_fn is None:
        findings.append("after the three no_grad calls the surviving ident_graph has no grad_fn, so "
                        "the check above compared two broken states and proves nothing.")

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

    detail = (f"{examined} case(s): 3 direct no_grad writes against all three cache states, and 8 "
              f"gradient comparisons (4 arms x {{eval, leave-one-out}} inserted at window 6), each "
              f"against the same two training passes with nothing inserted")
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
# F4 -- eleven negative magnitude levers refused at build
# ==================================================================================================

REVERSED = ("FAB_BALANCE", "FAB_PONDER", "FAB_EMB_VAR")
GUARDED_OFF = ("FAB_EC_W", "FAB_EXPLORE", "FAB_DISCOVER", "FAB_DIV_W", "FAB_HOP_SUP",
               "FAB_IND_W", "FAB_AE_W", "FAB_DOM_FRAC")


def check_f4_negative_magnitude_levers_refused():
    """src/fabric/api.py::build refuses all eleven, alone, naming the lever AND the value it read.

    THE TWO GROUPS AND WHY BOTH ARE REFUSED. FAB_BALANCE, FAB_PONDER and FAB_EMB_VAR multiply their
    loss terms with no `> 0.0` in front of them, so a negative does not switch the mechanism off, it
    runs it BACKWARDS -- the population is paid to collapse onto one expert, the charge on routed
    depth becomes a subsidy, and the anti-collapse term becomes a pro-collapse one. The other eight
    are guarded and a negative is bit-identical to 0.0, so the refusal removes NO configuration an
    operator can ask for and makes a false gate reason impossible rather than correct once. The ground
    is src/capacity/api.py::new_valve's refusal of a negative CAP_LIFT.

    THE PREMISE OF THE FIRST GROUP IS MEASURED HERE, not quoted. src/fabric/api.py::_ae_loss takes
    emb_var as a plain argument, so the sign reversal is directly observable: at -1.0 the term is
    SUBTRACTED by exactly the amount +1.0 ADDS. That is the whole claim -- a negative is not "off" --
    and it stays testable after the refusal is in place, which the forward-path version does not.

    AND THE REFUSAL MUST NOT OVERREACH: 0.0 and 1.0 build for every one of the eleven, and
    FAB_BALANCE=5.0 -- a large pressure, still the pressure the lever names -- builds too. U.FRACTION
    is a label the census renders, not a bound.
    """
    findings, examined = [], 0

    for name in REVERSED + GUARDED_OFF:
        examined += 1
        try:
            c = cfg(**{name: -0.5})
        except Exception as e:                                # noqa: BLE001 -- reported, never swallowed
            findings.append(f"{name}=-0.5: assemble.build raised {type(e).__name__} before FAB.build "
                            f"could refuse it ({e}). The refusal under test is FAB's.")
            continue
        try:
            population(c)
            findings.append(f"{name}=-0.5 BUILT. "
                            + ("This lever multiplies its term unguarded, so the mechanism now runs "
                               "with its sign reversed and the objective pays for the opposite of "
                               "what the lever names." if name in REVERSED else
                               "This lever is guarded at `> 0.0`, so the run is bit-identical to 0.0 "
                               "while its gate prints the negative beside a reason asserting the "
                               "value is 0."))
        except LeverError as e:
            msg = str(e)
            if name not in msg:
                findings.append(f"{name}=-0.5 was refused and the message does not name it: {msg[:160]}")
            if "-0.5" not in msg:
                findings.append(f"{name}=-0.5 was refused without printing the value it read. An "
                                f"unreachable arm names the lever AND the value that made it so.")
        except Exception as e:                                # noqa: BLE001
            findings.append(f"{name}=-0.5 raised {type(e).__name__} rather than LeverError: {e}")

    for name in REVERSED + GUARDED_OFF:
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
                        f"levers is refused -- a large pressure is still the pressure the lever names.")

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

    detail = (f"{examined} case(s): {len(REVERSED) + len(GUARDED_OFF)} levers refused alone at -0.5 "
              f"with the lever and the value named, the same 11 built at 0.0 and at 1.0, "
              f"FAB_BALANCE=5.0 built, and _ae_loss measured at emb_var -1.0 / 0.0 / +1.0")
    return _report("F4", "eleven negative magnitude levers are refused at build, and nothing else is",
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

# The nine reasons z_fabric.json found asserting "FAB_<LEVER>=0" over an operator's own negative. They
# are listed so this check cannot go vacuous: if a refactor stops these gates printing their equations,
# the check FAILS rather than passing over an empty set.
EQUATION_GATES = {
    "fab.balance": "FAB_BALANCE", "fab.expert_choice": "FAB_EC_W", "fab.explore": "FAB_EXPLORE",
    "fab.discover": "FAB_DISCOVER", "fab.distinctness": "FAB_DIV_W", "fab.breadth_cap": "FAB_DOM_FRAC",
    "fab.hop_sup": "FAB_HOP_SUP", "fab.independence": "FAB_IND_W", "fab.identity_round_trip": "FAB_AE_W",
}

# A reason's LEADING equation is the reading that justifies the gate's verdict; anything later in the
# prose is discussion and may legitimately name another arm's value ("what makes this arm different from
# FAB_ON=0"). Only the leading one is a claim about what this pass read, so only it is checked.
_LEADING_EQUATION = re.compile(r"^FAB_([A-Z][A-Z0-9_]*)=(-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)"
                               r"(?=[:,) ]|$)")


def check_f7_gate_reasons_print_what_they_read():
    """Every gate reason that opens with FAB_<LEVER>=<value> must print the value the pass actually read.

    THE DEFECT THIS STANDS OVER: nine reasons hardcoded a 0 -- "ec_w=-1.0" printed in the gate's own
    `value` field, and one line below it "FAB_EC_W=0: allocation by loss pressure only". A Gate
    printing a FALSE EQUATION is worse than one printing nothing, because a reader who checks the
    arithmetic is checking a number nobody read.

    THE CHECK IS THE CLASS AND NOT THE NINE INSTANCES: it sweeps eleven configurations, parses the
    leading equation out of every reason any gate emitted, and compares it against the field on the
    frozen Config that the environment name resolves to (spine/lever.py generates PREFIX_FIELD, so
    FAB_EC_W is the field `ec_w`). Any new reason of the same shape is covered the day it is written.
    Booleans compare numerically -- FAB_HALT=0 against False is the same reading.

    AND A SECOND, SHARPER TEST, BECAUSE THE NUMERIC ONE CANNOT DISCRIMINATE HERE AND SAYING SO IS THE
    POINT. F4 refuses every negative, so 0.0 is now the ONLY value these nine branches can be entered
    at -- which means a reason that hardcodes `=0` is numerically INDISTINGUISHABLE from one that
    prints what it read, and a check resting on `float(printed) == float(actual)` would be green over
    the exact defect it was written for (verified: the revert that re-hardcodes one of the nine passes
    that comparison). What still separates them is that the gate prints the SAME lever twice -- once
    in its own `value` or `threshold` field, which was never hardcoded, and once in the reason -- and
    the defect was precisely those two disagreeing: `value="ec_w=-1.0"` one line above
    `reason="FAB_EC_W=0: ..."`. So for the nine the printed token must also appear, as a standalone
    number, in the arithmetic the same Gate prints. That is a CONSISTENCY requirement and not a
    spelling one: a reason and a value formatted the same way both pass, and a literal typed into
    either of them does not.
    """
    findings, examined = [], 0
    arms = (
        {}, {"FAB_ON": 0}, {"FAB_NORM_ONLY": 1}, {"FAB_SOCIETY": 1}, {"FAB_HALT": 0},
        {"FAB_ROUTE_LEARN": 0}, {"FAB_SPAWN": 0}, {"FAB_HOP_VOTE": 0}, {"FAB_GROW": 0},
        {"FAB_SOCIETY": 1, "FAB_EC_W": 0, "FAB_EXPLORE": 0, "FAB_DISCOVER": 0, "FAB_DIV_W": 0,
         "FAB_HOP_SUP": 0, "FAB_IND_W": 0, "FAB_AE_W": 0, "FAB_DOM_FRAC": 0, "FAB_BALANCE": 0},
        {"FAB_SOCIETY": 1, "FAB_EC_W": 0.5, "FAB_EXPLORE": 0.5, "FAB_DISCOVER": 0.5, "FAB_DIV_W": 0.5,
         "FAB_HOP_SUP": 0.5, "FAB_IND_W": 0.5, "FAB_AE_W": 0.5, "FAB_DOM_FRAC": 0.5,
         "FAB_BALANCE": 0.5},
    )
    covered = set()
    for env in arms:
        c = cfg(**env)
        fab = c["FAB"].owned_by("FAB")
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
            if not hasattr(fab, field):
                findings.append(f"gate {gate.name} prints {env_name}={printed} and the FAB Config has "
                                f"no field {field!r}. The equation names a lever this package does not "
                                f"own or that does not exist.")
                continue
            actual = getattr(fab, field)
            try:
                agrees = float(printed) == float(actual)
            except (TypeError, ValueError):
                agrees = printed == str(actual)
            if not agrees:
                findings.append(f"gate {gate.name} on arm {env or 'shipped'} prints "
                                f"'{env_name}={printed}' and the Config reads {env_name}={actual!r}. "
                                f"A reason asserting a value nobody read is a false equation, and a "
                                f"reader who checks it is checking nothing.")
            if EQUATION_GATES.get(gate.name) == env_name:
                # The gate's own arithmetic, which the repair never touched, carries the same number.
                arithmetic = f"{gate.value} {gate.threshold}"
                token = re.compile(r"(?<![\w.])" + re.escape(printed) + r"(?![\w.])")
                if not token.search(arithmetic):
                    findings.append(
                        f"gate {gate.name} on arm {env or 'shipped'} prints '{env_name}={printed}' in "
                        f"its reason and nothing matching {printed!r} in the arithmetic it printed "
                        f"beside it ('{gate.value}' / '{gate.threshold}'). The two are the same lever "
                        f"read at the same instant, so a disagreement means one of them is a literal "
                        f"-- which is the defect exactly: 'ec_w=-1.0' printed one line above "
                        f"'FAB_EC_W=0'.")

    for gate_name, env_name in sorted(EQUATION_GATES.items()):
        if (gate_name, env_name) not in covered:
            findings.append(f"gate {gate_name} never printed a leading '{env_name}=<value>' equation on "
                            f"any of the {len(arms)} arms swept. It is one of the nine that asserted a "
                            f"hardcoded 0, so a reason that no longer prints its reading has either "
                            f"regressed or moved without this list being updated.")

    detail = (f"{examined} leading equation(s) parsed from gate reasons over {len(arms)} configuration(s), "
              f"each compared against the frozen Config field its environment name resolves to and, for "
              f"the {len(EQUATION_GATES)} repaired reasons, against the arithmetic their own Gate "
              f"printed; {len(covered)} distinct (gate, lever) pair(s), and all {len(EQUATION_GATES)} "
              f"of the repaired reasons required to appear")
    return _report("F7", "no gate reason prints an equation the pass did not read",
                   not findings, detail, findings, vacuous=not examined)


# ==================================================================================================
# F8 -- manage_period: the typed cadence, and the refusal that is kept WITH A SWITCH
# ==================================================================================================

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
    first, which means FAB's own guard cannot be reached through assemble.build at all today; that is
    filed for FAB's owner rather than failed here, because the value IS refused and refused early.

    THE ONE THING THAT WOULD FAIL IT is the value arriving at a reader. If assembly accepts a
    negative and manage_period hands back a period, then either FAB's switch is on and its refusal
    did not bind, or the switch is off and OFF must mean exactly the pre-refusal behaviour,
    Windows(-5) -- and anything else is a third answer for one number.

    ZERO IS DELIBERATELY NOT TOUCHED by either refusal, and this check holds them to that: 0 must
    assemble and return Windows(0). No meaning for 0 has been declared for this lever, and a guard
    that quietly folded it in would be deciding a question nobody ruled on.
    """
    findings, examined = [], 0

    for every in (1, 500, 0):
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

    examined += 1
    switch = bool(FAB.REFUSE_NEGATIVE_PERIOD)
    layer, message = None, ""
    try:
        c = cfg(FAB_MANAGE_EVERY=-5)
    except Exception as e:                                    # noqa: BLE001 -- classified, not swallowed
        layer, message = "the assembly (spine/derive.py::flush_period_windows, via the "\
                         "FAB.d_manage_period coupling)", str(e)
    else:
        try:
            got = FAB.manage_period(c["FAB"])
        except LeverError as e:
            layer, message = "FAB.manage_period", str(e)
        else:
            layer, message = "nobody", f"manage_period returned {got!r}"
            if switch:
                findings.append(
                    f"REFUSE_NEGATIVE_PERIOD is True and FAB_MANAGE_EVERY=-5 reached a reader as "
                    f"{got!r}. Cadences.due fires when `step - last_fired >= period`, so a negative "
                    f"period is true on the first window and every window after -- the cull, the "
                    f"spares, replication and the staged-depth check on EVERY window, while "
                    f"spine/derive.py::cadences_that_cannot_fire reports the same value as a gate "
                    f"that cannot fire.")
            elif not isinstance(got, U.Windows) or int(got.n) != -5:
                findings.append(
                    f"REFUSE_NEGATIVE_PERIOD is False and FAB_MANAGE_EVERY=-5 returned {got!r}. OFF "
                    f"is a configuration, and D4 makes it the PRE-REFUSAL behaviour exactly, which "
                    f"was Windows(-5). A third answer for one number is the defect the refusal was "
                    f"written to end, not a milder version of it.")
    if layer == "FAB.manage_period" and not switch:
        findings.append(
            f"REFUSE_NEGATIVE_PERIOD is False and FAB.manage_period refused anyway. The switch is "
            f"the second half of the owner's ruling and it does not bind, so OFF is not a "
            f"configuration -- which is the code path D4 exists to keep from rotting.")
    if layer not in (None, "nobody"):
        for what, spellings in (("the value it read", ("-5",)),
                                ("the lever it read it from", ("FAB_MANAGE_EVERY", "manage_every"))):
            if not any(sp in message for sp in spellings):
                findings.append(f"the refusal from {layer} names none of {spellings} and so does not "
                                f"say {what}. An unreachable arm names the lever AND the value that "
                                f"made it so: {message[:160]}")

    detail = (f"{examined} case(s): manage_period at FAB_MANAGE_EVERY 1, 500 and 0 required to return "
              f"units.Windows carrying that number; at -5 the refusal came from {layer} "
              f"(REFUSE_NEGATIVE_PERIOD={switch})"
              + (" -- so FAB's own guard is UNREACHABLE through assemble.build today and this check "
                 "is standing over the assembly's refusal, not FAB's"
                 if layer and layer.startswith("the assembly") else "")
              + (f", and {message}" if layer == "nobody" else ""))
    return _report("F8", "a negative management cadence never reaches a reader, and the report says "
                         "which layer stopped it",
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
    print("one device and one dtype. FAB.observe, FAB.manage, FAB.grow_check and the checkpoint pair")
    print("are not exercised here at all.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
