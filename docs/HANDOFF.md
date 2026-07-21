# HANDOFF.md — pick-up-here guide for the next session

**Purpose:** a self-contained snapshot so a fresh chat (with no memory of the prior one) can continue
without re-deriving the project. Written 2026-07-21. Pairs with `docs/FILES.md` (what each file is)
and `STATE.md` (the live ledger + binding protocol).

> **Why this exists:** the previous chat could not be compressed and was migrated. This doc + `FILES.md`
> + the reconciliation below are the carry-over. Anything measured on a GPU happens on the user's own
> H100 and is pasted back — **this environment has no GPU**, so never run the real suite here and never
> invent measured numbers.

---

## 1. What the project is (one paragraph)

An autonomous continual-learning system driven by **one unlabeled stream**. It self-assembles domains
(C), grows a society of independent experts (Fabric), writes surprise-gated memory tagged by
provenance, detects wrong info (B), and edits/unlearns by provenance (A). The headline, defensible
result: **deleting a whole expert's weights is essentially free** (−0.0009 collateral), which inverts
the premise that weights are un-editable because they're entangled. Independence is what makes removal
clean. See `README.md` for the pitch, `CL_TESTBED.md` for the mechanism, `garry/GARRY.md` for the
frozen milestone numbers.

## 2. Status of the three parts (honest)

- **A — edit/unlearn by provenance: PROVEN.** Surgical unlearn of a whole process, ~1000× less
  collateral than gradient-ascent on weights. This is the shippable product and does **not** depend on B.
- **C — self-assembly: WORKS, over-segments.** Hundreds of fine domains for 4 true processes; proven
  **harmless** because knowledge composes across segments at retrieval (global kNN, no src filter).
- **B — wrong-detection: DOES NOT WORK in the realistic regime.** Self-consistency conflates
  "surprising" with "wrong" (the write gate stores surprising tokens; B flags surprising tokens).
  High recall, ~1–2% precision. Runs **DETECT-ONLY** — reports, never deletes.
- **Generation:** semi-coherent, not fluent. The ceiling is the small base model, not the architecture.

## 3. Two characterized regimes (choose per use case)

| regime | flags | end-to-end | expert deletion | specialization |
|---|---|---|---|---|
| **REDUNDANCY** (= frozen `garry/`) | `ROUTE_T=1.0` | 1.967 b/B | FREE (−0.0009) | none |
| **MODULARITY** | `ROUTE_GROUNDED=1 ROUTE_T=0.3` | 2.002 b/B | +0.127, concentrated on that expert's domains | real, for +0.035 b/B |

## 4. Frozen milestone vs live code

`garry/` is the **T33** frozen reference — do not edit it. **Root is its descendant**, not a copy: root
= garry T33 **plus** a later retrieval-grounding / source-passage feature set (`GROUND`, per-entry
`pos`, `source.bin`, an affiliation diagnostic). `cl_bench.py` and `tokenizer.py` are identical between
the two. Full diff table in `docs/FILES.md`.

## 5. Open questions — the user decides these (do NOT default; ASK)

Carried from `STATE.md §4`, still open:
0. **Expert evolution type.** Current scheme (occupancy fitness, Lamarckian inheritance, niche
   speciation) was never chosen by the user — its weakness is that a frequently-routed *bad* expert
   still wins. Alternatives: Darwinian per-expert loss fitness, tournament routing, adapter crossover,
   self-adaptive mutation, age-layered protection for young experts.
1. **Management ON/OFF ablation.** `PHASED=1` (non-stationary stream) is built; still owed a number for
   *how much* memory management + editing actually buy on a shifting stream.
3. **B direction.** Attempt a corroboration/contradiction signal (hard, speculative) — or **cut B** and
   ship clean-unlearning-on-command (A already delivers)?

Resolved/addressed (do not re-litigate): online tokenizer minting kept; base model can scale to a
Transformer on the H100; tokenizer ON for the full test.

## 6. How to resume work

