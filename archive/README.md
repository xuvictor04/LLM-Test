# archive/ — what in this tree is HISTORY, and must not be read as current

Everything under `archive/` is a frozen record. It is kept deliberately — this project's whole method is
that a record of what was believed, and when, is worth more than a tidy tree — but every item here holds
code or prose that was true once and is not true now. Grepping the repository without knowing that is
how the two most expensive documentation errors here happened (below). For what the system does now,
read `src/` (run by `run.py`), `docs/04_CONTRACT.md` and `docs/05_DEFAULTS.md`; the root `README.md` maps
the whole tree.

This file says what each item was, why it is kept, how to run the old tree, and where every moved path
went. It was the root's `ARCHIVE.md` until 2026-09-28 and moved here with `git mv`, so
`git log --follow archive/README.md` keeps its history. `garry/`, `legacy/`, `handoff/`, `docs/`,
`STATE.md` and `CL_TESTBED.md` moved here from the root on 2026-08-27, so that a repository-wide grep does
not return them beside live code; the old tree followed on 2026-09-28, and `agent-transcripts/` was
committed here directly. Nothing in `src/`, `tests/` or `tools/`, nor `run.py` or `gpu_world.sh`,
imports or executes any of it; the old tree runs when someone runs it (below), and
`.rework/capture_oracle.py`, the P0 capture of the oracle `tests/test_derive.py` replays, reads
`old-tree/self_organize.py` if it is ever run again.

| path | what it was | why it is kept | frozen since |
|---|---|---|---|
| `old-tree/` | the old system, at the repository root until 2026-09-28: `self_organize.py` (9,859 lines; its `_SPEC` holds 328 knobs), the modules it imports by bare name (`memory.py`, `verification.py`, `world_model.py`, `datastream.py`, `tokenizer.py`), its harness (`longrun.sh`, `selftest.sh`, `rerun.sh`, `equiv.sh`, `preflight.sh`, ...), its tests (`*_test.py`, `harness_test.sh`, `notes_check.py`), probes, fetchers, and the run registry `runs.py` + `runs.csv`: 51 files, and a `data` link | the only system that has ever trained at scale: every recorded result was measured under it, and `src/`, `docs/` and `tests/` cite it by line (`self_organize.py:NNNN`), which a move that changes no byte keeps true | 2026-08-28 (D5 froze branch `rm-predict`; every file here but `notes_check.py` and `equiv.sh` is byte-identical to it) |
| `garry/` | a working snapshot of the whole system at milestone T33: a 957-line `self_organize.py`, against the old tree's 9,859 | the known-good reference its own `GARRY.md` promised; `src/memory/api.py` cites its `self_organize.py` by line | 2026-07 |
| `legacy/` | the pre-rewrite package, a different architecture with the same vocabulary | where the vocabulary came from; its `build_continual_data.py` wrote `data/continual/`, and `docs/04_CONTRACT.md` (Q-DATA-4) cites it | 2026-07 |
| `handoff/` | the 2026-07-21 handover folder: phase notes, decisions, open questions, design directions | what a fresh session was told on 2026-07-21; the notes corpus and `.rework/ISSUES.md` cite it | 2026-07-21 |
| `docs/` | `FILES.md` (a file-by-file map written from a read of the code) and `HANDOFF.md` (the pick-up guide beside it), the root's `docs/` of 2026-07-21 — not today's `docs/` | the same handover | 2026-07-21 |
| `agent-transcripts/` | the raw transcripts of the multi-agent workflows behind `.rework/`, `src/`, `tests/` and `docs/`; its `MANIFEST.md` lists them | the only copy: the container that ran them is ephemeral | as committed |
| `STATE.md` | a "living project ledger" whose own header calls its protocol **binding for the assistant** and instructs it to be updated every turn. Last updated 2026-08-15 and carrying `FAB_N0=3`. A stale file that tells the reader it is authoritative is the worst kind. | the headline results the root `README.md` retracts (ISSUES P2-C3) came from its §7, which the retraction cites | 2026-08-15 |
| `CL_TESTBED.md` | the continual-learning testbed description from the import | what `cl_bench.py` and `run_full_unfrozen.sh` were written to test | 2026-08-15 |

## The trap, concretely

