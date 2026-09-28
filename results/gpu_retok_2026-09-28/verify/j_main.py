"""Judge's independent re-read of the 2026-09-28 (H100) and 2026-09-27 (H200) retok fleets from the raw
per-flush curves and bytes, with the per-byte area labels replayed at 5c28ca4 (labels.s*.npy here).
Imports nothing from the repo. Run from this folder with OMP_NUM_THREADS=1."""
import json, math, os, sys
import numpy as np
from scipy import stats

S = '/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad'
FL = {'H100': S + '/retok0928/gpu_retok_out', 'H200': S + '/retok0927/gpu_retok_out'}
HERE = os.path.dirname(os.path.abspath(__file__))
CTX, TOTAL, NPH = 128, 3780000, 4
L2 = math.log(2)
BND = [round((j + 1) * TOTAL / NPH) for j in range(NPH)]
NAMES = ["eng", "py", "num", "c"]
SCHED = [(0, 1), (1, 2), (1, 2), (2, 3)]
CELLS = [(p, a) for p in range(NPH) for a in SCHED[p]]
SEEDS = {'H100': [0, 1, 2, 3, 4], 'H200': [0, 1, 2]}
_lab, _cum = {}, {}


def load(fl, arm, s):
    d = FL[fl] + '/curves'
    L = np.array(json.load(open(f'{d}/{arm}.s{s}.json')), dtype=np.float64)
    B = np.array(json.load(open(f'{d}/{arm}.s{s}.bytes.json')), dtype=np.float64)
    return L, B


def cum(s):
    if s not in _cum:
        lab = np.load(os.path.join(HERE, f'labels.s{s}.npy'))
        ph = np.minimum(np.searchsorted(np.array(BND), np.arange(len(lab)), side='right'), NPH - 1)
        cell = ph * 4 + lab.astype(np.int64)
        c = np.zeros((16, len(lab) + 1), dtype=np.int64)
        for k in range(16):
            c[k, 1:] = np.cumsum(cell == k)
        _cum[s] = c
    return _cum[s]


def reads(fl, arm, s, lo=0, hi=TOTAL):
    """phase bpb (flush placed by first byte), whole bpb, and per (phase, area) cell bpb with each flush's
    bits split by byte share; lo/hi restrict to flushes whose first byte is in [lo, hi)."""
    L, B = load(fl, arm, s)
    o1 = np.cumsum(B).astype(np.int64); o0 = o1 - B.astype(np.int64)
    bits = L * CTX / L2
    m = (o0 >= lo) & (o0 < hi)
    ph = np.minimum(np.searchsorted(np.array(BND), o0, side='right'), NPH - 1)
    phase = np.array([bits[(ph == p) & m].sum() / max(B[(ph == p) & m].sum(), 1) for p in range(NPH)])
    whole = bits[m].sum() / B[m].sum()
    c = cum(s)
    cnt = (c[:, o1] - c[:, o0]).astype(float) * m
    Ab = (cnt / B * bits).sum(1); Ay = cnt.sum(1)
    cell = {(p, a): (Ab[p * 4 + a] / Ay[p * 4 + a] if Ay[p * 4 + a] > 0 else float('nan')) for p, a in CELLS}
    area = {}
    for a in range(4):
        yy = sum(Ay[p * 4 + a] for p in range(NPH))
        area[a] = sum(Ab[p * 4 + a] for p in range(NPH)) / yy if yy > 0 else float('nan')
    return dict(phase=phase, whole=whole, cell=cell, area=area, n=len(L))


def bnd(d, lev_lo, ntest):
    d = np.asarray(d, dtype=float); n = len(d); m = d.mean(); se = d.std(ddof=1) / math.sqrt(n)
    return m, m - stats.t.ppf(1 - lev_lo / ntest, n - 1) * se, m + stats.t.ppf(0.95, n - 1) * se, d.std(ddof=1)


R = {}
for fl in FL:
    arms = ['k0', 'k1000', 'k0_nuis'] + (['k1000_cd100'] if fl == 'H100' else ['k3000'])
    for arm in arms:
        for s in SEEDS[fl]:
            R[(fl, arm, s)] = reads(fl, arm, s)

print('== whole-run bpb per seed (check against PASTE_BACK)')
for fl in FL:
    for arm in ['k0', 'k1000', 'k1000_cd100', 'k0_nuis', 'k3000']:
        if (fl, arm, 0) in R:
            print(f'  {fl} {arm:12}', ' '.join(f"{R[(fl, arm, s)]['whole']:.5f}" for s in SEEDS[fl]))