1. Read `STATE.md §2` (Decisions — `[USER]` calls you must not override) and `§5` (Config) **before**
   any choice. Follow the binding protocol in `STATE.md §3`: update the ledger *before* responding each
   turn, flag every `[me]` default, report every add/remove/change **and** omission.
2. For a real measurement: the user runs `bash run_full_unfrozen.sh` (or `garry/`) on their H100 and
   pastes the output. Estimate wall-clock **before** proposing any GPU run (a standing `[USER]` directive).
3. Record new numbers in `STATE.md §7` **with their run/config**, and add a `garry/`-style comparison.
4. Bias toward pruning / simplification (standing `[USER]` directive).

---

## 7. Reconciliation ledger (state of the docs as of 2026-07-21)

The docs drifted because measurements happened across many GPU sessions and the ledger was only
partly maintained. What I found, and what I did about it:

### Fixed this session
- **`STATE.md` dangling cross-refs** — `§0/§2/§4` pointed to `§7z`, `§7x`, `§7n`, `§7r`, `§7c`, which
  never existed in the compacted file. Stripped the phantom labels; pointed the T33 reference at
  `garry/GARRY.md` (where those numbers actually live).
- **`STATE.md` "Latest results" (§7) was stale** — it is the **T2 dev run** (VMAX 4096, 476 domains,
  1.727 w/ memory), which is *older and weaker* than the **T33 GARRY** run (VMAX 8192, end-to-end
  1.967). Relabeled §7 as the T2 dev run and pointed "newest" at `garry/GARRY.md`.
- **`STATE.md` double "(current)"** — both T4 and T1 were tagged current in the changelog; fixed.
- **`README.md` output paths** — claimed `~/full_unfrozen.txt` and `runs/ck/`; the script's actual
  defaults are `~/full.txt` and `runs/full/` (or `~/<RUN_NAME>.txt` / `runs/<RUN_NAME>/`). Corrected.
- **`cl_bench.py` header** — usage line said `python3 control.py clbench …`; `control.py` is in
  `legacy/` and there is no `clbench` subcommand. Corrected to `python3 cl_bench.py`.

### Flagged, NOT auto-changed (left for the user to decide)
- **The T5–T32 history gap.** `STATE.md`'s changelog runs T0–T4; `garry/GARRY.md` is "T33". These are
  different counters — the ledger's `T0` was "created this ledger" (adopted late), while the Fabric /
  society / experts / phased-stream / grounding work that the *code* clearly contains is **not** written
  up in `STATE.md §6/§7`. That history lived in the migrated chat and on the GPU logs; it is not
  recoverable from the repo. **Do not fabricate it.** `STATE.md §2` (Decisions) *was* kept current
  through that work, so it is the trustworthy part of the ledger; §6/§7 are the stale part.
- **B precision "1%" vs "2%"** across README/STATE/CL_TESTBED/GARRY — different runs; both are "very
  low," the point ("B is detect-only") is unaffected. Left the run-specific numbers in place.
- **Collateral ratios** (810× / 1250× / ~25,000×) compare *different* operations (memory-delete-vs-
  weights vs expert-delete-vs-weights) on *different* runs; not contradictions once attributed. See the
  per-doc source before quoting a single ratio.
- **"Society of independent experts" naming.** The default run uses the **Fabric** society (`FABRIC=1`),
  not the alternate `ExpertBank`/`ExpertRouter` population (`EXPERTS=0`). Both are called "experts" in
  places; worth disambiguating if the README is ever rewritten.
- **`memory.py` dead constructor params** — `wrong_thresh` / `wrong_margin` / `wrong_min_n` are accepted
  but unused (kept for compat). Not live knobs; don't document them as such.
- **`tokenizer.py`** — references a `continual_tokenizer.py` that doesn't exist (the online variant is
  `DynamicTokenizer` in the same file), and defines `seg` twice (second wins). Cosmetic.

### Authoritative sources (when docs disagree)
- **What the code *is*** → `docs/FILES.md` (read from source this session).
- **Newest measured numbers** → `garry/GARRY.md` (T33), until a newer GPU run is pasted into `STATE.md §7`.
- **User decisions you must honor** → `STATE.md §2` + `§5`.
</content>
