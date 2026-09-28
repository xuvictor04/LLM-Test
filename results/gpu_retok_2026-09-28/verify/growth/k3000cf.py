import json, numpy as np
from counters import parse, FL
from unexp import unexpected_times, since
from replay import replay
fl='H200'
for sd in [0,1,2]:
    tag=f'k3000.s{sd}'
    d,prog,acts=parse(f'{FL[fl]}/logs/{tag}.log'); L=json.load(open(f'{FL[fl]}/curves/{tag}.json'))
    u=unexpected_times(L)
    late=[(w,since(w,acts)) for w in u if since(w,acts) is not None and 100<=since(w,acts)<400]
    for cool in (400,200,100):
        c,ev,g=replay(L,acts,cool=cool)
        rin=[(w,since(w,acts)) for w,leg in ev if leg=='R' and since(w,acts) is not None and since(w,acts)<400]
        print(f'{tag} acts {acts}: act readings at 100-399: {late}; replay at cool {cool}: aR={c["aR"]} aS={c["aS"]}  R asks within 400 of an act: {rin}')
# bytes/token rise per act for k3000 and k1000 (from the act warning lines)
import re
for tag in ['k3000.s0','k1000.s0']:
    for line in open(f'{FL[fl]}/logs/{tag}.log'):
        m=re.search(r'act at window (\d+).*Tail bytes/token ([\d\.]+) -> ([\d\.]+) \(([+\-\d\.]+)%\)',line)
        if m: print(tag, m.group(1), m.group(4)+'%', end=' | ')
    print()
