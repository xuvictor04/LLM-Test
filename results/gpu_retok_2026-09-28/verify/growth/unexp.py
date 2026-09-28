# Where do the regression trigger's "unexpected" readings fall relative to the acts? And counterfactual replays.
import json, numpy as np
from counters import parse, FL
from replay import replay, FAST, SLOW, MAD
def unexpected_times(L, z=4.0):
    n=0; fast=slow=dev=None; out=[]
    for i,loss in enumerate(L):
        step=i+1; n+=1
        fast=loss if fast is None else (1-FAST)*fast+FAST*loss
        slow=loss if slow is None else (1-SLOW)*slow+SLOW*loss
        d=abs(loss-slow); dev=d if n==1 else (1-MAD)*dev+MAD*d
        if (loss-slow)>z*max(1e-6,dev): out.append(step)
    return out
def since(w,acts):
    p=[a for a in acts if a<w]; return w-max(p) if p else None
fl='H100'
PH4={}
for sd in range(5):
    by=np.array(json.load(open(f'{FL[fl]}/curves/k1000.s{sd}.bytes.json'))); off=np.concatenate([[0],np.cumsum(by)[:-1]])
    PH4[sd]=[int(np.searchsorted(off,b,side='left'))+1 for b in [945000,1890000,2835000]]
print('unexpected flushes (regression trigger true) by windows since the last act: bins 0-99 / 100-399 / 400-999, and those within 30 windows of a phase entry')
for arm in ['k1000','k1000_cd100']:
    tot=np.zeros(3,int); tph=np.zeros(3,int)
    for sd in range(5):
        tag=f'{arm}.s{sd}'
        d,prog,acts=parse(f'{FL[fl]}/logs/{tag}.log'); L=json.load(open(f'{FL[fl]}/curves/{tag}.json'))
        u=unexpected_times(L)
        h=np.zeros(3,int); hp=np.zeros(3,int)
        for w in u:
            s=since(w,acts)
            if s is None: continue
            b=0 if s<100 else (1 if s<400 else 2)
            near=any(0<=w-p+1<=30 for p in PH4[sd])
            h[b]+=1; hp[b]+=near
        tot+=h; tph+=hp
        print(f'  {tag:16s} {h.tolist()}  of which near a phase entry {hp.tolist()}')
    print(f'  {arm:16s} total {tot.tolist()} near phase entry {tph.tolist()}')
print()
print('counterfactual: each run\'s own loss curve replayed at the other cooldown (asks by leg; R asks in [100,400) of an act, and whether at a phase entry)')
for arm,alt in [('k1000',100),('k1000_cd100',400)]:
    for sd in range(5):
        tag=f'{arm}.s{sd}'
        d,prog,acts=parse(f'{FL[fl]}/logs/{tag}.log'); L=json.load(open(f'{FL[fl]}/curves/{tag}.json'))
        c,ev,g=replay(L,acts,cool=alt)
        rb=[(w,since(w,acts)) for w,leg in ev if leg=='R' and since(w,acts) is not None and 100<=since(w,acts)<400]
        sb=[(w,since(w,acts)) for w,leg in ev if leg=='S' and since(w,acts) is not None and 100<=since(w,acts)<400]
        print(f'  {tag:16s} at cool {alt}: aR={c["aR"]} aS={c["aS"]} bkW={c["bkW"]}  R in [100,400): {rb}  S in [100,400): {len(sb)}   phase-4 entry {PH4[sd][2]}')
