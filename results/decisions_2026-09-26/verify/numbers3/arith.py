import math
def tcdf4(t):
    # closed form for nu=4: F(t) = 1/2 + (3/8)*(x - x^3/3) * ... use numeric integration instead
    nu=4
    c=math.gamma((nu+1)/2)/(math.sqrt(nu*math.pi)*math.gamma(nu/2))
    f=lambda x: c*(1+x*x/nu)**(-(nu+1)/2)
    # integrate 0..t
    n=20000; h=t/n; s=f(0)+f(t)
    for i in range(1,n): s+= (4 if i%2 else 2)*f(i*h)
    return 0.5+s*h/3
def tq(p):  # upper-tail quantile
    lo,hi=0,50
    for _ in range(100):
        m=(lo+hi)/2
        if 1-tcdf4(m)>p: lo=m
        else: hi=m
    return m
def zq(p):
    lo,hi=0,10
    for _ in range(100):
        m=(lo+hi)/2
        if 0.5*math.erfc(m/math.sqrt(2))>p: lo=m
        else: hi=m
    return m
Phi=lambda x: 0.5*math.erfc(-x/math.sqrt(2))
pz=0.5*math.erfc(2/math.sqrt(2)); pt=1-tcdf4(2)
for A in (4,8,20):
    a=1-0.95**(1/A)
    kz,kt=zq(a),tq(a)
    print(A,'fw z %.1f%% t %.0f%%'%(100*(1-(1-pz)**A),100*(1-(1-pt)**A)),'k z %.2f t %.2f'%(kz,kt),
          'power3SE %.0f%%'%(100*(1-Phi(kz-3/math.sqrt(2)))), 'k+0.84 %.2f'%(kz+0.8416),'eps/.. %.4f'%(0.05/(kz+0.8416)),
          'tol full z %.2f t %.2f'%(kz*math.sqrt(2),kt*math.sqrt(2)))
# expected max of n normals
import random
random.seed(0)
for n in (4,8,16):
    N=200000; s=0
    for _ in range(N): s+=max(random.gauss(0,1) for _ in range(n))
    print('E max',n, round(s/N,3))
