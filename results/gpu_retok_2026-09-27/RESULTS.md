# The 2026-09-27 retok fleet: the result

The owner ran `EXP=retok bash tools/gpu_launch.sh --go` at commit 319f313 on one NVIDIA H200 (torch
2.8.0+cu128, NCPU 13, PAR 12, MPS on). Arms k0 (no act), k3000, k1000 and k0_nuis (`SIG_WARMUP=801`)
ran at seeds 0-2, plus k0_rerun. Each run read one whole 3.78 MB epoch in four phases (areas eng+py,
py+num, py+num, num+c). All 13 runs ended rc=0.

The files here:
- `gpu_retok_2026-09-27.tgz` is the archive: logs, per-flush losses and bytes, SUMMARY, ANALYSIS,
  calibration, smoke, smi.csv, KEPT.txt and the heartbeat. It holds no checkpoints; those are in the
  owner's tars (`CHECKPOINTS.md`).
- `PASTE_BACK.txt` is the fleet's block.
- `verify/` holds this record's re-reads, each script beside its output.

## Verdict

**`TOK_RETOK_EVERY` ships 1000, replacing the interim 3000** (register O14). It is B-provisional until
E2's held-out worst-area re-read PASSes.

Prequential bits/byte, mean over the 3 paired seeds, each flush placed in its phase by its first byte:

| | p1 | p2 | p3 | p4 | whole run |
|---|---|---|---|---|---|
| k0 | 2.5311 | 1.7577 | 1.5711 | 1.8697 | 1.9324 |
| k3000 − k0 | +0.0184 | +0.0015 | +0.0485 | +0.0049 | +0.0183 |
| k1000 − k0 | −0.0139 | −0.0014 | +0.0237 | +0.0204 | +0.0072 |
| k1000 − k3000 | −0.0323 | −0.0029 | −0.0248 | +0.0155 | −0.0111 |

- **Harm (the ε rule per phase, ε 0.05).** k1000 PASSes against k0: its worst upper bound is +0.0426,
  in p4. k3000 is UNRESOLVED: its p3 upper bound is +0.0579.
- **Choice.** Over the whole run, 1000 − 3000 is −0.0111 with a one-sided 95% upper bound of −0.0035
  (p = 0.026), so 1000 is significantly better.
- **Reported, deciding nothing.** M = 0.0182, seed 1's |k0 − k0_nuis|. k0_rerun is bit-exact with k0.s0.
- **C13's alarm.** k1000 blacks out 37.9% of its windows before the pool fills, above 20%. That orders
  a `FAB_COOLDOWN` 100 arm, the next test.

## Verification

Two analysts recomputed the result independently from the raw per-flush losses, bytes and logs, and
this record did it a third time with the scripts in `verify/`:
- `verify.py` reads the rule, the rates and the blackout;
- `replay.py` replays the stream's per-byte areas;
- `areas_check.py` and `areas_1000_3000.py` give the per-area readings;
- `interp_check.py` and `placement.py` give the numbers below.

Everything matched:
- **Integrity.** Each run has one finite loss and one byte count per flush. sum(bytes) equals
  `loop.bytes_scored` exactly (3,779,766-3,779,946 of 3,780,000). The phase gate reads '4 vs 4',
  `torch_seed` is equal across arms at each seed, and no run reached its window cap.
- **The block.** All 13 whole-run values, the phase means and the 16 bounds match (Holm puts k3000
  first, at a = 0.025). So do both verdicts, the choice, M, the rates (239.17 windows/s aggregate) and
  the blackout: k3000 1,995 windows per run, and k1000 6,170, 5,985 and 6,120.
- **Pairing.** k1000 and k3000 equal k0 bit for bit through windows 1001 and 3001, so every difference
  follows an act. A model-free CPU replay of `DATA.draw_stream` and the build tokenizer gives k0's
  per-flush bytes exactly at every seed, so the phases are true stream byte ranges.
