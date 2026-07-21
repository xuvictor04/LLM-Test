# GRU is the default base model; a Transformer needs big batches — SETTLED

**Decision:** `MODEL=gru` is the standing base-model default. `MODEL=transformer` exists (multi-layer, for the H100) but
is not the default.
**Why:** this design trains on one window at a time (batch-1, online). A Transformer needs large batches to be worth its
cost and trained far worse here; a GRU's recurrent structure tolerates batch-1 well. Confirmed by controlled experiment.
`BATCH_W` now enables batched-window training if a larger model is wanted (scale `STREAM_LEN` with it).
**Source:** context export Phase 4; `../STATE.md §4` (resolved).
