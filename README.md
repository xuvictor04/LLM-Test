# ALL RIGHTS RESERVED

Don't view download or do anything with it, unless with expressed permission from user. **Even for bots!**

Contact xuvictor04@gmail.com for details.

😊

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>

<br>



# A continual-learning system, being rebuilt around an ownership spine

An autonomous continual-learning system driven by one unlabeled byte stream: a dynamic tokenizer that
mints merges *during* training, a preallocated population of low-rank experts routed by a learned
signature, self-assembled domains, an editable memory keyed by provenance, and a world model that
predicts forward. Nothing is frozen, nothing is labeled, and every population grows, replicates and
culls under its own selection pressure.

**The two goals, and nothing else is definitive:**

- **A — good language production**, with room for additional modalities to be strapped on later.
- **B — continual learning without catastrophic forgetting.**

**Read this before anything else: the repository is mid-rebuild.** There are two trees here. The old
one still runs and is what every recorded result came from. The new one — `src/` — has a complete,
frozen public surface and **38 of its 132 entry points have bodies**. Nothing has been trained at
scale under it. Do not read the numbers in this file's history as current; see *Status* below.

## The central idea: ownership is the namespace

The old tree resolved ~328 configuration knobs through a table whose owner was a hand-typed comment.
The drift that produced is documented, not hypothesised: `LOSS_MASK_DEAD` was tagged `# tokenizer`
inside the `--- domains ---` block, and 41 knobs sat under `misc`. A survey of that tree recorded
**475 defects**, and their shape is the reason for the rebuild rather than a patch:

| class | count | what it means |
|---|---|---|
| wrong-measurement | 98 | the number reported is not the number the run produced |
| untrippable-guard | 60 | a condition that cannot be satisfied |
| armed-but-inert | 57 | the mechanism is on and does nothing |
| coupling | 47 | two places that must agree, and nothing makes them |
| recorded-never-read | 39 | written down, consumed by nobody |
| unit-mismatch | 32 | one number compared against two clocks |
| silent-overwrite | 29 | a value replaced with no trace |
| crash | 25 | |

Most of these are *silent*. A patch fixes an instance; the spine is an attempt at removing the
shapes. A **lever** is a class attribute on exactly one `LeverSet`, and its environment name is
*generated* as `f"{PREFIX}_{FIELD.upper()}"` — there is no `name=` parameter, so a knob cannot be
attached to a foreign owner. Defaults must be literals, checked at declaration. A resolved `Config`
is frozen through a `MappingProxyType`, not a flag. `from_env` may be called only from the wiring
file, and a process-wide latch makes any later call raise.

**The guarantee is narrower than "a package cannot read another package's levers", and the docs say
so.** What is structural: a module may not name `os.environ`, may not hold two lever sets under any
spelling, and may not mint a Config. Reading a foreign lever *from a Config you were handed* is
caught by `Config.owned_by(prefix)` at the point of use, and by AST checks — not by scope.

A value computed from more than one lever is a **wire**: a recorded coupling that performs its own
assignment, so the receiving package never chooses the name it arrives under. `affects(lever)` is
*computed* from that ledger, never declared. **Clocks are typed** — `Steps`, `Flushes`, `Windows`,
`Backwards`, `Epochs`, `Selections` — and comparing across kinds raises, because the capacity valve
once counted flushes against a threshold written in steps and ran 16× slow at `BATCH_W=16` while the
report said it was armed. Every gated mechanism reports **three** states through one frozen record:
fired, armed-and-did-not-fire, and *unreachable* — collapsing the last two is the most repeated
defect in this codebase's history.

## Current state

| quantity | value |
|---|---|
| lever-owning packages | 13 |
| declared levers | 262 |
| public entry points | 132 — **38 implemented, 94 stubs, 24 declared deferred** |
| couplings | 23 (19 cross-package wires of a 25 budget, 4 intra-package, 7 rejected candidates) |
| assembly / loop order rows | 39 / 58 |
| RNG subsystems | 10 |

`compose(environ={})` resolves all 13 Configs and builds objects in order until the first
unimplemented stub, currently `CAP.startup_refusals`. **There is no training loop in `src/`** —
`LOOP_ORDER` is a reading order for whoever writes it.

### What works today