- **Reproducible.** `gpu_world.sh --analyze` at this commit, run on a copy with
  `RETOK_INCUMBENT=3000`, reproduces ANALYSIS.txt from RUNS to KEPT and the block. Only the ε-rule
  header's wording differs, and the block's KEPT lines, because the archive holds no checkpoints. At
  the new default incumbent the same runs read "stays 1000". *(Corrected 2026-09-28: the copy must be
  unpacked in a scratch directory, never beside this archive, because `--analyze` rewrites
  ANALYSIS.txt and the block and repacks the `.tgz` beside OUT. At 88d3fae it also deleted the copy's
  KEPT.txt, printed "KEPT: none (KEEP_CKPT off)" and repacked without it. It now keeps KEPT.txt and
  reads its rows, so only the header's wording and the KEPT section's disk and resume lines differ;
  `tests/test_gpu_world.py` F26 holds that on a copy.)*
- **Placement.** Placing each flush by its last byte, or pro rata, moves no phase mean by more than
  0.0007.
- Not checkable here: the 9.93 GB of checkpoint disk.

**Discrepancies.** None is in the arithmetic.
1. **The register did not pin the choice's endpoint.** O14 said harm and choice are read "on the
   worst phase". The script and the contract have read the choice on the whole run since 1bd51c5,
   before the fleet ran. The four readings of 1000 − 3000:
   - every phase: the upper bounds are −0.0295, +0.0072, −0.0103 and +0.0414, so 3000 would have
     stayed;
   - the phase worst against k0 (p3): −0.0103;
   - each run's worst-phase harm: −0.0104;
   - the whole run: −0.0035.

   O14 now names the whole run and says that it did so after the reading.
2. **Holm covers the FAIL side only.** With Holm on the PASS side too, k1000's PASS (intersection-union
   p = 0.030, set by p4) would read UNRESOLVED at a = 0.025. O14 needs only "does not FAIL", so the
   DECISION holds.
3. **k3000's UNRESOLVED got no more seeds**, because no cap was pre-registered (O2). The choice rests
   on "significantly better", not on this.
4. **Per area, which the fleet did not pre-register.** Each phase mixes two areas 50/50. Split by the
   replayed per-byte labels:
   - k1000 − k0 on num in p4 is +0.103 (+0.077, +0.114 and +0.119 by seed). Its lower bound is +0.064
     unadjusted and −0.014 Bonferroni over the 8 area×phase cells, so it reads UNRESOLVED.
   - k3000's is +0.145.
   - Over the whole run, k3000 FAILs on num (+0.067, lower bound +0.052) and k1000 PASSes narrowly
     (+0.043, upper bound +0.046).
   - The p4 mean hides num behind c's arrival gain (c: −0.062 at 1000, −0.134 at 3000).
5. **The block's LOW-GPU-WORLD-ETA line gives the wrong advice.** It says to raise `CAL_WINDOWS` to at
   least 520, but this fleet calibrated on 600. The miss was scheduling (below). The register's
   LOW-GPU-WORLD-ETA row records it: the raise is not taken, and the owed ETA priced by waves replaces
   it.
6. **`CHECKPOINTS.md`'s resume line lacked `RUN_DEVICE=cuda` and `OMP_NUM_THREADS=1`.** It would have
   continued a CUDA parent on the CPU. It is corrected.

## Interpretation

