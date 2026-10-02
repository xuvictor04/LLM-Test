"""Register §8 6.3b's wall, by waves as gpu_world.sh's ETA prices it: the 22 runs in the job list's order (k0, S and
S_replay at each seed, then k0_rerun), each started when a slot frees, each its epoch's windows (realreplay.out at seed
0: k0 17,476; S 14,424 at k1000 and 15,249 at k1000_mn; S_replay 14,625 and 15,528) at the per-run rate the earlier
fleets measured -- 19.2 windows/s on the H100 PCIe at PAR 24 (2026-09-28), about 38 on the H200 at PAR 12 (2026-09-27)
-- times 1.08-1.15 for the in-run reads, R's 2,048-window read, the best saves and the book, plus the startup.

    python3 wall.py
"""
import heapq


def wall(jobs, par):
    slots = [0.0] * par
    for d in jobs:
        heapq.heappush(slots, heapq.heappop(slots) + d)
    return max(slots)


ARMS = {"k1000": (17476, 14424, 14625), "k1000_mn": (17476, 15249, 15528)}
for card, rate, par, startup in (("H100 PCIe", 19.2, 24, 22), ("H200", 38.0, 12, 13)):
    for s, (k0, s_, sr) in ARMS.items():
        mins = []
        for over in (1.08, 1.15):
            jobs = [w / rate * over + startup for _ in range(7) for w in (k0, s_, sr)] + [k0 / rate * over + startup]
            mins.append(wall(jobs, par) / 60)
        print(f"{card}, PAR {par}, S = {s}: the fleet {mins[0]:.1f}-{mins[1]:.1f} min "
              f"({-(-22 // par)} wave(s) of runs)")
