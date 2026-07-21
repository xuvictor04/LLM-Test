"""Adaptive write-gate: a threshold that moves DOWN every step and JUMPS UP only when triggered.

Why: the novelty scale drifts as the base trains (we measured in-dist error 3.40 -> 2.28 bits), so a
fixed threshold goes stale -- too permissive early, too strict late. This gate tracks the moving scale
and fires on RELATIVE novelty (above the recent decayed level), staying selective at any scale.

  on fire  : theta += jump   (refractory -- the next capture must be even more novel)
  on quiet : theta -= drift   (receptivity returns over time)
"""
import random
random.seed(0)


class AdaptiveGate:
    def __init__(self, theta, drift=0.04, jump=0.8, floor=1.0):
        self.theta = theta; self.drift = drift; self.jump = jump; self.floor = floor
    def step(self, x):
        if x > self.theta:
            self.theta += self.jump
            return True
        self.theta = max(self.floor, self.theta - self.drift)
        return False


if __name__ == "__main__":
    import random
    random.seed(0)
    # stream: baseline drifts DOWN 3.4 -> 2.3 (the in-dist error as the base trains) + noise + OOD spikes
    N = 400
    stream = [3.4 - 1.1 * (i / N) + random.gauss(0, 0.25) for i in range(N)]
    spikes = set(range(20, N, 40))
    for i in spikes:
        stream[i] += 1.6                                   # an unfamiliar (OOD-like) encounter

    FIX = 3.0
    fixed = [x > FIX for x in stream]
    g = AdaptiveGate(theta=stream[0], drift=0.04, jump=0.8, floor=1.0)
    traj, ada = [], []
    for x in stream:
        th = g.theta; fired = g.step(x); ada.append(fired); traj.append((round(x, 2), round(th, 2), fired))

    half = N // 2
    def rate(flags, a, b): return 100 * sum(flags[a:b]) / (b - a)
    def spike_recall(flags): return 100 * sum(flags[i] for i in spikes) / len(spikes)

    print("=== fixed threshold (3.0) vs adaptive (down-drift + jump-on-fire) ===\n")
    print(f"  baseline drifts 3.4 -> 2.3 over {N} steps;  {len(spikes)} spikes (+1.6)\n")
    print(f"  {'gate':<10}{'writes':>8}{'early-half %':>14}{'late-half %':>13}{'spikes caught %':>17}")
    print(f"  {'fixed 3.0':<10}{sum(fixed):>8}{rate(fixed,0,half):>14.0f}{rate(fixed,half,N):>13.0f}{spike_recall(fixed):>17.0f}")
    print(f"  {'adaptive':<10}{sum(ada):>8}{rate(ada,0,half):>14.0f}{rate(ada,half,N):>13.0f}{spike_recall(ada):>17.0f}")

    print("\nfixed: fires constantly early, goes dead late (scale-dependent).")
    print("adaptive: stable write rate across the drift, catches spikes throughout.\n")
    print("theta trajectory around a spike (step 18-24): downward drift, then a jump on the trigger")
    for i in range(18, 25):
        x, th, f = traj[i]
        print(f"  step {i}:  novelty {x:>5}  theta {th:>5}  {'<-- FIRE (jump up)' if f else 'drift down'}")