- **Phase pattern: an act's cost depends on when it lands.**
  - *Descriptive, not a test, until note retok fleet (4)'s maturity-matched k0 control runs (the
    spike test's offline analysis, still owed).* Each act is followed by a transient spike whose size
    follows the act's. In 10 KB bins over the next 200 KB, k3000's acts (bytes/token +4 to +11%) peak
    at +0.4 to +1.1 bits/byte against k0, and k1000's (+1 to +4%) at +0.1 to +0.3. The peaks do not
    grow with lateness: k3000's first is its largest (+1.09), and k1000's first eight average +0.23
    and its last eight +0.22. The mean over the same 200 KB does grow: k3000 +0.10, +0.04, +0.10,
    +0.09 and +0.22 by act, and k1000 −0.008 over its first eight acts and +0.052 over its last eight
    (+0.06, +0.11 and +0.24 at its last three). *(Corrected 2026-09-28: this said the spike grows with
    lateness, which its peaks do not show.)*
  - Coarser tokens pay while the model is naive. Right after k1000's first act (window 1001, the end of
    LR warmup) it reads −0.066 over 0.19-0.38 MB at every seed, and p1 holds its first four acts. k3000's
    p1 harm is its first act's spike alone (+0.203 over 0.567-0.661 MB).
  - At c's entry both act arms beat k0 by about 1.1 bits/byte over the first 10 KB.
  - Late acts, at a low LR, cost most. Over the last 5% of bytes, k1000 − k0 is +0.097 (lower bound
    +0.028) and k3000 − k0 is +0.062 (+0.043). Over the last 10% they are +0.092 and +0.118.
  - That end-of-run regime is B's, and the whole-run endpoint dilutes it. E2's re-read and the
    continuation tests are therefore decisive, not formalities.
- **Old areas.** The harm concentrates on num: an old area re-segmented with merges minted as c
  arrives, the risk note retok fleet (3) names. 1000 does less harm than 3000 on every old area at
  every seed (over the whole run eng −0.026, py −0.021, num −0.024). It does more only on the new area
  c (+0.072).