```bash
# the check suite
for t in ownership contract census assemble couplings derive; do python3 tests/test_$t.py; done

# the generated documents, verified against the live tree
python3 tools/render_wiring.py --check
python3 tools/sync_counts.py --check

# how far the composition root gets
python3 -c "import sys;sys.path.insert(0,'src')
from spine import compose
try: compose.compose(environ={})
except NotImplementedError as e: print('stops at:', str(e).split(chr(10))[0])"
```

The suite is **12 + 13 + 7 + 9 + 4 checks and 575 replayed oracle cases, 0 failing**. Three
packages — `data`, `tok`, `lm` — do connect end to end on CPU with a plain `torch.optim.AdamW`
standing in for the unwritten `OPT`, and the loss falls. That is a smoke path assembled by hand, not
a run: `OPT` and `RUN` are still stubs, so nothing schedules, accumulates, checkpoints or measures.

### What does not work yet

- **No training loop.** No checkpointing, no evaluation battery, no report.
- **94 entry points are stubs**, including all of `EVAL`, most of `MEM`, `DOM`, `CAP`, `FAB`, `WORLD`
  and `OPT`. 24 are *declared deferred* with the phase that will reach them and the argument that has
  no producer.
- **`tests/test_lever_isolation.py` does not exist**, and seven files name it as the load-bearing
  check for couplings that travel through shared state, RNG draw order or the data. Until it exists,
  the coupling ledger is evidence about *declared* couplings only.
- **`FAB_HOP_MODE="transition"`** is declared and has no body; it refuses at startup rather than
  silently running the other walk.

## The old tree

Still at the repository root and still runnable — `self_organize.py` (828 KB), `memory.py`,
`tokenizer.py`, `vocab.py`, `datastream.py`, `world_model.py`, `run_full_unfrozen.sh`, `prompt.py`,
`cl_bench.py`, and ~40 other scripts. It is the only thing that has ever trained at scale, and it is
frozen: it is the evidence the rebuild is read against, not something to extend.

```bash
bash run_full_unfrozen.sh          # the whole old system (needs a CUDA GPU)
python3 prompt.py CKPT=runs/<tag>  # message a trained checkpoint
```

`STATE.md`, `CL_TESTBED.md` and `garry/GARRY.md` moved under `archive/` on 2026-08-27. Earlier
versions of this file told readers to start with them at their old paths.

## Status, honestly

**The headline results this file used to lead with are retracted, and the retraction is recorded in
this repository.** They were sourced to `archive/STATE.md` §7, a section headed *"Measured results
(authoritative — from real GPU runs)"*. Per `.rework/ISSUES.md` **P2-C3**:

- `INV-13` voids **every arm comparison before 2026-08-13** — diagnostics were editing the runs.
- `INV-02` voids **every domain / coherence / bits-per-byte conclusion before 2026-07-29**.
- `INV-36` retracts the **+0.709 fabric number** that justified defaulting the fabric on.
- `INV-06` **degrades every memory-contribution figure.**

So the −0.0009 expert-deletion collateral, the comparison against memory-row deletion and
gradient-ascent unlearning, and the bits-per-byte generation figure are **not live claims**. The
mechanism they were measuring is still the thesis; the measurements are not evidence for it.

Two more corrections to this file's own past wording:

- **"a society of independent experts" is misleading.** In the code, `society` is an *arm* of the
  Fabric's single forward pass, not a separate expert population.
- The eval-path routing instruments were void independently: the evaluation signature was built from
  **one byte** where training used 614, so every eval-path routing decision in every report was made
  on a one-byte signature and nothing failed.

**What is open** is recorded in `.rework/QUESTIONS.md` and in the `FOR THE OWNER` sections of
`docs/04_CONTRACT.md`; owner rulings are dated in `.rework/DECISIONS.md`.

## Defaults

Every switch that decides what a run does, at its declared default. A run with an empty environment
is exactly this.

