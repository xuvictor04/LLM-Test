"""The record's own checks of the figures RESULTS.md gives that the judge's scripts do not print: the noise
spread against independent flushes, the leave-one-out, pooled and k0_nuis-control readings of the rule,
1000 - 3000 after the loss drop, dev/slow, where the act's own regression readings end, the heartbeat's
rate and the ETA by windows run. Imports nothing from the repo; the per-run SD of num over the last 10% is
taken from j_main.out's per-seed values (the labels it needs are not kept). Run from this folder, with
OMP_NUM_THREADS=1 and growth/ on the path."""
import glob, json, math, os, re, sys
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "growth"))
from counters import parse                                          # noqa: E402
from replay import FAST, SLOW, MAD                                   # noqa: E402

S = '/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad'
FL = {'H100': S + '/retok0928/gpu_retok_out', 'H200': S + '/retok0927/gpu_retok_out'}
SEEDS = {'H100': [0, 1, 2, 3, 4], 'H200': [0, 1, 2]}
T, L2, EPS = 3780000, math.log(2), 0.05
BND = [round((j + 1) * T / 4) for j in range(4)]


def load(fl, a, s):
    d = FL[fl] + '/curves'
    return (np.array(json.load(open(f'{d}/{a}.s{s}.json'))),
            np.array(json.load(open(f'{d}/{a}.s{s}.bytes.json')), float))


def phases(fl, a, s, lo=0):
    L, B = load(fl, a, s)
    o0 = np.cumsum(B) - B
    ph = np.minimum(np.searchsorted(np.array(BND), o0, side='right'), 3)
    bits, m = L * 128 / L2, o0 >= lo
    return np.array([bits[(ph == p) & m].sum() / B[(ph == p) & m].sum() for p in range(4)]), bits[m].sum() / B[m].sum()


def rule(per):
    rows, v = [], 'PASS'
    for x in per:
        x = np.asarray(x); n = len(x); m = x.mean(); se = x.std(ddof=1) / math.sqrt(n)
        lo, up = m - stats.t.ppf(1 - 0.05 / 4, n - 1) * se, m + stats.t.ppf(0.95, n - 1) * se
        rows.append(f'{m:+.4f} [{lo:+.4f},{up:+.4f}]')
        v = 'FAIL' if lo > EPS or v == 'FAIL' else ('UNRESOLVED' if up > EPS else v)
    return ' '.join(f'p{i + 1} {r}' for i, r in enumerate(rows)) + f' -> {v}'


print('== the between-run spread against the SE independent flushes would give (k0_nuis - k0, 8 pairs)')
D = {k: [] for k in ['p1', 'p2', 'p3', 'p4', 'whole']}
for fl in FL:
    for s in SEEDS[fl]:
        La, B = load(fl, 'k0', s); Lb, _ = load(fl, 'k0_nuis', s)
        ph = np.minimum(np.searchsorted(np.array(BND), np.cumsum(B) - B, side='right'), 3)
        for k, m in [(f'p{p + 1}', ph == p) for p in range(4)] + [('whole', np.ones(len(B), bool))]:
            da, b = (Lb[m] - La[m]) * 128 / L2, B[m]
            diff = da.sum() / b.sum()
            D[k].append((diff, (da - diff * b).std(ddof=1) * math.sqrt(m.sum()) / b.sum()))
for k, v in D.items():
    d, se = np.array([x for x, _ in v]), np.array([y for _, y in v])
    print(f'  {k:5}: pair SD {d.std(ddof=1):.4f} (rms {math.sqrt(np.mean(d ** 2)):.4f}); independent-flush SE '
          f'{se.mean():.5f}: SD/SE {d.std(ddof=1) / se.mean():.1f}, rms/SE {math.sqrt(np.mean(d ** 2)) / se.mean():.1f}')

print('== per-run SD of num over the last 10% (j_main.out, k0_nuis - k0 per seed, / sqrt 2)')
jm = open(os.path.join(HERE, 'j_main.out')).read()
for fl in FL:
    m = re.search(rf'last 10% {fl} k0_nuis-k0: .*\| num \S+ \[\S+\] per seed (.*)$', jm, re.M)
    d = np.array([float(x) for x in m.group(1).split()])
    print(f'  {fl}: SD {d.std(ddof=1) / math.sqrt(2):.4f}, rms {math.sqrt(np.mean(d ** 2)) / math.sqrt(2):.4f}')

