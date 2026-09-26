import json,os,sys
S=sys.argv[1]
L6=["hard","easy","cred","false","corrob","late"]; L5=[a for a in L6 if a!="false"]
def J(p):
    p=os.path.join(S,p); return json.load(open(p)) if os.path.exists(p) else None
def m6(g): return sum(g[a] for a in L6)/6
def m5(g): return sum(g[a] for a in L5)/5
print("== graft")
for s,p in [(0,'judge/w/d3/out/fulltd_tags_s0.json'),(1,'judge/w/d3/out/fulltd_tags_s1.json'),(2,'judge/w/d3/out/fulltd_tags_s2.json'),(3,'repro/d3/out/fulltd_tags_s3.json'),(4,'repro/d3/out/fulltd_tags_s4.json')]:
    d=J(p); o=d['oracle']; ks=[k for k in d if 'tag' in k]
    tg=None
    for k in ('bpb_end_tag',):
        if k in d: tg={a:d[k][a]-o[a] for a in d[k]}
    print(s, ks, 'null m6 %.3f'%m6(d['gap_end']), 'tag m5 %.3f'%m5(tg) if tg else None, 'rho3',d.get('rho_by_phase',[None]*4)[3], 'Qa', d['facts_end']['null_c']['Qa']['acc_true'], 'binds', d['counters'].get('focus.rho_cap_binds'))
print("== act6")
for s,p in [(0,'judge/w/d3/out/fulltd_act6_s0.json'),(1,'judge/w/d3/out/fulltd_act6_s1.json'),(3,'repro/d3/out/fulltd_act6_s3.json'),(4,'repro/d3/out/fulltd_act6_s4.json')]:
    d=J(p); print(s,'m6 %.3f m5 %.3f'%(m6(d['gap_end']),m5(d['gap_end'])), {k:v for k,v in d['counters'].items() if 'act' in k or 'replan' in k})
print("== lp repro s3 s4 / lp_train / replay d1 / d3 replay_fixed 0.2")
for p in ['repro/d1/out/lp_s3.json','repro/d1/out/lp_s4.json','d1/out/lp_train_s0.json','d1/out/lp_train_s1.json','repro/d1/out/lp_train_s3.json','repro/d1/out/lp_train_s4.json','d1/out/replay_s0.json','d1/out/replay_s1.json','repro/d1/out/replay_s3.json','repro/d1/out/replay_s4.json','d3/out/replay_fixed_s0.json','d3/out/replay_fixed_s1.json','repro/d3/out/replay_fixed_s3.json','repro/d3/out/replay_fixed_s4.json','d1/out/loss_s0.json','d1/out/loss_s1.json','d1/out/base_cm_s0.json','d1/out/base_cm_s1.json','d1/out/base_s0.json','d1/out/base_s1.json','d1/out/base_s2.json']:
    d=J(p); print(p,'m6 %.4f'%m6(d['gap_end']),'fe %.3f'%d['forget_easy'],'fh %.3f'%d['forget_hard'],'hard %.3f'%d['gap_end']['hard'],'noise_share %.3f'%d['drawn_share']['noise'], 'probe_frac',d.get('probe_overhead_windows_frac'))
print("== sel")
for s in (0,1,2):
    d=J(f'd2/out/sel_s{s}.json'); print(s,'m6 %.3f'%m6(d['gap_end']), 'wall',d['wall'], 'gws', {k:round(v,3) for k,v in d['grad_weight_share'].items()} if isinstance(d.get('grad_weight_share'),dict) else d.get('grad_weight_share'), 'ds noise %.3f'%d['drawn_share']['noise'])
for s in (0,1,2):
    d=J(f'd2/out/base_s{s}.json'); print('base',s,'wall',d['wall'])
print("== nomir / rehearse / trust walls")
for p in ['d3/out/focus_nomir_s0.json','d3/out/focus_nomir_s1.json','d3/out/rehearse_s0.json','d3/out/rehearse_s1.json','d3/out/fulltd_s0.json','d3/out/fulltd_s1.json','judge/w/d3/out/fulltd_s2.json']:
    d=J(p); print(p,'wall %.1f probe %.2f trust %s'%(d['wall'],d['wall_probe'],d.get('wall_trust')), 'rf',d['counters'].get('focus.rehearse_fired'),'rcb',d['counters'].get('focus.rho_cap_binds'),'rho',d['rho_by_phase'])
print("== focus/fulltd counters")
for arm in ('focus','fulltd'):
  for s,p in [(0,f'd3/out/{arm}_s0.json'),(1,f'd3/out/{arm}_s1.json'),(2,f'judge/w/d3/out/{arm}_s2.json'),(3,f'repro/d3/out/{arm}_s3.json'),(4,f'repro/d3/out/{arm}_s4.json')]:
    d=J(p); c=d['counters']; print(arm,s,{k:c.get(k) for k in ['focus.rehearse_fired','focus.rho_cap_binds','focus.floor_binds','focus.cap_binds','focus.replans']})