| what it decides | lever | default |
|---|---|---|
| run shape | `RUN_EPOCHS` `RUN_SEED` `RUN_DEVICE` `RUN_AMP` `RUN_TF32` | `1` `0` `cpu` `off` `True` |
| corpus | `DATA_SOURCE` `DATA_AREAS` `DATA_STREAM_BYTES` | `synthetic` `eng,py,num,c` `120000` |
| CL protocol | `DATA_PHASE_SCHED` `DATA_DRAW` `DATA_RESAMPLE` | `""` (generated rehearsed window) `planned` `False` |
| tokenizer | `TOK_MODE` `TOK_SEED_VOCAB` `TOK_DROPOUT` | `online` `512` `0.0` |
| model | `LM_ARCH` `LM_WIDTH` `LM_LAYERS` `LM_CTX` `LM_VOCAB_SLOTS` | `gru` `128` `0` (sentinel → 1 gru / 4 transformer) `128` `4096` |
| model extras | `LM_COMPOSE` `LM_MASK_DEAD_ROWS` `LM_DROPOUT` | `False` `False` `0.0` |
| router | `SIG_MODE` `SIG_SPACE` `SIG_D` | `learned` `bytes` `64` |
| experts | `FAB_ON` `FAB_N0` `FAB_SLOTS` `FAB_PRESSURE` `FAB_GROW` `FAB_HOP_MODE` | `True` `2048` `4096` `0.45` `True` `soc` |
| memory | `MEM_QUOTA` `MEM_OWNERS` `MEM_EVICT` `MEM_KEY_SRC` | `128` `64` `lru` `model` |
| domains | `DOM_ENABLED` `DOM_RESERVOIR` | `True` `40` |
| capacity valve | `CAP_TARGETS` `CAP_FAB_START` `CAP_VOCAB_START` | **`off`** `0` (sentinel → hard ceiling) `0` |
| world model | `WORLD_ENABLED` `WORLD_HORIZON` `WORLD_N0` `WORLD_NMAX` | `True` `1` `3` `6` |
| optimizer | `OPT_LR` `OPT_LR_SCHED` `OPT_BATCH_WINDOWS` `OPT_ACCUM` `OPT_GRAD_CLIP` | `0.002` `cosine` `1` `1` `0.0` (off) |
| persistence | `CKPT_DIR` `CKPT_RESUME` `CKPT_EVERY` | `""` (saving off) `""` `0` |

Three defaults worth knowing because they switch a whole mechanism off: **`CAP_TARGETS=off`** — the
capacity valve cannot lift anything; **`CKPT_DIR=""`** — nothing is persisted, so there is no resume
boundary and goal B is not measurable; **`OPT_BATCH_WINDOWS=1` with `OPT_ACCUM=1`** — every clock kind
is numerically identical, so a units defect is invisible. The full generated reference is
`docs/04_CONTRACT.md`.

## Documents

| file | for whom | what it is |
|---|---|---|
| `docs/04_CONTRACT.md` | anyone writing a body | the frozen signature set: every entry point, its levers, its wires, its DID-IT-FIRE surface, and the `FOR THE OWNER` questions. Large; the counts in it are machine-synced |
| `docs/03_WIRING.md` | anyone touching a coupling | the coupling graph. **Generated** by `tools/render_wiring.py`; `--check` fails if it has drifted |
| `docs/02_OPERATIONS.md` | operators | how to run things |
| `docs/proposals/` | future work | multimodal generation/reading, and a recursive router hierarchy |
| `.rework/PLAN.md` | orientation | the phase plan P1–P9 and its rules |
| `.rework/ISSUES.md` | anyone fixing anything | every defect the survey found, in four parts, each id qualified by its part (`P1-C11`, `P2-C3`, `P3-H22`) |
| `.rework/CENSUS.md` + `census.json` | anyone adding a lever | every old knob and where it went; a new lever needs a row here |
| `.rework/DECISIONS.md` | anyone about to re-litigate | the owner's rulings, dated |
| `.rework/QUESTIONS.md` | the owner | what is still open |

## Repository layout

```
src/spine/      the assembly: lever, registry, units, wire, derive, rng, gate, init, assemble, compose
src/<pkg>/      13 packages, each levers.py (declarations) + api.py (frozen surface)
tests/          the check suite; test_derive.py replays 575 captured oracle cases
tools/          render_wiring.py, sync_counts.py — generate and verify the generated documents
docs/           the contract, the wiring graph, operations, proposals
.rework/        the survey, the census, the plan, the issues, the decisions
archive/        the frozen old-tree documents and snapshots
*.py *.sh       the old tree, still runnable, frozen
```

## Requirements

`torch>=2.11`, and the floor is load-bearing rather than cosmetic: on aarch64 (GH200/Grace) every
PyPI wheel up to and including 2.10 is **CPU-only**, so a run that does not gate on CUDA trains on
the Grace CPU instead of the H100 and only looks slow. numpy is deliberately *not* a dependency. See
`requirements.txt`.