print('== the rule on k1000 - k0 per phase: leave one seed out (H100), pooled over 8 pairs, and k0_nuis as control')
P = {(fl, a, s): phases(fl, a, s) for fl in FL for a in ['k0', 'k1000', 'k0_nuis'] for s in SEEDS[fl]}
for drop in SEEDS['H100']:
    ss = [s for s in SEEDS['H100'] if s != drop]
    print(f'  without s{drop}: ' + rule([[P[('H100', 'k1000', s)][0][p] - P[('H100', 'k0', s)][0][p] for s in ss] for p in range(4)]))
print('  pooled 8: ' + rule([[P[(fl, 'k1000', s)][0][p] - P[(fl, 'k0', s)][0][p] for fl in FL for s in SEEDS[fl]] for p in range(4)]))
print('  H100 k1000 - k0_nuis: ' + rule([[P[('H100', 'k1000', s)][0][p] - P[('H100', 'k0_nuis', s)][0][p] for s in SEEDS['H100']] for p in range(4)]))

print('== H200 1000 - 3000 over the whole run and from 0.756 MB (20% of the stream) on')
w = np.array([phases('H200', 'k1000', s)[1] - phases('H200', 'k3000', s)[1] for s in SEEDS['H200']])
p1 = np.array([phases('H200', 'k1000', s)[0][0] - phases('H200', 'k3000', s)[0][0] for s in SEEDS['H200']])
a = np.array([phases('H200', 'k1000', s, 756000)[1] - phases('H200', 'k3000', s, 756000)[1] for s in SEEDS['H200']])
print(f'  whole {w.mean():+.4f}, share from p1 (p1/4) {p1.mean() / 4 / w.mean():.3f}; from 0.756 MB {a.mean():+.4f}, '
      f'upper {a.mean() + stats.t.ppf(0.95, 2) * a.std(ddof=1) / math.sqrt(3):+.4f}')

print('== fab.grow_dev / fab.grow_slow at the end, mean over runs')
for fl, d in FL.items():
    R = {}
    for f in sorted(glob.glob(d + '/logs/*.log')):
        t = open(f).read()
        g = lambda k: float(re.search(r'^\s+' + re.escape(k) + r'\s+(\S+)\s*$', t, re.M).group(1))
        R[os.path.basename(f)[:-4]] = g('fab.grow_dev') / g('fab.grow_slow')
    print(f'  {fl}: ' + ', '.join(f"{arm} {np.mean([v for k, v in R.items() if k.split('.')[0] == arm]):.3f}"
                              for arm in ['k0', 'k0_nuis', 'k1000', 'k1000_cd100', 'k3000']
                              if any(k.split('.')[0] == arm for k in R)))

print('== the act\'s own regression readings (trigger true, not within 30 windows of a phase entry): the latest, in windows after its act')
for arm in ['k1000', 'k1000_cd100']:
    late = []
    for s in SEEDS['H100']:
        tag = f'{arm}.s{s}'
        _, _, acts = parse(f"{FL['H100']}/logs/{tag}.log")
        L, B = load('H100', arm, s)
        off = np.concatenate([[0], np.cumsum(B)[:-1]])
        PH = [int(np.searchsorted(off, b, side='left')) + 1 for b in BND[:3]]
        n = 0; fast = slow = dev = None; out = []
        for i, loss in enumerate(L):
            step = i + 1; n += 1
            fast = loss if fast is None else (1 - FAST) * fast + FAST * loss
            slow = loss if slow is None else (1 - SLOW) * slow + SLOW * loss
            dd = abs(loss - slow); dev = dd if n == 1 else (1 - MAD) * dev + MAD * dd
            if (loss - slow) > 4.0 * max(1e-6, dev):
                p = [x for x in acts if x < step]
                if p and step - max(p) < 400 and not any(0 <= step - q + 1 <= 30 for q in PH):
                    out.append(step - max(p))
        late.append(max(out))
    print(f'  {arm}: per run {late}')

print('== the heartbeat while all 21 trained, and the ETA by the windows actually run')
hb = open(FL['H100'] + '/heartbeat.log').read()
r = [float(x) for x in re.findall(r'21 training .*? windows, ([\d.]+) w/s', hb)]
print(f'  {len(r)} heartbeats, {min(r):.1f}-{max(r):.1f} windows/s')
tw = sum(len(json.load(open(f))) for f in glob.glob(FL['H100'] + '/curves/*.s[0-9].json'))
print(f'  {tw} windows run; at the calibrated 416.404 that is {tw / 416.404:.0f} s against the 1084 s wall: '
      f'{1084 / (tw / 416.404):.3f}x (the block: 420,000 nominal windows, 1.07x)')
