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

# RE-RUN AT THE SHIPPED CADENCE (2026-09-28, the review of the retok fleet read). TOK_RETOK_EVERY ships 1000
# since the 2026-09-27 retok fleet (register O14) and E2 pins the shipped cadence (S0b-ship), so E2's retok
# acts are k1000's, not k3000's 5. In that fleet k1000 acted 16, 15 and 16 times (seeds 0-2) over 16,186,
# 15,957 and 16,136 windows of the same 3.78 MB epoch (results/gpu_retok_2026-09-27/ANALYSIS.txt), so 16
# retok acts, at the windows above and at the fleet's own. Each act is priced as above (0.96 s, this
# container's CPU) and at the act time the fleet measured on the GPU box's CPU, loop.act_seconds over
# loop.acts in each k1000 log (the MEM re-cut, loop.act_remap_seconds, is not in it).
RETOK = 16
W_K1000 = round((16186 + 15957 + 16136) / 3)
ACT_S_FLEET = (11.172267 / 16, 10.679583 / 15, 11.857102 / 16)
for label, w_ in (("the windows above", W), ("k1000's mean windows in the fleet", W_K1000)):
    probes_, wall_ = w_ / EVERY, w_ / RATE
    print(f"k1000, {RETOK} retok acts, {label} ({w_}): probes {probes_:.1f}, wall {wall_:.0f} s at {RATE:.0f} w/s")
    for ae in (3, 6, 25):
        focus = int(probes_ // ae)
        acts = focus + RETOK + 3
        s = acts * per_act
        lo, hi = acts * min(ACT_S_FLEET) / wall_, acts * max(ACT_S_FLEET) / wall_
        print(f"  DATA_FOCUS_ACT_EVERY {ae:2d}: {focus} focus + {RETOK} retok + 3 phase = {acts} acts, {s:.0f} s splice, "
              f"{100*s/wall_:.1f}% of wall; at the fleet's {min(ACT_S_FLEET):.2f}-{max(ACT_S_FLEET):.2f} s per act "
              f"{100*lo:.1f}-{100*hi:.1f}%")