print('== the rule per phase, arm - ref (lower at t(1-a/4), upper one-sided 95%)')
for fl, arm, ref, a in [('H100', 'k1000', 'k0', 0.05), ('H100', 'k1000_cd100', 'k1000', 0.05),
                        ('H100', 'k0_nuis', 'k0', 0.05), ('H100', 'k1000', 'k0_nuis', 0.05),
                        ('H200', 'k1000', 'k0', 0.05), ('H200', 'k0_nuis', 'k0', 0.05)]:
    row = []
    verdict = 'PASS'
    for p in range(NPH):
        d = [R[(fl, arm, s)]['phase'][p] - R[(fl, ref, s)]['phase'][p] for s in SEEDS[fl]]
        m, lo, up, sd = bnd(d, a, 4)
        row.append(f'p{p+1} {m:+.4f} [{lo:+.4f},{up:+.4f}]')
        if lo > 0.05: verdict = 'FAIL'
        elif up > 0.05 and verdict != 'FAIL': verdict = 'UNRESOLVED'
    print(f'  {fl} {arm}-{ref}: ' + ' '.join(row) + f' -> {verdict}')

print('== per (phase, area) cell, arm - ref: mean [Bonferroni-8 lower at a=0.05; one-sided 95% upper]; per seed')
for fl, arm, ref in [('H100', 'k1000', 'k0'), ('H100', 'k1000_cd100', 'k1000'), ('H100', 'k0_nuis', 'k0'),
                     ('H200', 'k1000', 'k0'), ('H200', 'k3000', 'k0'), ('H200', 'k0_nuis', 'k0')]:
    print(f'  {fl} {arm}-{ref}')
    for p, a in CELLS:
        d = [R[(fl, arm, s)]['cell'][(p, a)] - R[(fl, ref, s)]['cell'][(p, a)] for s in SEEDS[fl]]
        m, lo, up, sd = bnd(d, 0.05, 8)
        verdict = 'FAIL' if lo > 0.05 else ('PASS' if up <= 0.05 else 'UNRES')
        print(f'    p{p+1}:{NAMES[a]:3} {m:+.4f} [{lo:+.4f},{up:+.4f}] sd {sd:.4f} {verdict:5} per seed ' +
              ' '.join(f'{x:+.4f}' for x in d))

print('== whole run per area, arm - ref [Bonferroni-4 lower; upper]')
for fl, arm, ref in [('H100', 'k1000', 'k0'), ('H200', 'k1000', 'k0'), ('H200', 'k3000', 'k0'),
                     ('H100', 'k0_nuis', 'k0')]:
    out = []
    for a in range(4):
        d = [R[(fl, arm, s)]['area'][a] - R[(fl, ref, s)]['area'][a] for s in SEEDS[fl]]
        m, lo, up, sd = bnd(d, 0.05, 4)
        out.append(f'{NAMES[a]} {m:+.4f} [{lo:+.4f},{up:+.4f}]')
    print(f'  {fl} {arm}-{ref}: ' + ' | '.join(out))

print('== late windows of the stream, arm - ref (whole-stream bpb over flushes starting in the window)')
for frac in (0.10, 0.05):
    lo = int(TOTAL * (1 - frac))
    for fl, arm, ref in [('H100', 'k1000', 'k0'), ('H200', 'k1000', 'k0'), ('H100', 'k1000_cd100', 'k1000'),
                         ('H100', 'k0_nuis', 'k0'), ('H200', 'k0_nuis', 'k0')]:
        d, dn = [], []
        for s in SEEDS[fl]:
            x = reads(fl, arm, s, lo=lo); y = reads(fl, ref, s, lo=lo)
            d.append(x['whole'] - y['whole']); dn.append(x['cell'][(3, 2)] - y['cell'][(3, 2)])
        m, lo_, up, sd = bnd(d, 0.05, 1)
        mn, lon, upn, sdn = bnd(dn, 0.05, 1)
        print(f'  last {int(frac*100)}% {fl} {arm}-{ref}: all {m:+.4f} [{lo_:+.4f},{up:+.4f}] sd {sd:.4f} per seed ' +
              ' '.join(f'{v:+.4f}' for v in d) + f' | num {mn:+.4f} [{lon:+.4f},{upn:+.4f}] per seed ' +
              ' '.join(f'{v:+.4f}' for v in dn))

print('== num in p4 by quarter of p4, k1000 - k0 (and k0_nuis - k0), per seed')
q = (TOTAL - BND[2]) / 4
for fl in FL:
    for arm, ref in [('k1000', 'k0'), ('k0_nuis', 'k0')]:
        rows = []
        for j in range(4):
            lo, hi = int(BND[2] + j * q), int(BND[2] + (j + 1) * q)
            d = [reads(fl, arm, s, lo, hi)['cell'][(3, 2)] - reads(fl, ref, s, lo, hi)['cell'][(3, 2)] for s in SEEDS[fl]]
            rows.append(f'Q{j+1} {np.mean(d):+.4f} (min {min(d):+.4f})')
        print(f'  {fl} {arm}-{ref} num p4: ' + '  '.join(rows))
