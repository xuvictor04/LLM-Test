# Proposal 02 — Router recursion

**Status: design only.** Nothing in `src/` implements this. It gets its own branch when it starts.

## The owner's words, verbatim

> Something we could add to the router is a sense of recursiveness - where there will be multiple
> layers of routers stacked on top of each other. Each sibling router are to be independent. Lowest
> level routers touch experts. When routers have nothing below, they die. The only catch to a normal
> router is back routing, back to their parent. When an expert finishes, it should be sent up the
> chain of command - not necessarily to the top, but passed to its parent router, who decides later.

Preserved exactly because the design below is an interpretation of it, and where the two differ the
quotation wins. Six claims are being made:

1. routers stack, in layers;
2. **siblings are independent**;
3. only the lowest routers touch experts;
4. **a router with nothing below it dies**;
5. a router may route **back to its parent** — the one departure from ordinary routing;
6. a finished expert's result goes **to its parent**, not to the top, and **the parent decides later**.

## What exists today

The fabric is **flat**. `FAB.forward(fab, pop, *, h, signature, novelty, head, targets,
step_windows, domain_id, live_domains, training, hold_out)` routes one hidden state to experts in a
single population of `FAB.slots` (4096) preallocated slots, `FAB.n0` (2048) of them alive at the
start. There is no tree, and no node between the router and an expert.

There is already a **depth** mechanism, and reading it before designing on top of it is not optional:

- `FAB.hop_mode` defaults to `'soc'` — *"re-routes from scratch each hop"*. `FAB.hops` (4) is the
  budget and effective depth is `min(depth0-stage, hops, 2 + n_live//2)`.
- **The alternative arm is armed and inert** (`fabric/levers.py:186`, ISSUES P1-M27): the transition
  branch is the only thing that fills `fab._hops`, so under the shipped `hop_mode="soc"` any hop
  value above zero adds nothing. Whether to port it at all is **Q-FAB-1**, still open.
- `FAB.ponder` (0.01) charges routed depth *"so the chain does not take hops it does not need"* —
  and `ponder_warm` is 8000 windows, longer than a default run can reach (ISSUES P1-C11), so on today's
  defaults the charge never arms.

**Hops are not layers.** A hop re-routes within *one* population; the proposal stacks *distinct*
routers with their own populations beneath them. The relationship between the two is the first
question below, and it is the one most likely to be answered by accident.

Two more facts the design has to live with:

- **The router's only input is the signature.** `SIG.encode(sig, st, windows)` returns
  `SIG.d`-dimensional vectors (64), in `SIG.space` (`'bytes'`), from a learned encoder
  (`SIG.mode='learned'`). `sig/api.py:8` states the stake: a collapsed encoder routes every window
  to the same experts.
- **`ISSUES P1-C3` voids the counterfactual on the shipped path.** `fab.contrib` — the marginal-
  contribution signal that gates both cull-spare rules and picks replication parents — is measured
  by re-walking with `ban1` set, and the soc-loop never applies `ban1` to any logit. Every expert
  gets the same number. **So "measurements showed the depth arm did not help" is a statement about
  the measurement**, and any hierarchy that inherits `contrib` inherits a signal carrying no
  information about which expert matters.

## What the architecture forces

### Sibling independence is already a checkable property, and the machinery exists

*"Each sibling router are to be independent"* is, structurally, the **L3 lever-isolation property one
level down**: flip something owned by sibling A, and nothing owned by sibling B may move beyond the
measured floor. `tests/test_determinism.py` already establishes that floor and
`tests/test_lever_isolation.py` (P4) is the sweep.

Extending it to runtime siblings is a real change, not a free one — the existing sweep flips a
**lever**, which is frozen at build, and two sibling routers are **runtime objects** created by
growth. What would have to exist is a per-node integer fingerprint of the kind graft G3 already
specifies for packages: routing histogram, `n_live`, centroid EMAs, RNG fingerprint. Two siblings
are independent when perturbing one moves none of the other's.

**That test is the whole proposal's falsifier**, and it should be written before the mechanism.
Without it "siblings are independent" is an intention, and this repository's history is that
intentions of exactly that shape (`FAB_BALANCE` keeping every expert fed; `contrib` distinguishing
experts) were reported as working for entire investigations while being structurally inert.

### Back-routing is a cycle in a system whose checks read forwards

This is the hardest constraint and it is worth being precise about, because it is not a style
objection.

`ASSEMBLY_ORDER` and `LOOP_ORDER` are **data**, and K10 reads them **forwards**: an argument is
produced by an *earlier* row. `compose.py` already carries exactly three values that cross a boundary
those tables cannot express, and they live on `System.__slots__` with the row that consumes each one
naming it — `due` (asked per window, acted on per flush), `novelty` (the previous flush's mean
surprise), `token_seen` (written every window, read at the flush).

Back-routing and "the parent decides later" would make a **fourth and much larger** one: not a
scalar carried across a stage boundary, but a **result buffered at a node until that node decides**.
Three consequences follow, and none is optional:

- **The buffer is state, so it goes in the checkpoint.** Which means it enters the geometry manifest
  question (`Q-CKPT-2`, unresolved) — a resumed run with a partly-drained buffer is either restored
  faithfully or it is not, and a resume is what `ckpt/api.py:3-6` calls *the experiment* for goal B.
