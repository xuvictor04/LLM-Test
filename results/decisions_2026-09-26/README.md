# Decision register workflow, 2026-09-26

This is the evidence behind `docs/proposals/05_DECISIONS.md`. It answers the owner's request of
2026-09-26: rule the open decisions under the fundamentals, A (a universal, or universal-capable,
model) and B (it keeps learning after training without risking too much), with B first. Document
the decisions and their conflicts, and let testing decide.

No training runs were made for it and no tracked file was edited while it ran. The readings are:
- model-free replays of the tree's own functions;
- short CPU composes at small stream sizes;
- the arithmetic behind the stated numbers.

Read every number as a signal, not a result. The register cites these files by paths relative to
this folder, for example `verify/emp3/acts.py`.

## Contents

**`workflow_result.json`**: the ruling workflow's whole output, under these keys:
- `inv`: the inventory of 103 open, pending, superseded and revisable decisions;
- `rulings`: the four rule roles;
- `gaps`: the gap finder;
- `conflicts`: C01-C45, the priority-order draft and 28 ruling changes;
- `lit`: the literature digest;
- `critic`: the critic's review;
- `doc`: the merging agent's report on the first full draft (critic's fixes applied, before the
  verification rounds); the draft itself is superseded by the committed register.

**Each role's scripts and logs**, in folders named after the role:
- `inv/`
- `rule_media/`
- `rule_pending_measurements/`
- `rule_self_regulation/`
- `rule_tree_and_training/`
- `gap/`
- `conflicts/`
- `critic/`
- `lit/`

**`verify_result.json`**: the verification loop's rounds 0-2. Each round had three independent
checkers, covering the empirical claims, the numbers and cites, and consistency. After each round a
fixer pass applied the findings.

**`verify/`**:
- `fixlog.md`: every fix, by round. It also records round 3, the last fixer pass, and round 4, the
  final adversarial check on round 3's diff, whose findings were applied by hand.
- `emp/`, `emp2/`, `emp3/`: the checkers' empirical re-runs, including:
  - the phase each run reaches at HEAD and at `d97779d`;
  - whether the synthetic text varies with the seed;
  - the continuation learning rate for finished parents (`emp3/k0_epoch_child.py`);
  - bytes per window across tokenizer acts.
- `numbers/`, `numbers3/`: lever, count and arithmetic checks, including E2's splice cost.
- `final/`: the round-4 checker's scripts and its diff of round 3.
- `check_tables.py`: the table-shape check.
- `patch_round2*.py`: the round-2 fixer's patches.

**`s0b/`**: a CPU OPERATION check of the mid-epoch act. It ran k0 against `TOK_RETOK_EVERY` 1000
over one whole 760,000-byte epoch, at seeds 0 and 1, with `OMP_NUM_THREADS=1` (see `preq_eq.py`).
What it establishes: the act fires (3 acts per k1000 run), both arms finish with finite losses, and
the prequential bytes are accounted over the whole epoch. The recorded prequential bits/byte
(k0 2.6892 / 2.7880, k1000 2.6895 / 2.7958) are **not** an efficacy reading: by the owner's rule of
2026-09-26, CPU checks test operation only, and whether live re-segmentation works is decided by the
GPU `EXP=retok` fleet.

**`rulings/`**: the manager's rulings on the 20 decisions first queued for the owner (O1-O20) and the
D-1..D-10 confirmation, made under the owner's delegation of 2026-09-26. There are three versions:
- `drafts_and_checks.json`: the first drafts and two adversarial checks.
- `revised_detailed.json`: the detailed revision, with per-ruling statistical rules. It was not
  committed to the register: the check rounds kept finding contradictions between the rulings, and
  the owner had said the bulk was impractical.
- `lean.json`: the lean form the register carries (§3.3 and Appendix D). It keeps one statistical
  rule for every GPU comparison against ε and leaves seeds and caps to each test's own
  pre-registration.

**`revise/`**: the scripts the revision ran: power and sample-size arithmetic, O14's confirmation
arithmetic, and the capacity and refill arithmetic behind O16 to D-CONFIRM (`o16_dc/`).

## Left out

Two copies of the `d97779d` source tree, used to re-run the 2026-09-24 fleet's composition, are not
archived. To reproduce those comparisons, check out `d97779d`.