`archive/garry/self_organize.py` still reads `_i("FAB_N0", 3)`. The default has been **2048** since
`6380519`/`25aba88` (2026-08-17), in the old tree's `_SPEC`, and `src/` declares the same 2048 for its
`FAB_N0` (`src/fabric/levers.py`). A repo-wide grep for `FAB_N0` returns all three, and the wrong one is in
a file that looks exactly like the right one.

That is not hypothetical: nine files in `notes/` stated `FAB_N0=3` as the current default a week after it
changed, and it was `00_INDEX`'s "five things to know before spending any GPU time" item #1. Separately,
`02_IDEAS` filed a built mechanism as NEVER IMPLEMENTED and its own correction records the cost — "it was read
during the 0.75 GB planning and used to tell the user the mechanism did not exist".

## Where to look instead

- **Defaults of the system that runs now:** `docs/05_DEFAULTS.md`, generated from the lever registry by
  `tools/render_defaults.py`; `tests/test_assemble.py`'s A10 fails if it drifts.
- **Defaults of the old tree:** `notes/CURRENT_DEFAULTS.md`, generated from `self_organize.py`'s `_SPEC`
  by `old-tree/notes_check.py` (in `selftest.sh`), which fails if that file drifts, if `README.md` or
  any `notes/*.md` states a default `_SPEC` contradicts without saying it is history, or if this file
  is missing.
- **Current behaviour:** `src/`, run by `run.py`; its surface is `docs/04_CONTRACT.md`.
- **What was true before:** everything in this directory, and the 2026-08 notes corpus in `notes/`
  (`notes/00_INDEX.md` first). Correct as records. Where one has since been overtaken, it carries a dated
  correction rather than an edit.

## Rules

1. Do not edit anything under `archive/`. `archive/garry/GARRY.md` said this already; it applies to all of it.
   The exceptions are recorded here, never made silently: this README, the label, which is updated
   whenever something is archived or moves; and the edits that let two old-tree files run from their new
   place, listed under *Running the old tree*. `notes_check.py` fails if `archive/` exists without this
   README, so the label cannot quietly go missing.
2. Do not cite them for what the system does now.
3. When a note is overtaken, append a dated correction. Do not rewrite the original — the record of a wrong
   belief is the most useful thing in the corpus, and this project has re-learned that twice.

## Running the old tree (`old-tree/`)

It runs from its own directory, with the commands it always had:

```bash
cd archive/old-tree                         # its data/ is a link to the root's data/
bash selftest.sh --quick                    # its own gate: 16 unit checks, no training (without --quick: + a CPU run and a resume)
mkdir -p runs && bash run_full_unfrozen.sh  # the whole old system (needs a CUDA GPU); runs/ here, gitignored
python3 prompt.py CKPT=runs/<tag>           # message a checkpoint it wrote here
bash longrun.sh <command>                   # the long-run harness; bash longrun.sh --help lists the commands
```

Three of its scripts find their own place and run from any directory: `bash archive/old-tree/preflight.sh`
(it moves to its own directory, as it always did), `python3 archive/old-tree/notes_check.py` and
`bash archive/old-tree/equiv.sh <ref> [ref2]` (both below).

`old-tree/data` is a tracked link to the repository's `data/`, so the corpus default the old tree reads
relative to where it runs (`DATA_DIR=data`, and the `data/` that `rerun.sh`, `probe_signature.py`,
`preflight.sh` and `sweep_domain_grid.sh` name) is the same tracked corpus as before, and a vocabulary
written under `data/` lands in the root's `data/`, as it always did. Everything else the old scripts
write relative to where they run — `runs/`, `data_pilot/`, `data_big/`, `sweep_out/`, `bench_out/`, logs —
now lands in `archive/old-tree/` instead of at the root (`equiv.sh`, which names the checkout's own
`runs/` and `data_pilot/`, is the exception; below). `runs/` and `data_pilot/` are gitignored at any
depth. The `mkdir -p runs` above is needed on a checkout that has no `runs/`, here as it was at the
root: a run saves its vocabulary to `<SAVE_CKPT>.dyntok.json` (for `run_full_unfrozen.sh`,
`runs/<RUN_NAME>.dyntok.json`) near its end and dies there if nothing has created `runs/` by then. A
best-model snapshot creates it; a run that took none does not (measured on CPU with `BEST_TRACK=0`).

