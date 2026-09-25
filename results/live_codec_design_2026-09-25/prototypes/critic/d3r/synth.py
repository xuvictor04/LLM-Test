"""Paired synthetic audio+caption generator with KNOWN parameters, and an analytic
parameter-recovery probe (no learned model), so understanding and generation are scored exactly.

Attributes: kind in {tone, rise, fall, beeps}; band in {low, mid, high}; timbre in {pure, buzzy};
count in {2,3,4} for beeps. 36 combinations; HELDOUT_COMBOS never appear in training.
"""
import math, re
import torch

SR = 8000
BANDS = {"low": (180, 260), "mid": (450, 650), "high": (1100, 1500)}
KINDS = ["tone", "rise", "fall", "beeps"]
TIMBRES = ["pure", "buzzy"]
COUNTS = [2, 3, 4]
NUMW = {2: "two", 3: "three", 4: "four"}
WNUM = {v: k for k, v in NUMW.items()}
KW = {"tone": "tone", "rise": "rising chirp", "fall": "falling chirp"}


def all_combos():
    out = []
    for k in KINDS:
        for b in BANDS:
            for t in TIMBRES:
                if k == "beeps":
                    out += [(k, b, t, c) for c in COUNTS]
                else:
                    out.append((k, b, t, 0))
    return out


HELDOUT_COMBOS = [("rise", "high", "buzzy", 0), ("fall", "mid", "pure", 0),
                  ("beeps", "low", "pure", 3), ("beeps", "high", "buzzy", 2)]
TRAIN_COMBOS = [c for c in all_combos() if c not in HELDOUT_COMBOS]


def caption(p):
    k, b, t, c = p
    if k == "beeps":
        return f"{NUMW[c]} {b} {t} beeps"
    return f"a {b} {t} {KW[k]}"


def parse_caption(s):
    s = s.strip()
    m = re.fullmatch(r"(two|three|four) (low|mid|high) (pure|buzzy) beeps", s)
    if m:
        return ("beeps", m.group(2), m.group(3), WNUM[m.group(1)])
    m = re.fullmatch(r"a (low|mid|high) (pure|buzzy) (tone|rising chirp|falling chirp)", s)
    if m:
        k = {"tone": "tone", "rising chirp": "rise", "falling chirp": "fall"}[m.group(3)]
        return (k, m.group(1), m.group(2), 0)
    return None


def _osc(f_t, timbre, n):
    ph = 2 * math.pi * torch.cumsum(f_t, 0) / SR
    if timbre == "pure":
        return torch.sin(ph)
    out = torch.zeros(n)
    for k in range(1, 8):
        out += (1.0 / k) * torch.sin(k * ph) * (k * f_t < SR / 2 - 100).float()
    return out / 1.6


def _env(n, g):
    a = max(1, int(SR * 0.01)); r = max(1, int(SR * 0.02))
    e = torch.ones(n)
    e[:a] = torch.linspace(0, 1, a); e[-r:] = torch.linspace(1, 0, r)
    return e


def render(p, g, dur=1.0):
    k, b, t, c = p
    n = int(SR * dur); x = torch.zeros(n)
    lo, hi = BANDS[b]
    f0 = lo + (hi - lo) * torch.rand(1, generator=g).item()
    amp = 0.3 + 0.6 * torch.rand(1, generator=g).item()
    if k == "beeps":
        L = int(SR * (0.10 + 0.04 * torch.rand(1, generator=g).item()))
        gap = int(SR * (0.08 + 0.04 * torch.rand(1, generator=g).item()))
        span = c * L + (c - 1) * gap
        pos = int((n - span) * torch.rand(1, generator=g).item())
        for _ in range(c):
            seg = _osc(torch.full((L,), f0), t, L) * _env(L, g)
            x[pos:pos + L] += seg; pos += L + gap
    else:
        on = int(SR * (0.03 + 0.12 * torch.rand(1, generator=g).item()))
        off = int(SR * (0.80 + 0.15 * torch.rand(1, generator=g).item()))
        L = off - on
        if k == "tone":
            f = torch.full((L,), f0)
        elif k == "rise":
            f = f0 * 1.5 ** torch.linspace(0, 1, L)
        else:
            f = f0 * 1.5 ** torch.linspace(1, 0, L)
        x[on:off] = _osc(f, t, L) * _env(L, g)
    x = amp * x
    if torch.rand(1, generator=g).item() < 0.3:
        x += 0.005 * torch.randn(n, generator=g)
    return x.clamp(-1, 1)