- **Blackout and growth.**
  - The blackout is arithmetic: each act blacks out min(399, windows left). That gives 12.0% for
    k3000's 5 acts and 37.9% for k1000's 15-16, as C13 predicted.
  - Growth is a small lever. An ask adds at most one expert, and growth is about 1% of births (k0: 24
    grown of about 2,355; spawning is not gated). So k1000 forgoes about 13 experts per run out of
    about 3,600 live.
  - The blackout is not the whole deficit. The act arms' `fab.grow_dev` ends at 0.21-0.33, against
    0.13-0.20 in the k0 family, which raises the regression bar. *(Corrected 2026-09-28: the trigger
    compares the loss's rise over `fab.grow_slow` with z × dev in the same units, so the bar relative
    to the loss is dev/slow. For k1000 the higher `fab.grow_dev` is the per-token loss scale, not a
    higher bar: dev/slow ends at 0.102 against k0's 0.097 here, and 0.113 against 0.110 on
    2026-09-28. For k3000 the bar is higher: dev/slow ends at 0.140 (0.137-0.143 by run, against at
    most 0.119 in this fleet's k0 family and k1000; `results/gpu_retok_2026-09-28/verify/j_logs.out`),
    a candidate cause of its lower regression-ask rate. k1000's lower rate has no established cause.)*
    Outside the blackout they ask for regression growth 3-5 times per run, against 8-17.
  - `FAB_COOLDOWN` also spaces growth firings: that refused 8-26 regression asks per k1000 run and
    18-62 per k0 run. So the cooldown fleet prices the whole 400-window cooldown, not the blackout
    alone; one analyst predicts a difference within ±0.01 bits/byte.
- **Pool.** `FAB_SLOTS` 4096 was reached in 2 of 13 runs (k0.s0 and its replicate k0_rerun, from window
  13,401), and end `n_live` ranged 2,469-3,974, so every run ended with 122-1,627 slots free. The
  2026-09-24 fleet filled in 20 of 21 runs, on a stationary phase-1 stream at 87f810a; both counts
  include the fleet's replicate (1 of 12 and 19 of 20 without it). *(Corrected 2026-09-28: this said 1
  of 12 against 20 of 21, counting the replicate for one fleet only.)* Shape and commit (DOM Levels
  on, the merge scan rewritten) are confounded. `n_live` is also chaotic: at seed 1, k0_nuis's
  one-step `SIG_WARMUP` change moved it by 944.
- **Nuisance and fragility.** M = 0.018 is 2.5 times k1000's whole-run effect. k0_nuis is worse at
  every seed and reaches +0.052 in one phase (seed 1, p4). It decides nothing, but at n = 3 the choice
  (p = 0.026) and the PASS (p = 0.030) are fragile, which argues for 5 or more seeds.
- **Rates** (post-fix, from each log's loop time):
  - k0 35.8 windows/s (6,897 B/s, including its 19 periodic saves) and k0_nuis 36.2;
  - k3000 39.2 (8,878 B/s) and k1000 38.5 (9,034 B/s).

  The act and its MEM re-cut take 0.95% and 3.11% of loop time. The rest of the act arms' per-byte gain
  over k0 (−22.3%, −23.6%) is compression (15-18% fewer windows) and k0's saves. k0_rerun, alone, ran at
  37.1 windows/s with the GPU about 22% busy (17-24%). That is as fast as one run of twelve with the
  card 98-99% busy, so each run is bound by its own CPU thread.
- **ETA miss (1.95x).** 13 runs shared 12 slots. k0_rerun started at +433 s, when k1000.s0 finished, and
  took 553 s, alone from +590 s, so the wall was 986 s against an ETA of 505 s.
  - An ETA priced by waves would have been within 3%: 2 × (20,000 / 42.88 + 12.6 s) = 958 s.
  - The heartbeat's "~17m20s (2 waves)", written 20 s into the fleet, was time left: it put the end at
    +1,060 s against +986 s, 7.5% late. *(Corrected 2026-09-28: this set 1,040 s against the whole
    986 s and said within 6%.)*
  - FILL adds seeds only when jobs < PAR, so after the first wave ended (590 s) 11 of 12 slots sat
    idle for 6.6 minutes.

## What it changes

- **The default.** `TOK_RETOK_EVERY` is 1000 (`src/tok/levers.py`, `docs/05_DEFAULTS.md`), provisional
  until E2's held-out re-read. `gpu_world.sh`'s `RETOK_INCUMBENT` and `PIN_RETOK` are 1000.
  - Every `EXP=retok` arm sets its cadence itself, so none of its runs changes, and the 80-window
    baseline fixture reproduces. `EXP=world_epoch` pins `PIN_RETOK`, so its runs move 3000 → 1000 by
    design. `EXP=world`'s four arms set only `WORLD_` levers and it pins nothing, so its runs now act
    every 1000 windows, about 19 acts per 20,000-window run where 3000 gave about 6. *(Corrected
    2026-09-28: this said every fleet arm.)*
  - Re-reading this archive's block needs `RETOK_INCUMBENT=3000`, on a copy unpacked in a scratch
    directory, never beside this archive (Verification, Reproducible).
  - The register (O14, S0b-ship, §8 2.1) and the contract (Q-RUN-8) record the result.
- **The next test is C13's cooldown fleet at the shipped cadence** (`notes/OWNER_BRIEF.md` test 3):
  `EXP=retok RETOK_ARMS="1000" COOLDOWN_ARM=100 SEEDS="0 1 2 3 4" KEEP_CKPT=0`, 21 runs in about 20-25
  minutes. `gpu_world.sh` now reads k1000_cd100 against k1000 with bounds (F25), and the fleet re-reads
  1000 against k0 at 5 seeds. If 1000 FAILs there, it does not ship, and 3000 and the remedy arms run
  next: the fleet holds one cadence, and O14 escalates only when both cadences and every remedy arm
  FAIL (read so since 2026-09-28; at 88d3fae the script would have read ESCALATE). On CPU (operation
  only) the command ran all 21 runs rc=0 and printed both readings (`docs/04_CONTRACT.md` Q-RUN-8).
- **E2 carries a named risk.** At 1000, num in p4 reads +0.10, so E2's worst-area re-read may FAIL
  there. A later retok fleet should pre-register a per-area reading, which needs a CPU build: per-flush
  area bytes in the analysis.
- **Still owed:**
  - the spike test's offline analysis on k0's kept copies (note retok fleet (4));
  - an ETA priced by waves, and a FILL that fills a partial last wave;
  - the continuation from the finals (§8 6.1).
