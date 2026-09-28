"""Judge: divergence points, early-drop timing, nuisance SDs and the rule's power under the null."""
import json, math, os
import numpy as np
from scipy import stats
S = '/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad'
FL = {'H100': S + '/retok0928/gpu_retok_out', 'H200': S + '/retok0927/gpu_retok_out'}
TOTAL, NPH, CTX, L2 = 3780000, 4, 128, math.log(2)
BND = [round((j + 1) * TOTAL / NPH) for j in range(NPH)]
SEEDS = {'H100': [0, 1, 2, 3, 4], 'H200': [0, 1, 2]}


def load(fl, arm, s):
    d = FL[fl] + '/curves'
    return (np.array(json.load(open(f'{d}/{arm}.s{s}.json')), dtype=np.float64),
            np.array(json.load(open(f'{d}/{arm}.s{s}.bytes.json')), dtype=np.float64))


def first_diff(a, b):
    n = min(len(a), len(b))
    i = np.nonzero(a[:n] != b[:n])[0]
    return int(i[0]) if len(i) else None


print('== first differing flush index (0-based) of the loss curves')
for fl in FL:
    for x, y in [('k0', 'k0_nuis'), ('k0', 'k1000'), ('k1000', 'k1000_cd100'), ('k0', 'k3000')]:
        out = []
        for s in SEEDS[fl]:
            try:
                La, _ = load(fl, x, s); Lb, _ = load(fl, y, s)
            except FileNotFoundError:
                continue
            out.append(first_diff(La, Lb))
        if out:
            print(f'  {fl} {x} vs {y}: {out}')
print('  cross-card k0 (H100 vs H200) flush 0 |dL|:',
      [f"{abs(load('H100','k0',s)[0][0]-load('H200','k0',s)[0][0]):.2e}" for s in range(3)],
      'first diff', [first_diff(load('H100','k0',s)[0], load('H200','k0',s)[0]) for s in range(3)])
print('  cross-card bytes identical per flush (k0):', [bool(np.array_equal(load('H100','k0',s)[1], load('H200','k0',s)[1])) for s in range(3)])


def crossing(L, B, thr=2.5, w=50):
    bits = L * CTX / L2
    cb = np.concatenate([[0], np.cumsum(bits)]); cy = np.concatenate([[0], np.cumsum(B)])
    r = (cb[w:] - cb[:-w]) / (cy[w:] - cy[:-w])
    i = np.nonzero(r < thr)[0]
    return (int(i[0] + w - 1), int(cy[i[0] + w])) if len(i) else (None, None)


def phases(L, B):
    o0 = np.cumsum(B) - B
    ph = np.minimum(np.searchsorted(np.array(BND), o0, side='right'), NPH - 1)
    bits = L * CTX / L2
    return np.array([bits[ph == p].sum() / B[ph == p].sum() for p in range(NPH)]), bits.sum() / B.sum()


print('== early loss drop: flush where the 50-flush rolling bits/byte first falls below 2.5 (k0 family)')
cross, p1v, wv, tag = [], [], [], []
for fl in FL:
    for arm in ['k0', 'k0_nuis']:
        for s in SEEDS[fl]:
            L, B = load(fl, arm, s)
            c, by = crossing(L, B)
            ph, wh = phases(L, B)
            cross.append(c); p1v.append(ph[0]); wv.append(wh); tag.append((fl, arm, s))
            print(f'  {fl} {arm:8} s{s}: crossing flush {c} (byte {by}); p1 {ph[0]:.4f} whole {wh:.5f}')
c = np.array(cross, float)
others = [x for x, t in zip(cross, tag) if not (t == ('H100', 'k0', 1))]
print(f'  k0.s1 H100 crossing {cross[tag.index(("H100","k0",1))]}; the other {len(others)}: {min(others)}-{max(others)}, '
      f'mean {np.mean(others):.0f} sd {np.std(others, ddof=1):.0f}; z {(cross[tag.index(("H100","k0",1))]-np.mean(others))/np.std(others, ddof=1):.1f}')

print('== nuisance pairs k0_nuis - k0 per phase and whole run (8 pairs: 5 H100 + 3 H200)')
D = []
for fl in FL:
    for s in SEEDS[fl]:
        a = phases(*load(fl, 'k0', s)); b = phases(*load(fl, 'k0_nuis', s))
        D.append(list(b[0] - a[0]) + [b[1] - a[1]])
D = np.array(D)
for j, nm in enumerate(['p1', 'p2', 'p3', 'p4', 'whole']):
    d = D[:, j]
    rms = math.sqrt(np.mean(d ** 2))
    print(f'  {nm}: pair diffs ' + ' '.join(f'{x:+.4f}' for x in d) + f' | sd {np.std(d, ddof=1):.4f} rms {rms:.4f} '
          f'per-run {rms/math.sqrt(2):.4f}; H100 only sd {np.std(d[:5], ddof=1):.4f}')
# contribution of each phase to seed 1's whole-run |k0 - k0_nuis| on H100 (equal byte ranges: whole ~ mean of phases)
a = phases(*load('H100', 'k0', 1)); b = phases(*load('H100', 'k0_nuis', 1))
print('  H100 s1 k0 - k0_nuis per phase', ' '.join(f'{x:+.4f}' for x in a[0] - b[0]), 'whole', f'{a[1]-b[1]:+.5f}',
      'phase/4 contributions', ' '.join(f'{x/4:+.4f}' for x in a[0] - b[0]))

print('== the rule under the null for an arm diverging at window 1 (P(PASS per phase), simulated from the pooled pair sd)')
rng = np.random.default_rng(0)
for nm, sd in [('p1', np.sqrt(np.mean(D[:, 0] ** 2))), ('whole', np.sqrt(np.mean(D[:, 4] ** 2)))]:
    for n in (3, 5, 8, 10):
        x = rng.normal(0, sd, size=(200000, n))
        m = x.mean(1); se = x.std(1, ddof=1) / math.sqrt(n)
        pp = np.mean(m + stats.t.ppf(0.95, n - 1) * se <= 0.05)
        print(f'  {nm} sd {sd:.4f} n {n}: P(upper <= eps) {pp:.2f}')
