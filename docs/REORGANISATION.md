# The file-structure reorganisation of 2026-09-28: what is done, and what moves after the Stage 3 merge

**Status.** Phase A is done on `rm-predict-DC` (the commits below). **Phase B is unblocked** since the
Stage 3 branch (`sr0-build`) merged on 2026-09-29 (edb90de), the whole suite green on the merge (*At the
merge*, below). It waited for that merge because each of its steps edits files that Stage 3 also edits
(B1–B2 `docs/04_CONTRACT.md`; B3 `src/ckpt/api.py`, `src/world/levers.py`, `tests/test_assemble.py`,
`docs/` and `.rework/CENSUS.md`; B4 `run.py`, `src/spine/compose.py`, `tests/test_census.py`,
`tests/test_ownership.py` and `docs/04_CONTRACT.md`), and editing them on both branches would make the
merge conflict. The lines of B4's kind in files Stage 3 does not touch were fixed in Phase A instead (B4
lists them). This page is the plan for Phase B, with every reference it has to update, written down so
that it is not lost. When Phase B lands, mark it done here and in the root `README.md`.

Line numbers below are at `fac6aa8` (Phase A's last move). Of the files Phase B edits, Phase A touched
only its own (`README.md`, `archive/README.md`, `.rework/README.md`, `notes/00_INDEX.md`,
`archive/old-tree/notes_check.py`) and no Stage 3 file, so in the Stage 3 files these are also the
numbers at `55709a8`. Stage 3 moves them: after the merge, re-find each anchor by the text quoted with
it, or with the searches below.

The searches also return lines no list here names, and most of those stay as they are. A match is one
more line to fix only if it is in a live file and still places the old tree, its `memory.py`, a sweep
or the notes corpus where it no longer is. The live files are `src/`, `tests/`, `tools/`, `run.py`,
`gpu_world.sh`, the two sweeps, `docs/` (this page aside: it quotes what it looks for),
`requirements.txt`, the root `README.md`, `OWNER_BRIEF.md` and `AGENT_STATE.md` in `notes/`, the
`README.md` indexes of `.rework/`, `results/` and `archive/`, and `.rework/CENSUS.md` with
`census.json`. Records keep the paths of their day, as `archive/README.md` says under
*Where each moved path went*: the notes corpus and `notes/_evidence/`; in `.rework/`, the dated entries
of `DECISIONS.md`, `ISSUES.md`, `PLAN.md` and `COMPACTION_SUMMARIES.md`, and `COMMIT_RECORD.md`,
`reviews.json`, `survey/`, `audits/` and `questions/`; `results/` but its `README.md`; the rest of
`archive/`; the commit messages. At `e125e9c` the second search returns 837 lines, 802 of them in
those records. Live lines that name the root for another reason stay too: a directory named `0` once
written into the repository root, a test run from the repository root, N5's collisions with the root
(`data/` is still one).

## The layout, and the rules it follows

- **The root holds what a reader or the owner starts from.** After Phase A: `README.md`, `LICENSE`,
  `requirements.txt`, `run.py`, `gpu_world.sh`, the two run.py sweeps (until Phase B) and `.gitignore`.
  Everything else is a folder with one job; the root `README.md`'s *Repository layout* maps them.
- **One archive folder, `archive/`, with a README** that says what each record was, why it is kept, how
  to run the old tree, and where every moved path went (its path table). Records keep the paths of their
  day; the path table resolves them. Nothing is rewritten to follow a move.
- **An archived item is named for where it came from:** `archive/old-tree/` (the repository root),
  `archive/rework/` (`.rework/`), and in Phase B `archive/notes/` (`notes/`). Lower case, hyphenated like
  `archive/agent-transcripts/`.
- **A folder that needs an index gets a `README.md`:** `archive/`, `.rework/`, `results/`, as
  `docs/proposals/` already had.
- **Moves are `git mv`, one commit per coherent group,** a pure rename where possible so that
  `git log --follow` and `git blame` keep the history; a file that must also change is edited
  line-neutrally where anything cites it by line.

## Phase A: done

| commit | what it did |
|---|---|
| `427ab21` | `ARCHIVE.md` → `archive/README.md`, a pure rename; `notes_check.py` requires `archive/README.md` |
| `738aba9` | `archive/README.md` rewritten: every record, why it is kept, the path table; a dated correction appended to `notes/00_INDEX.md` |
| `aca21e0` | the old tree's 51 root files → `archive/old-tree/` (49 unchanged; `notes_check.py` and `equiv.sh` edited line-neutrally to run from there); the tracked link `archive/old-tree/data` → `../../data`; `.rework/capture_oracle.py`, `requirements.txt`, the root `README.md` and `archive/README.md` follow; `notes/CURRENT_DEFAULTS.md` regenerated |
| `250dc4b` | `.rework/QUESTIONS.md` (Q1–Q7, ruled as D1–D7) → `archive/rework/QUESTIONS.md`; `.rework/README.md` becomes the folder's index |
| `fac6aa8` | `results/README.md`, the index of the evidence folders |
| `9e65513` | this plan |
| `e125e9c` | `archive/README.md`'s path-table row for `.rework/QUESTIONS.md` joins the table (a blank line had left it outside) |
| the commit after `e125e9c` | a review's fixes: the four lines of B4's kind in files Stage 3 does not touch, and a pointer to Phase B in `notes/AGENT_STATE.md`; in `archive/README.md`, where a root checkpoint resumed from `archive/old-tree/` is prompted from, every script that changes to its own directory, and the old tree's printed commands; `STATE.md` and `CL_TESTBED.md` in the root `README.md`'s layout; on this page, the searches, what a match is, `mkdir -p archive/notes` in B3 and the sweeps' checks |

What was checked, on CPU (operation only): every `tests/test_*.py` and the three tools' `--check`; the
census and ownership counts (N5 finds one root collision, `data`, where it found two; N7 still counts
331 citations; O12 and O13 count what they counted); the owner's commands' check and status paths
(`tools/gpu_launch.sh` without `--go`, `tools/fleet_dash.sh --once`, `gpu_world.sh --status`); from
`archive/old-tree/`, `selftest.sh` quick and full, `preflight.sh` (the same verdicts, line for line, as
at the root), the moved scripts' `--help`, usage and dry paths, a run and its `prompt.py`;
`equiv.sh 55709a8` against the move, IDENTICAL at `SCALE=fast`; `capture_oracle.py` re-run from the
root reproduces the oracle's cases. A trial merge of `sr0-build` (at `c872121`) into Phase A is free of
conflicts, and the census, ownership, contract, assemble, coupling, derive and prose-guard suites and
the tools' `--check` pass on it.

For the commit after `e125e9c`, the same way: the whole suite and the tools' `--check` (N5 one
collision, N7 331); `notes_check.py` (22 files) and `selftest.sh --quick` from `archive/old-tree/`; a
trial merge of `sr0-build` at `d9900c6` onto it, free of conflicts. On scratch clones: a checkpoint
trained at the root before the move and resumed in place from `archive/old-tree/` (`archive/README.md`
has what it showed); `sweep_domain_grid.sh` started by path from the root; B3's `git mv` with and
without its `mkdir`; B1–B2 applied to a trial merge, each sweep started from another directory as the
checks for Phase B below describe.