- **"Later" is a clock, and it needs a kind.** `Windows`, `Flushes` and `Steps` are distinct and
  comparing them raises. Whether a parent decides on the next window, the next flush, or after a
  fixed budget of pending results is a units decision, and at the shipped `OPT.batch_windows=1,
  accum=1` **all three are numerically identical**, so a wrong choice is invisible until the batch
  width moves (ISSUES P1-H52, which amended P3's exit criterion for exactly this reason).
- **The decision to defer is itself a gate** and needs its DID IT FIRE surface: how many results were
  buffered, how many were acted on, how many are still pending at the end of the run. A parent that
  never decides looks identical to a parent with nothing to decide.

### A router that dies is a cull, and the fabric already has one

*"When routers have nothing below, they die"* is a cull rule at a new level. The existing gate is
`derive.cull_gate_open(n_live, cap, pressure)` — `not (n_live <= 2 or n_live/cap < pressure)` —
whose failure mode is on record: `n0=2048` against `slots=4096` parks occupancy at 0.50, and at the
old `pressure=0.75` the utilisation cull, the utilisation spare and `FAB_RESCUE` were **all
unreachable for an entire investigation while the report showed them switched on**. The default is
0.45 today *because of that*.

An empty-router cull is a much simpler predicate — `children == 0` — which is a point in its favour
and also its danger: it is trivially satisfiable and therefore trivially *over*-satisfiable. A
router whose last child was culled dies in the same pass, and its parent may then be empty, and so
on up. **Whether death cascades in one pass or one level per pass is a real decision** with a
measurable difference, and it wants the same treatment `FAB.grace` gets — a newborn is protected for
a period before it can be judged.

### Ownership: one package or two

The hierarchy is either an extension of `FAB` or a new package with its own `PREFIX`. This is not
cosmetic — it decides where every new lever's environment name comes from, since names are
**generated** as `PREFIX_FIELD`.

- **Inside FAB** costs nothing in wires: depth, branching and the death rule read `FAB.slots`,
  `FAB.pressure` and `FAB.grace` directly, as one package's own levers. FAB already has 82 levers,
  the largest by a wide margin, and this would add perhaps a dozen.
- **A new package** (`ROUTE`?) makes the tree's own parameters separately settable and separately
  reportable, and forces every value it shares with FAB through a declared wire — which is the
  architecture working as intended, and also a coupling budget cost (`WIRE_BUDGET` is 25; 19 are
  spent).

D1 rules that the fabric stays. Neither option violates that. **The question is which one makes the
tree's own behaviour separable from the population's in the report**, because "the hierarchy helped"
and "the population helped" have to be distinguishable claims.

## Questions this raises

Numbered for the branch. None is answered here.

| # | Question | Why it matters |
|---|---|---|
| R1 | Are **hops** and **layers** the same mechanism? Does a hierarchy replace `hop_mode`/`hops`, subsume it, or coexist? | If they coexist, a forward pass has two independent notions of depth and `FAB.ponder` charges only one of them. Bears on **Q-FAB-1**. |
| R2 | Is back-routing (5) the same mechanism as passing a finished result up (6), seen from the two ends? | If yes, one mechanism. If no, a router has two distinct upward paths and each needs its own counter. |
| R3 | What does the parent **decide**, and on what clock? | "Decides later" is a gate with no stated condition. The clock kind is load-bearing and invisible at the shipped defaults. |
| R4 | Does a result go up **once** or can it be passed up repeatedly toward the top? | *"not necessarily to the top"* rules out mandatory ascent but does not rule out repeated ascent. Termination differs. |
| R5 | Death: cascade in one pass, or one level per pass? Is there a `grace` for a newborn router? | Trivially satisfiable predicates over-fire. The fabric's grace exists for the same reason. |
| R6 | New package or FAB extension? | Decides every environment name, and whether the tree's contribution is separately reportable. |
| R7 | Does each router get its **own RNG stream**? | `rng.issued()` is the register; two siblings drawing from one stream are correlated, which would defeat R-independence for a reason that is not about routing at all. |
| R8 | How does the sibling-independence sweep get an oracle? | `affects(L)` is **computed** from the wire ledger (graft G1) and is about *levers*. Runtime siblings need an equivalent that is also computed and not hand-declared. |
| R9 | Does a router route on the **same signature** as its children, or on something coarser? | If every level sees the same 64-d vector, the levels are not doing different work. This is the question that connects to Proposal 01. |
| R10 | What is the depth limit and what enforces it? | Unbounded recursion with a growth rule is a capacity question; the capacity valve (`CAP`) is the existing mechanism and it is currently **unreachable at the defaults** (C11). |
| R11 | Does `contrib` mean anything at a node? | ISSUES P1-C3 says the leave-one-out is void on the shipped path. A hierarchy built on a signal carrying no information inherits that, and the spare and replication rules read it. |

## What to build first

**The falsifier before the mechanism.** In order:

1. **The per-node fingerprint** and the sibling-independence sweep, against the `test_determinism`
   noise floor — the one thing that can show this working or not.
2. **A two-level tree on synthetic data with a known partition**, where the right answer is known in
   advance and "the hierarchy found it" is checkable rather than plausible.
3. **The death rule**, with its counter, before growth — so an over-firing cull is visible on a tree
   that is being built rather than one that has settled.
4. **Back-routing last**, because it is the cycle, and everything above is testable without it.

The temptation will be to build the tree first and the test after. This repository has 60 recorded
guards that could not fire and 57 mechanisms that were on and never ran, and every one of them was
built in that order.
