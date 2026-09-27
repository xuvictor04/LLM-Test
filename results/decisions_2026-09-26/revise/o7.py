"""O7 seed counts at the split alphas (normal approx to noncentral t; scratch)."""
import math
from power import t_ppf, N
def pc(n, M, sd, a):
    df = n-1; tc = t_ppf(1-a, df); ncp = M*math.sqrt(n)/sd
    return N.cdf((ncp-tc)/math.sqrt(1+tc*tc/(2*df)))
def ns(C, sd, a, M=0.05):
    for n in range(3, 500):
        if pc(n, M, sd, a) >= 0.8**(1/C): return n
for a in (0.05, 0.04, 0.01):
    print(f"alpha {a}: C=4 untagged-sd 0.0445 n*={ns(4,0.0445,a)}; easy {ns(4,0.0527,a)} cred {ns(4,0.0624,a)} hard {ns(4,0.1279,a)}; C=6 untagged {ns(6,0.0445,a)}")
# the toy's untagged cost: row 19 of 04's evidence table
x = [-0.015, 0.092, 0.049, 0.092, 0.037]
m = sum(x)/5; s = (sum((v-m)**2 for v in x)/4)**0.5
print(f"untagged - planned: mean {m:.4f} sd {s:.4f} t {m/(s/5**0.5):.2f} UB95 {m + t_ppf(0.95,4)*s/5**0.5:.4f}")