## The owner's commands

| | before | after |
|---|---|---|
| GPU fleets, the dashboard, the archive reader, `run.py` | `EXP=retok bash tools/gpu_launch.sh [--go]`, `bash tools/fleet_dash.sh`, `EXP=retok bash gpu_world.sh --status`, `bash tools/read_fleet_archive.sh <tgz>`, `python3 run.py ...` | unchanged, and their output stays at the root |
| the run.py sweeps (Phase B) | `bash sweep_gpu.sh`, `bash sweep_world.sh` | `bash tools/sweep_gpu.sh`, `bash tools/sweep_world.sh`, from any directory; `sweep_out/` and `world_out/` stay at the root |
| the old tree (Phase A) | `bash run_full_unfrozen.sh`, `python3 prompt.py CKPT=runs/<tag>`, `bash selftest.sh`, `bash longrun.sh <command>` | `cd archive/old-tree`, then the same commands (`mkdir -p runs` first where there is none) |
| | `python3 prompt.py CKPT=runs/<tag>` for a checkpoint last saved at the root before the move | `python3 archive/old-tree/prompt.py CKPT=runs/<tag>` from the root: a checkpoint records its vocabulary's path relative to where its run started, so once resumed from `archive/old-tree/` it is prompted from there, `python3 prompt.py CKPT=../../runs/<tag>` |
| | `bash preflight.sh`, `python3 notes_check.py`, `bash equiv.sh <ref>`, `python3 fetch_big.py ...` | the same, by path from anywhere: `bash archive/old-tree/preflight.sh`, `python3 archive/old-tree/notes_check.py`, `bash archive/old-tree/equiv.sh <ref>`, `python3 archive/old-tree/fetch_big.py ...` (whose `--out` is relative to where it runs) |

