# The 2026-09-28 cooldown fleet: the result

The owner ran `EXP=retok RETOK_ARMS="1000" COOLDOWN_ARM=100 SEEDS="0 1 2 3 4" KEEP_CKPT=0 bash
tools/gpu_launch.sh --go` at 5c28ca4 on a different provider and card from 2026-09-27: one NVIDIA H100
PCIe (81,559 MiB; torch 2.7.0, CUDA 12.8; NCPU 26, PAR 24, MPS on). k0, k1000, k1000_cd100
(`FAB_COOLDOWN=100`) and k0_nuis ran at seeds 0-4, plus k0_rerun: 21 of 21 runs rc=0, no checkpoints
kept. The code copy's sha256 (9ccacc5afb465b9b) recomputes from `git archive 5c28ca4`.

Files: `gpu_retok_2026-09-28.tgz` (the archive; it equals the upload), `PASTE_BACK.txt` (the block) and
`verify/`, each script beside its output: `j_main.py` (the rule, per area, the late bytes), `j_noise.py`
(the nuisance pairs), `j_logs.py` (FAB and the pool), `replay.py` (the per-byte area labels), `growth/`
(the growth trigger, replayed) and `record_checks.py` (the rest). The label arrays are not kept: they
regenerate by running `replay.py` from a scratch copy with `DATA_DIR=<checkout>/data` and a `src/` from
`git archive 5c28ca4` (the 319f313 its docstring names draws the same stream: the src differs only in
comments and the retok default, which the replay sets to 0).

## Verdict

**`TOK_RETOK_EVERY` stays 1000** (register O14), B-provisional until E2's held-out worst-area re-read.
k1000 − k0, paired over 5 seeds: mean [lower bound at t(1 − a/4); one-sided 95% upper bound].

| p1 | p2 | p3 | p4 | whole run |
|---|---|---|---|---|
| −0.0319 [−0.1169, +0.0200] | −0.0044 [−0.0364, +0.0151] | +0.0162 [+0.0075, +0.0215] | −0.0091 [−0.0441, +0.0123] | −0.0073 |

- **Harm.** k1000 PASSes against k0 on a second card and torch (worst upper bound +0.0215, p3). The
  fleet held one cadence, so the choice is not re-read and nothing escalates.
- **`FAB_COOLDOWN` stays 400** (C13). k1000_cd100 − k1000 PASSes per phase (+0.0002, +0.0028, +0.0007,
  −0.0026) and reads +0.0003 over the whole run (upper bound +0.0067, not below 0), so no measured cost
  of the cooldown is recorded. Growth moved and learning did not: the blackout fell from 37.9% to 9.7%
  of windows and grown regression/stall per run went from 2.4/7.2 to 3.0/12.0 (k0 10.6/11.2). C13's
  alarm stays tripped at the defaults, with no arm left to order at this shape.
- **Reported, deciding nothing.** M = 0.0788 (seed 1). k0_rerun is bit-exact with k0.s0.

## Verification

Three analysts, then `verify/`, recomputed every block number from the raw curves, bytes and logs. Each
run has one finite loss per flush, its bytes sum to `loop.bytes_scored` (21 of 21), the phase gate reads
'4 vs 4', and no run reached its cap. The archive equals the upload (`tar -d`), and STATE's
`log=.../retok_fleet.log` is the launcher's default LOG. Pairing: k0_nuis has k0's bytes and equals it
through flush 1-2 only; k1000 equals k0 through flush 1001, its first act; k1000_cd100 equals k1000
through flushes 3,130-4,220. The replayed labels give k0's per-flush bytes exactly at 5 of 5 seeds, and
the growth trigger, replayed, reproduces all ten growth counters and `fab.grow_dev` in all 34 runs of
both fleets. **Discrepancies, wording only:** "at PAR 24" where 21 runs ran; an ETA priced on 20,000
nominal windows a run (1.2x by the windows run); ESTIMATED on a blackout split the act windows give
exactly; `FILL=1` one slot short of a sixth seed past the cap (21 runs + 4 arms against PAR 24); and the
contract's expected repeat of 2026-09-27's seeds 0-2, which needed the same card and torch.

## Beside the rule, deciding nothing

