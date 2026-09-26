# E2's own splice cost (04-Q9's +10% wall line), arithmetic only.
# Inputs: whole-epoch 3.78 MB shape under k3000 reads 3.689 MB by window 15000 at ~300 B/window late
# (verify/emp2/actsim_k3000_s0.txt) -> about 15,300 windows; E2 probes at EVAL_RETENTION_EVERY 160 and sweeps
# DATA_FOCUS_ACT_EVERY 3 / 6 / 25 (docs/proposals/04_SELF_REGULATION.md:1507); every act re-segments the whole
# tail (04:523-525); besides focus acts, ~5 TOK retok acts (k3000: 3001..15001) and 3 phase entries.
# Splice cost 8.63 s per 17 MB tail (rule_pending_measurements/measured.json) = 0.508 s/MB; mean tail about
# half the 3.78 MB stream. Wall at the early 38 windows/s rate the register uses. Excludes the redraw's own
# DATA rebuild.
W = 15300; EVERY = 160; STREAM_MB = 3.78; S_PER_MB = 8.63 / 17; RATE = 38.0
probes = W / EVERY
per_act = (STREAM_MB / 2) * S_PER_MB
wall = W / RATE
print(f"windows {W}, probes {probes:.1f}, mean tail {STREAM_MB/2:.2f} MB, {per_act:.2f} s per act, wall {wall:.0f} s at {RATE:.0f} w/s")
for ae in (3, 6, 25):
    focus = int(probes // ae)
    acts = focus + 5 + 3
    s = acts * per_act
    print(f"  DATA_FOCUS_ACT_EVERY {ae:2d}: {focus} focus + 5 retok + 3 phase = {acts} acts, {s:.0f} s splice, {100*s/wall:.1f}% of wall")