Nothing outside the repository follows the move by itself: a workflow script, a note or a pasted command
that calls an old-tree file at the root (`python3 notes_check.py`, `bash selftest.sh`) needs the form
above, and the two sweeps change in Phase B. Inside the repository the same holds for the old tree's own
printed commands: they name paths relative to `archive/old-tree/`, and the requirements they name are
`../../requirements.txt` from there (`archive/README.md`, *Running the old tree*). `notes/OWNER_BRIEF.md`
is not edited before the merge (see B4).

## Phase B, after the Stage 3 merge

Do it on `rm-predict-DC` after `sr0-build` has merged and the suite is green there, in three commits:
B1–B2, B3, B4. Run the searches first:

```bash
git grep -n -E "bash sweep_(gpu|world)\.sh|sweep_(gpu|world)\.sh"
git grep -n -E "notes/(0[0-9]_|10_|DOC_PLAN|EXTERNAL|RESEARCH_BRIEF|LITREVIEW|research_|_evidence|CURRENT_DEFAULTS)"
git grep -n -i -E "repository('s)? root|repo root|root-level|\./memory\.py|root memory|loose top-level|frozen tree stays where it is|old tree still runs|reads the old system" -- src tests docs notes run.py gpu_world.sh
```

The first serves B1–B2, the second B3, the third B4. The third ignores case and takes the possessive,
because `run.py` writes "THE REPOSITORY ROOT" (:67) and "this repository's root" (:68); its last three
phrases find `run.py:73` and `tests/test_census.py:411` and `:716`, which do not name the root. At
`e125e9c`, and on a trial merge of `sr0-build` at `d9900c6`, it returns a line of every B4 anchor.
Read each match against the rule at the top of this page: most of what the searches return stays.

