import json,os,sys
S=sys.argv[1]
L6=["hard","easy","cred","false","corrob","late"]; L5=[a for a in L6 if a!="false"]
def J(p):
    p=os.path.join(S,p); return json.load(open(p)) if os.path.exists(p) else None
def m6(d,key='gap_end'): return sum(d[key][a] for a in L6)/6
def m5(d,key='gap_end'): return sum(d[key][a] for a in L5)/5
def pr(*a): print(*a)
# d2 tags
pr("== d2 tags")
for s,p in [(0,'d2/out/tags_s0.json'),(1,'d2/out/tags_s1.json'),(2,'d2/out/tags_s2.json'),(3,'repro/d2/out/tags_s3.json'),(4,'repro/d2/out/tags_s4.json')]:
    d=J(p); o=d['oracle']
    tg={a:d['bpb_end_tag'][a]-o[a] for a in L6+['noise']} if isinstance(d['bpb_end_tag'],dict) else None
    pr(s,'null mean6 %.3f'%m6(d),'tag mean6 %.3f'%(sum(tg[a] for a in L6)/6), 'tag mean5 %.3f'%(sum(tg[a] for a in L5)/5),'tag noise %.3f'%tg['noise'],'trusted_tag_acc',d.get('trusted_tag_acc'),'forget_easy',d['forget_easy'])
    pr('   td_tag', str(d.get('td_tag'))[:300]); pr('   steer', str(d.get('steer_gap_wrong_minus_true'))[:300])