What the old tree left at the root before the move stays there, and is reached like this:
- **a checkpoint in the root's `runs/`**: prompt it from the root, `python3 archive/old-tree/prompt.py
  CKPT=runs/<tag>`. A checkpoint records its vocabulary's path relative to the directory it was trained
  in, so `CKPT=../../runs/<tag>` from here loads the weights and then misses the vocabulary.
- **corpora**, from here, by pointing the variables at them: `PILOT_DIR=../../data_pilot`,
  `DATA_DIR=../../data_big`. `sweep_domain_grid.sh` looks for `data_big/` in its own directory only.
- **a run directory**: `DATA_DIR=../../data_big OUT=../../runs/long bash longrun.sh resume` continues the
  root's long run where it is, on its corpus, and writes there, as `bash longrun.sh resume` did before the
  move (a resume finds the vocabulary saved beside its checkpoint).

**What changed in these files, and when.** Every file here but two is byte-identical to branch
`rm-predict`, which D5 froze on 2026-08-28:
- `notes_check.py` changed on this branch on 2026-09-22 (`3ff859e`: its generated file says which tree
  it describes). At the move it was made to find `self_organize.py` beside itself and the repository's
  `README.md`, `notes/` and `archive/` two directories up, to require this README instead of
  `ARCHIVE.md`, and to print its own path in the commands it prints. It checks the same 22 files and
  still writes `notes/CURRENT_DEFAULTS.md`.
- `equiv.sh`, at the move: it takes the checkout from `git rev-parse --show-toplevel` rather than from
  its own directory, runs `self_organize.py` wherever the commit under test has it (the root before
  2026-09-28, `archive/old-tree/` after), so it still compares across the move, and names `fetch_big.py`
  by its new path. Its output and its default corpus are still the root's `runs/equiv_*` and
  `data_pilot/`. Both edits kept every line where it was, so line citations into either file still land.
- The `data` link is new.

Checked at the move, on CPU (operation only): `selftest.sh`, quick and full, passes from here as it did
at the root; `preflight.sh` gives the same verdict line for line (its GPU checks fail on a CPU box);
`equiv.sh 55709a8` (the old tree at the root) against the move (the old tree here) reports IDENTICAL at
`SCALE=fast`; a run and its `prompt.py` work from here, and a checkpoint trained at the root before the
move prompts from the root as described above.

## Where each moved path went

Records written before a move keep the paths of their day and are not rewritten: the notes corpus, the
dated entries of `.rework/`'s ledgers, the survey and audit JSON, `results/`, the agent transcripts and
the commit messages. This table resolves them.

| was | is | moved |
|---|---|---|
| `garry/`, `legacy/`, `handoff/`, `docs/FILES.md` and `docs/HANDOFF.md`, `STATE.md`, `CL_TESTBED.md`, at the root | the same names under `archive/` | 2026-08-27 |
| `ARCHIVE.md` | `archive/README.md` | 2026-09-28 |
| the old tree at the root, all 51 files: `bench_gpu.sh` `blowup_test.py` `cap_test.py` `cl_bench.py` `compare.py` `compare_test.py` `corpus_test.py` `curve_test.py` `datastream.py` `domain_test.py` `equiv.sh` `fetch_40g.sh` `fetch_big.py` `fetch_data.sh` `fetch_local.py` `growth_test.py` `harness_test.sh` `holdout.py` `keystone_probe.py` `levers.py` `longrun.sh` `lr_test.py` `mem_evict_test.py` `memory.py` `notes_check.py` `preflight.sh` `probe_ckpt_geometry.py` `probe_signature.py` `probe_stability.py` `proj_test.py` `prompt.py` `ramp_test.py` `rerun.sh` `rescue_ckpt.py` `resume_test.py` `run_cl_test.sh` `run_full_unfrozen.sh` `run_verify_test.py` `runs.csv` `runs.py` `self_organize.py` `selftest.sh` `sweep_domain_grid.sh` `sweep_domain_report.py` `sweep_domains.sh` `tok_test.py` `tokenizer.py` `verification.py` `verify_console_test.py` `vocab.py` `world_model.py` | `archive/old-tree/<same name>` | 2026-09-28 |

The root kept `README.md`, `LICENSE`, `requirements.txt`, `run.py`, `gpu_world.sh`, `sweep_gpu.sh` and
`sweep_world.sh`: a root file a record names that is not in this table is where it was.