**At the merge (2026-09-29).** The whole suite, `tests/test_baseline.py --mutants` and the three tools'
`--check` pass. The three searches find every anchor below. The second returns 840 lines, as at b444456
(the three over e125e9c's 837 are this page's own), and names no live file B3 does not list. The third
adds three live lines to b444456's, which stay: two are a test run from the repository root
(`tests/test_baseline.py`'s docstring and its `planted_tree`'s), and one names N5's collision, the root's
`data/` (`tests/test_position.py`'s Q6). Stage 3 moved most of the numbers below, so re-find each by
its quoted text: the contract's B4 line is `:3220`, for one, and `sweep_world.sh`'s usage lines are
`:56`-`:58` and `:66`, its `set -u` `:70`. The counts Phase B's checks compare with, on the merge: N5
one root collision (`data`), N7 336 citations (Stage 3 added five), O12 1,461 symbol citations resolved
and 279 line citations left alone, O13 1,749 citations opened.

### B1–B2: `sweep_gpu.sh` and `sweep_world.sh` move to `tools/`

A run.py sweep is a tool, and the root keeps what a reader starts from. Both scripts run `python3 run.py`
and write `OUT` relative to where they run, with no `cd`, so each gets one line after `set -u`
(`sweep_gpu.sh:41`, `sweep_world.sh:66`), as `tools/gpu_launch.sh:49` has:
`cd "$(dirname "$0")/.." || exit 2`. They then run from any directory and still write `sweep_out/`
and `world_out/` at the checkout's root.

- `git mv sweep_gpu.sh tools/sweep_gpu.sh`; `git mv sweep_world.sh tools/sweep_world.sh`.
- Their usage lines: `sweep_gpu.sh:34`, `:35`, `:50` and `sweep_world.sh:52`, `:53`, `:54`, `:62`,
  `bash sweep_…` → `bash tools/sweep_…`.
- `docs/04_CONTRACT.md:3730`, "The command is `SEEDS="0 1 2 3 4" ONLY=shipped,feedback_off bash
  sweep_world.sh`" → `bash tools/sweep_world.sh` (the same line, so nothing citing the file moves).
- The root `README.md`: drop the two root lines of *Repository layout*, and the `tools/` line reads
  "gpu_launch.sh (check the box, then launch a fleet), fleet_dash.sh (watch it), read_fleet_archive.sh,
  sweep_gpu.sh + sweep_world.sh (run.py sweeps); designate_parent.py (...); render_wiring.py,
  render_defaults.py, sync_counts.py (write, or --check, the generated documents)", `designate_parent.py`
  as the merge wrote it. The run-output sentence stands.
- `archive/README.md`: its sentence "The root kept …" loses the two sweeps, and the path table gains a
  row, `sweep_gpu.sh`, `sweep_world.sh` → `tools/<same name>`.
- Unchanged, because they name the scripts without a path and stay true: `run.py:96`, `run.py:235`,
  `gpu_world.sh:31`, `:33` (the owner's script), `src/spine/compose.py:2231`, `src/spine/loop.py:1729`,
  `:2137`, `docs/04_CONTRACT.md:3660`, `:3728`, `:6501`. No test, tool or record runs either script.

### B3: the 2026-08 notes corpus, its evidence and its defaults file move to `archive/notes/`

`notes/` then holds the two live pages only, `OWNER_BRIEF.md` and `AGENT_STATE.md`. The corpus is the
record of the old tree (its `00_INDEX.md` still opens by superseding the README and `docs/`), and its
defaults file describes the old tree's `_SPEC`, a second "defaults" file beside the live pages.

- First `mkdir -p archive/notes`: `git mv` does not create the directory it moves into, and without it
  both `git mv notes/00_INDEX.md archive/notes/00_INDEX.md` and
  `git mv notes/_evidence archive/notes/_evidence` fail ("fatal: renaming ... failed: No such file or
  directory").
- Move, with `git mv`, the 19 corpus files (`00_INDEX.md`, `01_TIMELINE.md`, `02_IDEAS.md`,
  `03_EXPERIMENTS.md`, `04_RESULTS.md`, `05_ERRORS.md`, `06_CONTINUAL_LEARNING.md`, `07_WIP.md`,
  `08_GLOSSARY.md`, `09_COMMENT_AUDIT.md`, `10_HISTORY_FINDINGS.md`, `DOC_PLAN.md`,
  `EXTERNAL_RESEARCH_BRIEF.md`, `LITREVIEW_FINDINGS.md`, `RESEARCH_BRIEF_DIFFERENTIATION.md`,
  `research_continual_memory.md`, `research_experts_routing.md`, `research_lr_schedules.md`,
  `research_tokenizer.md`), `CURRENT_DEFAULTS.md`, and `notes/_evidence/` (46 files) in one call,
  `git mv notes/_evidence archive/notes/_evidence`, so no empty directory is left behind. 66 files.
  Their content does not change, so every line citation into them (`research_continual_memory.md:743-745`,
  `05_ERRORS.md` lines 255, 602-607 and 1030, `07_WIP.md:485`, `07_WIP:146`) stays true.
- `archive/old-tree/notes_check.py`, keeping its population (22 files) and its line count where it can:
  a `CORPUS = os.path.join(ROOT, "archive", "notes")` beside `NOTES` (:36), `GENERATED` in `CORPUS`
  (:37); `_live_markdown` scans `NOTES` and `CORPUS` (:137-138), and its docstring (:131-132) says
  `archive/notes/` is the one part of `archive/` it reads, and why (it is the record of this `_SPEC`'s
  program); the paths in the module docstring (:4, :20, :27) and in the generated text (:80), and the
  closing message (:181). Then regenerate: `cd archive/old-tree && python3 notes_check.py --write`, and check it
  still reports 22 files and still flags a default planted in `notes/` and in `archive/notes/`.
- `tools/render_defaults.py:3` and `:43` (the header it writes) name `archive/notes/CURRENT_DEFAULTS.md`;
  then regenerate `docs/05_DEFAULTS.md` with `cd tools && python3 render_defaults.py`
  (`tests/test_assemble.py`'s A10 compares the two byte for byte).
- The other live references: `tests/test_assemble.py:1229` and `src/ckpt/api.py:1215` (docstrings,
  `notes/CURRENT_DEFAULTS.md`); `docs/proposals/05_DECISIONS.md:931` (`notes/05_ERRORS.md:602-607`),
  `:1457` (`notes/05_ERRORS.md`), `:1458` (`notes/06_CONTINUAL_LEARNING.md`), `:1484`
  (`notes/05_ERRORS.md`); `docs/04_CONTRACT.md:3581` (`notes/07_WIP.md`); `src/world/levers.py:245`
  (`notes/07_WIP.md:485`); `tools/sweep_world.sh`, the comment at its `:48` and the line it prints at
  `:215` (`:216` after B1–B2's line); `.rework/CENSUS.md:373` and `.rework/census.json:4590` (the
  same sentence in both, `WORLD_HID`'s reason); `.rework/README.md` (`notes/_evidence/commit_log.txt`,
  `notes/_evidence/chat/`). Each becomes `archive/notes/...`, on the same line.
- Optional: `src/spine/assemble.py:735` says "notes 05_ERRORS"; if it changes, regenerate
  `docs/03_WIRING.md` with `cd tools && python3 render_wiring.py` (its `:117` and `:220` carry it).
- The root `README.md`: the `notes/` line of the layout reads "OWNER_BRIEF.md (the owner's page),
  AGENT_STATE.md (the agent's state after a reset)", and the `archive/` line adds "notes/ (the 2026-08
  notes corpus and the old tree's defaults)".
- `archive/README.md`: a `notes/` row in the table; "Where to look instead" names
  `archive/notes/CURRENT_DEFAULTS.md` and says `notes_check.py` scans `archive/notes/` too; rule 1's
  exceptions add dated corrections appended to the corpus (rule 3), which now sits under `archive/`;
  the path table gains the row `notes/<corpus file>`, `notes/_evidence/`, `notes/CURRENT_DEFAULTS.md` →
  `archive/notes/<same path>`.
- Append a dated correction to `archive/notes/00_INDEX.md`: the corpus moved, and where.
- Records keep their paths (the list at the top of this page). Among the second search's matches:
  `.rework/PLAN.md:245`, `:250`, `.rework/COMPACTION_SUMMARIES.md`, `.rework/ISSUES.md`,
  `.rework/COMMIT_RECORD.md`, `.rework/survey/`, `.rework/audits/`, `.rework/questions/`,
  `results/decisions_2026-09-26/`, `archive/agent-transcripts/`, the corpus's own mentions of itself, and
  the old tree's (`archive/old-tree/compare.py`, `longrun.sh:316`, `self_organize.py:6106`).

### B4: the Stage 3 files that still place the old tree at the root

Each anchor below is in a file Stage 3 edits, so Phase A left it alone (the last item adds a line
rather than fixing one). Every one is a comment, a docstring, a prose line or a declaration's reason
text; no check reads them, and the suite is green with them as they are. After the merge, re-find each
by the text quoted with it, or with the third search above, which returns a line of each.

- `run.py:67-74`, the paragraph headed "THE REPOSITORY ROOT MUST NOT BE ON sys.path BEFORE src/": its
  "this repository's root still carries the frozen old tree's `memory.py`" and "THE FROZEN TREE STAYS
  WHERE IT IS": say that it did until 2026-09-28 and is in `archive/old-tree/` now. Keep the heading
  and the `sys.path` repair (:75-79): the root still holds `data/`, named like `src/data`.
- `src/spine/compose.py:61-62`: "`import memory` return the old 654-line ./memory.py".
- `tests/test_census.py:199-203`, `KNOWN_SHADOWS["memory"]`'s reason ("cannot be moved without
  breaking…"): change the reason, keep the key, since the census's self-test plants a root `memory.py`
  (:699-705) and expects N5 to pass; `:398-402`, "The old system's files are still at the repository
  root" and what `import memory` returns under it; `:410-414`, "The old tree still runs", the paragraph
  on why the check does not demand the move: add a dated note that the tree moved whole. In the
  self-test, `:699-701` ("Written to shadow `memory` the way ./memory.py does") and `:714-716` ("every
  `import memory` in the tree silently reads the old system") hold for the tree it plants and no longer
  for this one: say so.
- `tests/test_ownership.py:3061` and `:3164`: "root-level files this rebuild does not index" → files in
  `archive/old-tree/`.
- `docs/04_CONTRACT.md:2897`: "`prompt.py` at the repository root is the old" → "`archive/old-tree/prompt.py`
  is the old".
- `notes/OWNER_BRIEF.md`, not a Stage 3 file: one line for the owner, that the old tree's commands now
  start with `cd archive/old-tree` and the sweeps are `tools/`, if the manager judges it worth his page.
  It waits for B1–B2, so that one line covers both.

Four lines of this kind are in files Stage 3 does not touch (`sr0-build` had changed none of the four
files at `d9900c6`), and were fixed in Phase A (the commit after `e125e9c`; the three code files kept
their line counts): `gpu_world.sh:1881` ("the repository root's memory.py shadows src/memory"),
`notes/AGENT_STATE.md:241` (the working rule stays, with its reason as it now stands: the root's
`data/`, and the old tree's `memory.py` gone), `src/memory/__init__.py:5-7` ("this tree already has a
memory.py at the repo root") and `src/eval/__init__.py:6` ("this tree is full of loose top-level
scripts").

### Checks for Phase B

Every `tests/test_*.py` (in parallel batches; `test_determinism.py` last, then `git checkout
tests/_noise_floor.json`), the three tools' `--check`, `notes_check.py` from `archive/old-tree/`
(22 files, and a planted default caught in `notes/` and in `archive/notes/`), and `selftest.sh --quick`
there. Neither sweep has a dry mode, and `sweep_world.sh` has no CUDA gate (a bare run on a CPU box
starts all 18 arm-and-seed runs), so check each moved sweep this way, on a scratch clone and started
from a directory other than its root: `bash tools/sweep_gpu.sh` on a CPU box stops at its no-CUDA
refusal, exit 1, having written `sweep_out/SUMMARY.txt` at the clone's root;
`ONLY=none bash tools/sweep_world.sh` exits 0 at once, having written only `world_out/SUMMARY.txt`
there. Nothing may land in the directory it was started from. Compare N5, N7, O12 and O13 with the
merge before Phase B (*At the merge*, above): they should not move.

## Deliberately not moved

- `docs/`'s numbering: `tests/test_contract.py`, `tools/sync_counts.py`, `tools/render_wiring.py` and
  `tools/render_defaults.py` name `03`, `04` and `05` by path.
- `tests/` and `tools/`: one level below the root by construction (every file there computes the root
  as its parent's parent), and `tools/sync_counts.py` imports `tests/test_contract.py`.
- `.rework/` and its name: the tests name it by path. `.rework/questions/` stays in it, because it
  holds 10 of the citations N7 counts and N7 does not read `archive/`. `.rework/survey/` and
  `.rework/COMMIT_RECORD.md` stay too: `.rework/PLAN.md:12-13` names both, inside the lines
  `docs/proposals/05_DECISIONS.md:1625` cites (`PLAN.md:11-14`), and the census names the survey
  (`.rework/CENSUS.md:414`, `census.json:5085`).
- `data/`: `DATA_DIR`'s default is `data`, relative to where a run starts, and the owner ruled the
  corpus is input that stays tracked (`.gitignore`).
- `results/`'s folders: the two fleet archives are test fixtures, and the documents cite files inside
  them by path.
- `LICENSE`, `requirements.txt` (`tools/gpu_launch.sh` reads the torch floor from it at the checkout's
  root, and skips that comparison if the file is missing), `run.py`, `gpu_world.sh`.
- No `runs` link beside the old tree: on a box without a root `runs/` it would dangle and break every
  `mkdir -p runs/...` in the old harness. Old-tree runs write `archive/old-tree/runs/` instead.

## Open, for the owner or the manager

- **Recording the instruction.** The owner's instruction for the reorganisation is not yet recorded in
  his words, in `.rework/DECISIONS.md` or in `notes/AGENT_STATE.md` (whose state entry for it points at
  this page); whoever records owner rulings should add it, in the owner's words, under the next free
  number (D19) if it goes into `DECISIONS.md`, which is append-only because
  `docs/proposals/05_DECISIONS.md` cites it by line.
- **Run output at the root is untracked but not ignored:** `gpu_*_out/`, the fleets' `.tgz`,
  `*_fleet.log`, `sweep_out/`, `world_out/`, `data_big/`. Anchored rules in `.gitignore` would quiet
  `git status` on the GPU box; never a bare `*.tgz`, since `results/*/*.tgz` are tracked. The owner's
  call; no check depends on it (the launcher and the fleet look only at tracked changes).
- **The root `README.md`'s other stale claims** (the entry-point and lever counts in *Current state*,
  "no training loop", "The full generated reference is `docs/04_CONTRACT.md`" where it is
  `docs/05_DEFAULTS.md`) were outside this move. Stage 3 changes the counts again, so refresh them after
  its merge.
- **Found while checking, not caused by the move, left as it is:** the old tree's
  `sweep_domain_grid.sh` refuses its own dry run (`DRY=1 SKIP_GPU_CHECK=1`) with "these knobs are NOT
  read by self_organize.py" at the root before the move too, and `compare.py --help` needs the arms'
  separator (`python3 compare.py --help --`). The old tree is frozen.
