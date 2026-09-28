# Replay FAB.grow_check's WATCH/trigger state machine (src/fabric/api.py grow_check, 5c28ca4) from the
# per-flush loss curve (the same float the loop hands grow_check as flush_loss) and the act windows (the stamps).
import json, sys, os, re
from counters import parse, FL
FAST, SLOW, MAD = 0.02, 0.002, 0.01
def replay(losses, acts, cool=400, z=4.0, plateau=0.002, warm=300, rec_min=600, rec_max=20000, step0=1):
    g=dict(n=0,fast=None,slow=None,dev=None,state='W',t0=None,last=None,last_regr=None,shift_seen=None,checked_at=None)
    c=dict(aR=0,aS=0,bsR=0,bsS=0,rcR=0,rcS=0,rec=0,warm=0,bkW=0,shift=0)
    ev=[]
    acts=sorted(acts); ai=0
    stamp=None
    for i,loss in enumerate(losses):
        step=i+step0
        # stamps delivered: an act after the flush at window a stamps shift_at=a; the next check sees it
        shift_at=stamp
        bo=False; left=0
        if shift_at is not None:
            if g['shift_seen'] is None or g['shift_seen']!=shift_at: c['shift']+=1
            g['shift_seen']=shift_at
        if g['shift_seen'] is not None:
            since=step-g['shift_seen']
            if since<cool: bo=True; left=cool-since
        if bo and cool>0:
            prev=g['checked_at']
            fr=g['shift_seen'] if prev is None else max(prev,g['shift_seen'])
            c['bkW']+=max(0,step-fr)
        g['checked_at']=step
        g['n']+=1
        g['fast']=loss if g['fast'] is None else (1-FAST)*g['fast']+FAST*loss
        g['slow']=loss if g['slow'] is None else (1-SLOW)*g['slow']+SLOW*loss
        d=abs(loss-g['slow'])
        g['dev']=d if g['n']==1 else (1-MAD)*g['dev']+MAD*d
        imp=(g['slow']-g['fast'])/max(1e-6,abs(g['slow']))
        thr=z*max(1e-6,g['dev'])
        unexp=(loss-g['slow'])>thr
        askR=0
        if unexp:
            if bo: c['bsR']+=1
            elif g['last_regr'] is not None and step-g['last_regr']<cool: c['rcR']+=1
            else:
                askR=1; g['last']=g['last_regr']=g['t0']=step; g['state']='R'; c['aR']+=1; ev.append((step,'R'))
        if not askR:
            if g['state']=='R':
                s0=step-(g['t0'] if g['t0'] is not None else step)
                if s0>=rec_min and (abs(imp)<plateau or s0>rec_max): g['state']='W'
                c['rec']+=1
            elif bo: c['bsS']+=1
            elif g['last'] is not None and step-g['last']<cool: c['rcS']+=1
            elif step<warm: c['warm']+=1
            elif abs(imp)<plateau:
                c['aS']+=1; g['last']=g['t0']=step; g['state']='R'; ev.append((step,'S'))
        # the act fires after this flush's check
        while ai<len(acts) and acts[ai]==step:
            stamp=acts[ai]; ai+=1
    return c, ev, g
MAP=dict(aR='fab.grow_asked_regression',aS='fab.grow_asked_stall',bsR='fab.growth_blackout_suppressed.regression',
 bsS='fab.growth_blackout_suppressed.stall',rcR='fab.grow_regression_refused_cooldown',rcS='fab.grow_stall_refused_cooldown',
 rec='fab.grow_recover_passes',warm='fab.grow_warmup_refused',bkW='fab.blackout_windows',shift='fab.shift_notifications')
def cool_of(tag): return 100 if '_cd100' in tag else 400
if __name__=='__main__':
    fl=sys.argv[1] if len(sys.argv)>1 else 'H100'
    import glob
    allok=True
    for p in sorted(glob.glob(FL[fl]+'/logs/*.log')):
        tag=os.path.basename(p)[:-4]
        d,prog,acts=parse(p)
        L=json.load(open(FL[fl]+'/curves/'+tag+'.json'))
        c,ev,g=replay(L,acts,cool=cool_of(tag))
        mism=[]
        for k,key in MAP.items():
            logged=d.get(key)
            if logged is None:
                if k=='bkW' and c['bkW']==0: continue
                mism.append((k,c[k],'absent')); continue
            if int(float(logged))!=c[k]: mism.append((k,c[k],logged))
        ok=not mism; allok&=ok
        print('%-16s acts=%2d replay %s  %s'%(tag,len(acts),' '.join('%s=%d'%(k,c[k]) for k in ['aR','aS','bsR','bsS','rcR','rcS','bkW']),'MATCH' if ok else 'MISMATCH %s'%mism),
              ' dev %.6f vs %s'%(g['dev'],d.get('fab.grow_dev')))
    print('ALL MATCH' if allok else 'SOME MISMATCH')
