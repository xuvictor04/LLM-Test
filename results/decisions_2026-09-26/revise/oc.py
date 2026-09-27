"""Operating characteristics of the gate's calibration check (binomial), scratch only."""
from math import comb
def cdf(k, n, p): return sum(comb(n, i) * p**i * (1-p)**(n-i) for i in range(k+1))
print("False rollbacks: HARD kept if <=5 of 100 pooled benign sessions")
for p in (0.02, 0.03, 0.05, 0.08, 0.10):
    print(f"  true FR {p:.2f}: P(stay/turn HARD) = {cdf(5,100,p):.3f}")
print("Power at eps: HARD kept if >=16 of 20 graded-eps sessions caught")
for p in (0.6, 0.7, 0.8, 0.9, 0.95):
    print(f"  true power {p:.2f}: P(>=16/20) = {1-cdf(15,20,p):.3f}")
print("Canary: per-session trigger share 0.01, confirmation 0.05 per tripped canary")
pf = 0.01*0.05
for runs in (90, 180):
    print(f"  false confirmed trips over {runs} sessions: expected {runs*pf:.3f}; P(any) <= {1-(1-pf)**runs:.3f}")
print("Unconfirmed false trips expected over 90 sessions at 1%:", 0.9)
