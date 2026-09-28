"""Judge: FAB counters and pool reads from every log of both fleets (no repo import)."""
import re, os, glob, json
import numpy as np
S = '/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad'
FL = {'H100': S + '/retok0928/gpu_retok_out', 'H200': S + '/retok0927/gpu_retok_out'}
KEYS = ['fab.n_live', 'fab.births', 'fab.spawned', 'fab.grown_regression', 'fab.grown_stall', 'fab.grow_asked_regression',
        'fab.grow_asked_stall', 'fab.blackout_windows', 'fab.growth_blackout_suppressed.regression',
        'fab.growth_blackout_suppressed.stall', 'fab.grow_regression_refused_cooldown', 'fab.grow_stall_refused_cooldown',
        'fab.grow_dev', 'fab.grow_slow', 'fab.grow_fast', 'fab.shift_notifications', 'loop.acts']
rows = {}
for fl, d in FL.items():
    for f in sorted(glob.glob(d + '/logs/*.log')):
        tag = os.path.basename(f)[:-4]
        txt = open(f).read()
        r = {}
        for k in KEYS:
            m = re.search(r'^\s+' + re.escape(k) + r'\s+(\S+)\s*$', txt, re.M)
            r[k] = float(m.group(1)) if m else None
        prog = [(int(a), int(b)) for a, b in re.findall(r'^\[(\d+) windows\].*?n_live=(\d+)', txt, re.M)]
        slots = re.search(r'FAB_SLOTS=(\d+)', txt)
        full = next((w for w, n in prog if n >= 4096), None)
        acts = [int(x) for x in re.findall(r'mid-epoch act at window (\d+)', txt)]
        r['full_at'] = full; r['acts_w'] = acts; r['last_prog'] = prog[-1] if prog else None
        rows[(fl, tag)] = r

print('fleet tag              n_live_end full_at births grown r/s asked r/s blackout supp r/s refusedCD r/s dev/slow')
for (fl, tag), r in rows.items():
    g = lambda k: r[k]
    ratio = (g('fab.grow_dev') / g('fab.grow_slow')) if g('fab.grow_dev') and g('fab.grow_slow') else None
    print(f"{fl} {tag:18} {g('fab.n_live'):6.0f} {str(r['full_at']):>7} {g('fab.births'):6.0f} "
          f"{g('fab.grown_regression'):3.0f}/{g('fab.grown_stall'):3.0f} {g('fab.grow_asked_regression'):3.0f}/{g('fab.grow_asked_stall'):3.0f} "
          f"{g('fab.blackout_windows') if g('fab.blackout_windows') is not None else '-':>6} "
          f"{g('fab.growth_blackout_suppressed.regression'):4.0f}/{g('fab.growth_blackout_suppressed.stall'):5.0f} "
          f"{g('fab.grow_regression_refused_cooldown'):3.0f}/{g('fab.grow_stall_refused_cooldown'):3.0f} "
          f"dev {g('fab.grow_dev'):.3f} slow {g('fab.grow_slow'):.3f} dev/slow {ratio:.4f} acts {len(r['acts_w'])} first {r['acts_w'][:2]}")

# per arm means
print()
for fl in FL:
    arms = sorted(set(t.split('.')[0] for (f, t) in rows if f == fl))
    for arm in arms:
        rs = [r for (f, t), r in rows.items() if f == fl and t.split('.')[0] == arm]
        m = lambda k: np.mean([r[k] for r in rs])
        print(f"{fl} {arm:12} n={len(rs)} births {m('fab.births'):.1f} grown {m('fab.grown_regression'):.1f}/{m('fab.grown_stall'):.1f} "
              f"asked {m('fab.grow_asked_regression'):.1f}/{m('fab.grow_asked_stall'):.1f} n_live_end {m('fab.n_live'):.0f} "
              f"[{min(r['fab.n_live'] for r in rs):.0f}-{max(r['fab.n_live'] for r in rs):.0f}] full {sum(1 for r in rs if r['full_at'])} "
              f"supp {m('fab.growth_blackout_suppressed.regression'):.1f}/{m('fab.growth_blackout_suppressed.stall'):.1f} "
              f"refCD {m('fab.grow_regression_refused_cooldown'):.1f}/{m('fab.grow_stall_refused_cooldown'):.1f}")
free = [4096 - r['fab.n_live'] for (f, t), r in rows.items()]
print('free slots at end over all', len(free), 'runs: min', min(free), 'max', max(free))
for fl in FL:
    fr = sorted((4096 - r['fab.n_live'], t) for (f, t), r in rows.items() if f == fl)
    print(fl, 'free at end (lowest 3, highest 1):', fr[:3], fr[-1])
