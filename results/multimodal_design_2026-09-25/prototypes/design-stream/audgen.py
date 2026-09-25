"""Captioned synthetic audio (8 kHz, 1 s clips). Every clip carries its generating parameters and a
caption rendered from the discrete ones. 16 caption classes. Deterministic per (seed, index)."""
import math, torch
SR = 8000; N = SR  # 1 s
VOW = {"a": [(730, 90, 1.0), (1090, 110, 0.5), (2440, 160, 0.25)],
       "i": [(270, 60, 1.0), (2290, 150, 0.4), (3010, 200, 0.3)],
       "u": [(300, 60, 1.0), (870, 90, 0.5), (2240, 160, 0.2)]}
BANDS = {"low": (150, 300), "mid": (400, 800), "high": (1000, 2000)}
CLASSES = (["tone low", "tone mid", "tone high", "chirp up", "chirp down"]
           + [f"{k} beeps {b}" for k in (2, 3, 4) for b in ("low", "high")]
           + ["vowel a", "vowel i", "vowel u", "notes rising", "notes falling"])

def _u(g, a, b): return a + (b - a) * torch.rand(1, generator=g).item()
def _env(n, att=0.01, rel=0.05):
    t = torch.arange(n, dtype=torch.float32) / SR
    return torch.clamp(t / att, max=1) * torch.clamp((n / SR - t) / rel, max=1)
def _harm(n, f0, formants=None):
    t = torch.arange(n) / SR; out = torch.zeros(n); k = 1
    while k * f0 < 3800:
        f = k * f0
        amp = 1.0 / k if formants is None else sum(a * math.exp(-((f - fc) / bw) ** 2) for fc, bw, a in formants) + 0.02 / k
        out += amp * torch.sin(2 * math.pi * f * t); k += 1
    return out / (out.abs().max() + 1e-6)

def clip(cls, g):
    name = CLASSES[cls]; w = name.split(); n = N; t = torch.arange(n) / SR
    if w[0] == "tone":
        f = _u(g, *BANDS[w[1]]); x = torch.sin(2 * math.pi * f * t + _u(g, 0, 6.28)) * _env(n)
    elif w[0] == "chirp":
        a, b = _u(g, 200, 400), _u(g, 1200, 2400)
        f0, f1 = (a, b) if w[1] == "up" else (b, a); k = (f1 / f0)
        x = torch.sin(2 * math.pi * f0 * (k ** t - 1) / math.log(k)) * _env(n)
    elif w[1] == "beeps":
        cnt = int(w[0]); f = _u(g, *BANDS[w[2]]); x = torch.zeros(n)
        slot = n // cnt
        for i in range(cnt):
            L = int(slot * _u(g, 0.4, 0.6)); s = i * slot + int(_u(g, 0, 0.2) * slot)
            L = min(L, n - s)
            x[s:s + L] = torch.sin(2 * math.pi * f * torch.arange(L) / SR) * _env(L, 0.005, 0.02)
    elif w[0] == "vowel":
        f0 = _u(g, 90, 200); x = _harm(n, f0, VOW[w[1]]) * _env(n, 0.03, 0.1)
    else:
        root = 48 + int(torch.randint(12, (1,), generator=g)); sc = [0, 2, 4, 5, 7, 9, 11, 12]
        st = int(torch.randint(4, (1,), generator=g)); idx = [st + i for i in range(4)]
        if w[1] == "falling": idx = idx[::-1]
        x = torch.zeros(n); L = n // 4; timbre = torch.rand(1, generator=g).item() < 0.5
        for j, i in enumerate(idx):
            f = 440 * 2 ** ((root + sc[i] - 69) / 12)
            seg = _harm(L, f) if timbre else torch.sin(2 * math.pi * f * torch.arange(L) / SR)
            x[j * L:(j + 1) * L] = seg * _env(L, 0.005, 0.03)
    x = x * _u(g, 0.3, 1.0)
    if torch.rand(1, generator=g).item() < 0.3: x = x + 0.01 * torch.randn(n, generator=g)
    return (0.9 * x / (x.abs().max() + 1e-6)).clamp(-1, 1)

def batch(n_items, seed):
    """(n,1,N) audio, (n,) class ids; seed stream is disjoint per purpose."""
    g = torch.Generator().manual_seed(seed)
    cls = torch.randint(len(CLASSES), (n_items,), generator=g)
    return torch.stack([clip(int(c), g) for c in cls]).unsqueeze(1), cls
