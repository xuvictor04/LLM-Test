import re, os, sys, glob
S='/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad'
FL={'H100':S+'/retok0928/gpu_retok_out','H200':S+'/retok0927/gpu_retok_out'}
KEYS=['fab.births','fab.spawned','fab.grown_regression','fab.grown_stall','fab.grow_asked_regression','fab.grow_asked_stall',
'fab.growth_blackout_suppressed.regression','fab.growth_blackout_suppressed.stall','fab.grow_regression_refused_cooldown',
'fab.grow_stall_refused_cooldown','fab.declined_newfrac','fab.declined_cap','fab.blackout_windows','fab.shift_notifications',
'fab.n_live','fab.merged','fab.cull_fail','fab.cull_util','fab.grow_recover_passes','fab.grow_dev','fab.spawn_declined',
'fab.newfrac_spent_on_spawn','fab.replicated','fab.manage_passes','fab.grow_warmup_refused','fab.grow_checks','fab.spared_shift','fab.crossed','fab.random_born']
def parse(path):
    d={}
    prog=[]
    acts=[]
    for line in open(path, errors='replace'):
        m=re.match(r'\s+(fab\.[\w\.]+)\s+(\S+)\s*$', line)
        if m and m.group(1) in KEYS:
            d[m.group(1)]=m.group(2)
        m=re.match(r'\[(\d+) windows\] loss=(\S+) opt_steps=\d+ n_live=(\d+) vocab=(\d+)', line)
        if m: prog.append((int(m.group(1)), float(m.group(2)), int(m.group(3)), int(m.group(4))))
        m=re.match(r'WARNING: loop: mid-epoch act at window (\d+)', line)
        if m: acts.append(int(m.group(1)))
        m=re.match(r'=== (\d+) windows, (\d+) flushes, .* in ([\d\.]+)s \(([\d\.]+) w/s\)', line)
        if m: d['_N']=int(m.group(1)); d['_secs']=float(m.group(3)); d['_wps']=float(m.group(4))
        m=re.search(r'startup took ([\d\.]+) s', line)
        if m: d['_startup']=float(m.group(1))
    return d, prog, acts
if __name__=='__main__':
    for fl in ['H200','H100']:
        print('=====',fl)
        logs=sorted(glob.glob(FL[fl]+'/logs/*.log'))
        cols=['fab.grown_regression','fab.grown_stall','fab.grow_asked_regression','fab.grow_asked_stall','fab.growth_blackout_suppressed.regression','fab.growth_blackout_suppressed.stall','fab.grow_regression_refused_cooldown','fab.grow_stall_refused_cooldown','fab.declined_newfrac','fab.declined_cap','fab.births','fab.spawned','fab.replicated','fab.blackout_windows','fab.shift_notifications','fab.n_live','fab.grow_dev','fab.merged','fab.cull_fail','fab.cull_util','fab.spared_shift']
        short=['gR','gS','aR','aS','bsR','bsS','rcR','rcS','dNF','dCap','births','spawn','repl','bkW','shift','nlive','dev','merged','cfail','cutil','sprdSh']
        print('%-18s'%'run'+' '.join('%7s'%s for s in short)+'  N  secs wps fill')
        for p in logs:
            tag=os.path.basename(p)[:-4]
            d,prog,acts=parse(p)
            fill=next((w for w,l,n,v in prog if n>=4096),None)
            print('%-18s'%tag+' '.join('%7s'%d.get(k,'-')[:7] for k in cols)+'  %s %s %s %s'%(d.get('_N'),d.get('_secs'),d.get('_wps'),fill))