1. **Per area, E2's risk** (pre-registered by neither fleet). num in p4 reads +0.091 at k1000 − k0
   (Bonferroni-8 lower bound +0.065, upper +0.104; +0.072 to +0.104 by seed): FAIL level. It grows
   through p4 (+0.051, +0.083, +0.115, +0.117 by quarter); over the last 10% of bytes num reads +0.114
   and the whole stream +0.066 (lower +0.039), against +0.119 and +0.092 on 2026-09-27. The arriving c
   gains −0.109 in p4, which hides num in the phase mean; over the whole run num reads +0.034 (upper
   +0.041). It replicates 2026-09-27's +0.103, where 3000 read +0.145. No cadence change follows: 3000
   is worse on num (1000 − 3000 there is about −0.04 at every seed), and 0 is never shipped by rule.
   The 2026-09-27 choice stands on that area, though about 73% of its whole-run margin was phase 1
   (from 0.756 MB on, 1000 − 3000 is −0.0033, upper +0.0048).
2. **The p3 cost replicates:** +0.016 (lower +0.0075) here, +0.024 (lower +0.011) on 2026-09-27,
   positive at 8 of 8 seed-cards, below ε.
3. **Noise.** M is seed 1's late loss drop: k0.s1 crossed 2.5 bits/byte (50-flush rolling) at flush
   2,045 against 1,210-1,583 for the other 15 k0-family runs of both fleets (z 5.1), and p1 carries
   +0.062 of its +0.079. The runs part chaotically on identical bytes; the between-run spread is 4-41
   times the SE of independent flushes. p1's paired SD is 0.11 over the 8 pairs; after the drop the
   per-run SD is 0.004-0.006 in p2-p3, about 0.01 for num in p4, about 0.03 for c and 0.015-0.018 for
   num over the last 10%. k0_nuis itself reads UNRESOLVED against k0 (p1 upper +0.132). The PASS holds
   dropping any one seed and pooled over the 8 pairs (descriptive); against k0_nuis in place of k0 it
   reads UNRESOLVED (p1 upper +0.067); O14 keeps 1000 either way.
4. **Not repeats of 2026-09-27:** the card and torch changed. Flush-0 losses differ by 2.3e-4 to 5.0e-4
   nats on identical bytes, and k0.s1 reads 2.0081 against 1.9048. Pairs are read within one card;
   pooled figures are descriptive only.
5. **The cooldown's mechanism** (`verify/growth/`). The act's own regression readings end within 68
   windows of it, and the 400 blackout also held back a regression ask at c's arrival in 4 of 5 runs.
   A late k3000 act (2026-09-27 s0, window 15,001) had readings to +132 windows, where the trigger would
   have grown at 100 and not at 200. The act arms' low regression-ask rate (2.8 per run at 400, 3.2 at
   100, k0 12.2) is not the blackout's, and the spacing refused no stall ask in 34 runs.
   `fab.growth_blackout_suppressed.stall` counts every waiting check inside a blackout, not asks. A
   re-opened lever's arm would be a separate stamp-blackout window sized from these transients (at most
   132 windows), with a k0 cooldown control (not built).
6. **Pool.** `FAB_SLOTS` was reached in 3 of 21 runs, all at seed 2 (k0 from window 6,701, k1000 from
   8,401, k1000_cd100 from 6,901; not k0_nuis). k1000_cd100.s2 ended full; every other run had
   125-1,533 slots free.
7. **Rates.** 19.22 windows/s per k0 run (plain text, no saves; 16.6 alone in the one-run calibration);
   the act and its MEM re-cut take 2.41% of loop time. Calibrated 416.4 aggregate at PAR 24; the
   heartbeat read 411-423 while all 21 trained; 348.4 over the 1,084 s wall; 25 min 17 s from launch to
   block. The ETA's 1.07x is two offsetting errors: nominal windows (the act arms ran about 16,100) and
   every slot assumed busy to the end.

## What it changes

- **No default moves:** `TOK_RETOK_EVERY` 1000 (provisional until E2), `FAB_COOLDOWN` 400. The register
  (O14, S0b-ship, C13, note NEW-02, NEW-20, O20, §8 2.2 and the rows it names), the contract (Q-RUN-8,
  Q-RUN-17) and the owner brief record the reading.
- **Method** (note NEW-02): a training-run test whose arms leave their control before the loss drop
  decides on the bytes from 20% of the stream on (0.756 MB here), or branches its arms after the drop,
  and sets its seeds from the measured spread; a capped command passes `FILL=0`.
- **Owed:** E2's pre-registration reads the end state per area, worst area, within one card and torch,
  and names O14's remedy arms for old-area text re-segmented late at a low learning rate (3000 is not
  one); per-area cells in `analyze_retok`; the text fixes after the Stage 3 merge
  (`notes/AGENT_STATE.md`). No GPU test is ready now: the next ones need SR0.
