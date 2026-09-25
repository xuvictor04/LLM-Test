"""Second media area, aud/melody: four-note melodies with KNOWN parameters and an analytic probe.

Attributes: contour in {up, down, arch, valley}; register in {low, high}; timbre in {pure, reed}.
16 combinations, HELDOUT_B never appear in training. 'reed' = odd harmonics only (square-like), a
spectral pattern the aud/tones area does not contain; note changes every ~0.2 s are also new.
"""
import math, re
import torch
import synth as S

SR = S.SR
CONTOURS = {"up": [0, 4, 8, 12], "down": [12, 8, 4, 0], "arch": [0, 7, 12, 5], "valley": [12, 5, 0, 7]}
REGS = {"low": (200, 280), "high": (450, 600)}
TIMBRES = ["pure", "reed"]
CW = {"up": "going up", "down": "going down", "arch": "rising then falling", "valley": "falling then rising"}
WC = {v: k for k, v in CW.items()}


def all_combos():
    return [(c, r, t) for c in CONTOURS for r in REGS for t in TIMBRES]


HELDOUT = [("arch", "high", "reed"), ("down", "low", "pure")]
TRAIN = [c for c in all_combos() if c not in HELDOUT]


def caption(p):
    c, r, t = p
    return f"a {r} {t} melody {CW[c]}"


def parse_caption(s):
    m = re.fullmatch(r"a (low|high) (pure|reed) melody (going up|going down|rising then falling|falling then rising)", s.strip())
    if not m:
        return None
    return (WC[m.group(3)], m.group(1), m.group(2))


def _osc(f, timbre, n):
    ph = 2 * math.pi * torch.cumsum(torch.full((n,), float(f)), 0) / SR
    if timbre == "pure":
        return torch.sin(ph)
    out = torch.zeros(n)
    for k in (1, 3, 5, 7, 9):
        if k * f < SR / 2 - 100:
            out += (1.0 / k) * torch.sin(k * ph)
    return out / 1.2


def render(p, g, dur=1.0):
    c, r, t = p
    n = int(SR * dur); x = torch.zeros(n)
    lo, hi = REGS[r]
    root = lo + (hi - lo) * torch.rand(1, generator=g).item()
    amp = 0.3 + 0.6 * torch.rand(1, generator=g).item()
    L = int(SR * (0.15 + 0.04 * torch.rand(1, generator=g).item()))
    gap = int(SR * (0.04 + 0.02 * torch.rand(1, generator=g).item()))
    span = 4 * L + 3 * gap
    pos = int((n - span) * torch.rand(1, generator=g).item())
    for st in CONTOURS[c]:
        f = root * 2 ** (st / 12)
        x[pos:pos + L] += _osc(f, t, L) * S._env(L, g)
        pos += L + gap
    x = amp * x
    if torch.rand(1, generator=g).item() < 0.3:
        x += 0.005 * torch.randn(n, generator=g)
    return x.clamp(-1, 1)


def sample(g, combos=TRAIN):
    p = combos[int(torch.randint(len(combos), (1,), generator=g))]
    return p, render(p, g)


_W = torch.hann_window(512)


def probe(x):
    X = torch.stft(x, 512, 128, window=_W, return_complex=True).abs()
    e = X.pow(2).sum(0)
    if e.max() <= 1e-8:
        return ("up", "low", "pure")
    act = e > 0.08 * e.max()
    runs = []; i = 0
    while i < len(act):
        if act[i]:
            j = i
            while j < len(act) and act[j]:
                j += 1
            if j - i >= 2:
                runs.append((i, j))
            i = j
        else:
            i += 1
    if not runs:
        runs = [(int(e.argmax()), int(e.argmax()) + 1)]
    hz = SR / 512
    notes = []; hf = []
    for (a, b) in runs:
        ps = []
        for tt in range(a, b):
            s = X[:, tt]
            cand = torch.arange(8, 160)
            sc = s[cand] + 0.5 * s[(2 * cand).clamp(max=256)] + 0.33 * s[(3 * cand).clamp(max=256)]
            b0 = int(cand[sc.argmax()])
            ps.append(b0 * hz)
            p2 = s.pow(2); fund = p2[max(0, b0 - 3):b0 + 4].sum()
            hf.append(float(1 - fund / (p2.sum() + 1e-12)))
        notes.append(float(torch.tensor(ps).median()))
    med = float(torch.tensor(notes).median())
    reg = "low" if med < 520 else "high"
    timbre = "reed" if float(torch.tensor(hf).median()) > 0.05 else "pure"
    if len(notes) < 2:
        return ("up", reg, timbre)
    d = [1 if notes[k + 1] > notes[k] else -1 for k in range(len(notes) - 1)]
    if all(v > 0 for v in d):
        c = "up"
    elif all(v < 0 for v in d):
        c = "down"
    else:
        # first direction then the other
        c = "arch" if d[0] > 0 else "valley"
    return (c, reg, timbre)


def attr_acc(pred, true):
    if pred is None:
        return dict(contour=0, register=0, timbre=0, exact=0)
    d = dict(contour=int(pred[0] == true[0]), register=int(pred[1] == true[1]), timbre=int(pred[2] == true[2]))
    d["exact"] = int(all(d.values()))
    return d


if __name__ == "__main__":
    g = torch.Generator().manual_seed(7)
    tot = {}; n = 0
    for p in all_combos():
        for _ in range(20):
            x = render(p, g)
            d = attr_acc(probe(x), p); n += 1
            for k, v in d.items():
                tot[k] = tot.get(k, 0) + v
            if not d["exact"]:
                print("miss", p, probe(x))
    print({k: round(v / n, 3) for k, v in tot.items()}, n)
    print(caption(("arch", "high", "reed")), parse_caption(caption(("arch", "high", "reed"))))
