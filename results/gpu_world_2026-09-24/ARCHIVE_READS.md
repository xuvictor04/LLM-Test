# The 2026-09-24 WORLD fleet: what its archive adds (read 2026-09-26)

`gpu_world_2026-09-24.tgz` is the fleet's full output (SUMMARY, ANALYSIS, smi.csv, the calibration
ladder, 21 run logs and 21 per-flush loss curves). The owner uploaded it on 2026-09-26; before that
only the transcribed `ANALYSIS.txt` was in the repo. `archive_reads.txt` is the output of
`bash tools/read_fleet_archive.sh gpu_world_2026-09-24.tgz` (Proposal 05 §8 0.2).

**Which tree ran.** `SUMMARY.txt` names commit `87f810a`. Between `87f810a` and `d97779d` (the commit
that recorded the result) only `src/world/levers.py` changed (the `WORLD_FEEDBACK` default), so every
replay the decision register ran at `d97779d` for data, tokenizer and phases applies to this fleet.
The card was one NVIDIA H200 (143,771 MiB), 20 CPU cores by cgroup quota, 12 runs at a time under MPS.

## The four reads

1. **Data source (LOW-D-A13): the default synthetic source in all 21 runs** (`=== data plan:
   protocol=generated` in every log, `EXTRA=''`). With the per-seed stream hashes in
   `results/decisions_2026-09-26/verify/emp2/seedvar.out`, the five seeds trained on five different
   texts. D-A13 did not apply to this fleet; the contract's correction under Q-WORLD-10 now holds
   without its condition.
2. **The expert population (DECISIONS-Q-CAP-2): it does not settle; it fills the slot ceiling.**
   `n_live` climbs from 2,049 and reaches `FAB_SLOTS` = 4,096 in 20 of 21 runs, first between window
   4,301 and 13,201 (median 6,501), and stays there. The exception, `skip.s1` (the unstable
   capacity-control arm), ends at 3,927. Spawning fills the pool (2,664-3,207 spawned per run); once
   it is full, 2,508-16,933 spawns per run are declined, and `gate:fab.spawn` reads "the pool is full
   at cap=4096: growth never reallocates". No run's population comes near the cull's settling point
   of 1,844 that Q-CAP-2 asked about.
3. **Grace and culls (CONTRACT-Q-FAB-5): reachable, as ruled.** `fab.experts_past_grace_ever`
   481-1,002; `fab.merged` 336-648; FAB's cull verdicts `cull_fail` 203-810 and `cull_util` 31-99;
   DOM partitions culled (`part.n_culled`) 4-10. `fab.rescued` is 0 in every run.
4. **Gradient norms (CONTRACT-Q-OPT-3):** end-of-run `opt.grad_norm` p50 1.34-1.89 and p99
   8.6-25.0 (20,000 samples each); the highest p99, 25.0, is `skip.s1`. The fleet never left phase 1
   (Proposal 05 §3.2), so there was no phase turn for a spike to cross.

`fb_off_rerun.s0` reproduces `fb_off.s0` in every counter above, which agrees with the
bit-exact run-to-run floor in `ANALYSIS.txt`.

## What it changes

- **For B, the pool is full before training ends.** On a stationary two-area mixture, with no
  phase change and no forgetting pressure, the expert pool reaches its hard ceiling about a third of
  the way into the run. After training, a new area therefore finds no free slot: it can only gain
  experts through culls and merges of existing ones. The decision register records this as a B risk
  and puts slot headroom (`FAB_SLOTS`) and churn under the GPU plasticity and continuation tests.
- The register's mean-use arithmetic for Q-FAB-5 (about 62-64 selections per expert at ~2,500 live)
  is superseded: the population is 4,096 for most of the run. Its conclusion (culls reachable)
  stands, now measured directly.
