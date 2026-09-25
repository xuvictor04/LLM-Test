"""Recount D1 live25 vs frozen25 on the codec-invariant readings (0b.2 rows 1-2 of 03_live_codec.md).

Usage (from results/live_codec_design_2026-09-25/prototypes/):
    python3 rev/audit_d1.py . | tee rev/audit_d1.txt
"""
import json,os,sys
B=os.path.join(sys.argv[1] if len(sys.argv)>1 else '.', '')
def path(arm,s):
    lat = arm.endswith('lat')
    if s in (0,1):
        if lat: return B+f'judge/d1c/res/{arm}_s{s}.json'
        return B+f'd1/res/{arm}_s{s}.json'
    return B+f'repro/d1/res/{arm}_s{s}.json'
def rd(arm,s):
    d=json.load(open(path(arm,s)))
    a=d['after_A']; f=d['final']
    return dict(AA=a['A']['bits_per_s'],Aend=f['A']['bits_per_s'],Bend=f['B']['bits_per_s'],
        capAA=a['A']['caption_bits_per_byte'],capAend=f['A']['caption_bits_per_byte'],capB=f['B']['caption_bits_per_byte'],
        Bund=f['B']['understand_exact_train'],AundA=a['A']['understand_exact_train'],Aundend=f['A']['understand_exact_train'],
        recA_A=a['A_codec']['recon_probe_exact'],recA=f['A_codec']['recon_probe_exact'],recB=f['B_codec']['recon_probe_exact'],
        melAA=a['A_codec']['mel'],melAend=f['A_codec']['mel'],melB=f['B_codec']['mel'],text=f['text_bpb'],
        wall=d.get('wall_s'),timers=d.get('timers'),cs=d['counters'].get('codec_steps'),win=f['window'])
worse=0;tot=0;pcts=[]
for rows in ('','lat'):
  for s in range(4):
    L=rd('live25'+rows,s); F=rd('frozen25'+rows,s)
    print(rows or 'table', s, {k:(L[k],F[k]) for k in ('AA','Aend','Bend','capAA','capB','Bund','recA_A','recA','recB','melAA','melAend','text')})
    for k in ('capAA','capB'):
        p=(L[k]-F[k])/F[k]*100; pcts.append(p); tot+=1; worse+= L[k]>F[k]
        print('   ',k,round(p,2))
print('caption worse',worse,'of',tot,'range',round(min(pcts),2),round(max(pcts),2))
for s in range(4):
    L=rd('live25',s); print('timers',s,L['wall'],L['timers'],L['cs'],L['win'])
    F=rd('frozen25',s); print('  frozen',F['wall'],F['timers'],F['win'])
print('--- generation exact (train) live vs frozen')
cnt={'worse':0,'better':0,'tie':0}
for rows in ('','lat'):
  for s in range(4):
    L=json.load(open(path('live25'+rows,s))); F=json.load(open(path('frozen25'+rows,s)))
    out=[]
    for ph,ar in (('after_A','A'),('final','B')):
      for g in ('generate_t1.0','generate_t0.7'):
        l=L[ph][ar][g]['exact_train']; f=F[ph][ar][g]['exact_train']
        out.append((ar,g[-3:],l,f)); cnt['worse' if l<f else 'better' if l>f else 'tie']+=1
    print(rows or 'table',s,out)
print(cnt)
