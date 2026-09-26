import math
def t(d):
    n=len(d); m=sum(d)/n; sd=math.sqrt(sum((x-m)**2 for x in d)/(n-1)); se=sd/math.sqrt(n)
    return m, sd, m/se if se>0 else float('inf')
rows={
 'focus-m27 mean6':[0.033,-0.074,-0.016,-0.009,-0.004],
 'focus-m27 mean5':[0.021,-0.061,-0.035,0.005,0.023],
 'focus-m27 TIG6':[-0.026,-0.105,-0.050,-0.038,-0.055],
 'focus-planned mean6':[-0.284,-0.338,-0.264,-0.188,-0.231],
 'm27-planned mean6':[-0.317,-0.265,-0.248,-0.178,-0.226],
 'focus-m27 easy end':[0.103,0.048,0.117,-0.003,0.117],
 'focus-m27 hard end':[-0.008,-0.293,-0.145,0.033,-0.105],
 'focus-m27 cred end':[0.209,0.088,0.066,0.130,0.191],
 'tags untagged-planned':[-0.015,0.092,0.049,0.092,0.037],
 'lp-m27 mean6':[0.021,0.028,0.056,-0.039,0.073],
 'tags tagged-planned mean6':[1.352-1.751,1.337-1.665,1.425-1.621,1.481-1.655,1.286-1.621],
}
# t crit one-sided alpha .05 df4 = 2.132
for k,d in rows.items():
    m,sd,tt=t(d); print(f"{k:28s} mean {m:+.4f} sd {sd:.4f} t {tt:+.2f}  sig(|t|>2.132): {abs(tt)>2.132}")
# MDE for 5 paired seeds at sd of focus-m27 mean6, alpha .05 one-sided, power .8: (t_.05 + t_.2)*sd/sqrt(n); t_.2 df4 ~0.941
m,sd,_=t(rows['focus-m27 mean6']); print('MDE mean6 5 seeds power .8 ~', (2.132+0.941)*sd/math.sqrt(5))
m,sd,_=t(rows['focus-m27 TIG6']); print('TIG sd',sd)