def sample(g, combos=TRAIN_COMBOS, dur=1.0):
    p = combos[int(torch.randint(len(combos), (1,), generator=g))]
    return p, render(p, g, dur)


# ------------------------------------------------------------------ analytic probe
_W = torch.hann_window(512)


def probe(x):
    """Recover (kind, band, timbre, count) from a waveform with fixed signal processing."""
    X = torch.stft(x, 512, 128, window=_W, return_complex=True).abs()  # (257, T)
    e = X.pow(2).sum(0)
    if e.max() <= 1e-8:
        return ("tone", "low", "pure", 0)
    act = e > 0.08 * e.max()
    # merge 1-frame gaps, drop 1-frame blips; count runs
    a = act.clone()
    for i in range(1, len(a) - 1):
        if not a[i] and a[i - 1] and a[i + 1]:
            a[i] = True
    runs = []; i = 0
    while i < len(a):
        if a[i]:
            j = i
            while j < len(a) and a[j]:
                j += 1
            if j - i >= 2:
                runs.append((i, j))
            i = j
        else:
            i += 1
    frames = [t for (i, j) in runs for t in range(i, j)]
    if not frames:
        frames = [int(e.argmax())]
    hz = SR / 512
    # harmonic-sum pitch: score each candidate f0 bin by sum of X at k*f0 (k=1..3), fundamental-weighted
    pitches = []; hfrac = []
    for tt in frames:
        s = X[:, tt]
        cand = torch.arange(8, 160)  # 125..2500 Hz
        sc = s[cand] + 0.5 * s[(2 * cand).clamp(max=256)] + 0.33 * s[(3 * cand).clamp(max=256)]
        b0 = int(cand[sc.argmax()])
        # refine: parabolic
        pitches.append(b0 * hz)
        p2 = s.pow(2)
        fund = p2[max(0, b0 - 3):b0 + 4].sum()
        hfrac.append(float(1 - fund / (p2.sum() + 1e-12)))
    pit = torch.tensor(pitches)
    lp = torch.log2(pit)
    p10 = float(torch.quantile(pit, 0.1))
    band = "low" if p10 < 350 else ("mid" if p10 < 900 else "high")
    timbre = "buzzy" if float(torch.tensor(hfrac).median()) > 0.15 else "pure"
    if len(runs) >= 2:
        return ("beeps", band, timbre, int(min(4, max(2, len(runs)))))
    tsec = torch.tensor(frames, dtype=torch.float32) * 128 / SR
    if len(frames) >= 3:
        tc = tsec - tsec.mean()
        slope = float((tc * (lp - lp.mean())).sum() / (tc.pow(2).sum() + 1e-9))
    else:
        slope = 0.0
    kind = "rise" if slope > 0.25 else ("fall" if slope < -0.25 else "tone")
    return (kind, band, timbre, 0)


def attr_acc(pred, true):
    """Per-attribute match dict and exact match."""
    if pred is None:
        return dict(kind=0, band=0, timbre=0, count=0, exact=0)
    d = dict(kind=int(pred[0] == true[0]), band=int(pred[1] == true[1]), timbre=int(pred[2] == true[2]),
             count=int(pred[3] == true[3]))
    d["exact"] = int(all(d.values()))
    return d


if __name__ == "__main__":
    g = torch.Generator().manual_seed(7)
    tot = {}; n = 0
    for p in all_combos():
        for _ in range(10):
            x = render(p, g)
            d = attr_acc(probe(x), p); n += 1
            for k, v in d.items():
                tot[k] = tot.get(k, 0) + v
            if not d["exact"]:
                print("miss", p, probe(x))
    print({k: round(v / n, 3) for k, v in tot.items()}, n)
    print(caption(("beeps", "low", "pure", 3)), parse_caption(caption(("beeps", "low", "pure", 3))))
