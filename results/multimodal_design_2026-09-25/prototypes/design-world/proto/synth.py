"""Synthetic captioned audio: 4-note melodies, order-2 Markov grammar per area, 3 timbres.
Every clip carries its generating parameters; the caption is rendered from them."""
import math, random, torch
SR = 8000; HOP = 160; NFFT = 512; NMEL = 64
NOTE_S = 0.64; NNOTES = 4
CLIP_N = int(SR * NOTE_S * NNOTES)           # 20480 samples = 2.56 s
MEL_T = CLIP_N // HOP                         # 128 mel frames (50 Hz)
FREQS = [220 * 1.25 ** k for k in range(8)]   # 220 .. 1049 Hz
LETTERS = "abcdefgh"
TIMBRES = ["sine", "harm", "odd"]

def grammar(seed):
    """order-2 Markov: p(n3 | n1, n2), two allowed successors per pair, 0.7 / 0.3"""
    r = random.Random(seed); G = {}
    for a in range(8):
        for b in range(8):
            s = r.sample(range(8), 2); G[(a, b)] = [(s[0], 0.7), (s[1], 0.3)]
    return G

def draw_params(r, G):
    n = [r.randrange(8), r.randrange(8)]
    while len(n) < NNOTES:
        (x, p), (y, _) = G[(n[-2], n[-1])]
        n.append(x if r.random() < p else y)
    return {"timbre": r.randrange(3), "notes": n, "amp": r.uniform(0.3, 0.8), "seed": r.randrange(1 << 30)}

def caption(p):
    return f"{TIMBRES[p['timbre']]}:{''.join(LETTERS[k] for k in p['notes'])}."

def render(p):
    g = torch.Generator().manual_seed(p["seed"])
    nn_ = int(SR * NOTE_S); t = torch.arange(nn_) / SR
    env = torch.clamp(t / 0.01, max=1.0) * torch.exp(-t / 0.35)
    out = []
    for k in p["notes"]:
        f = FREQS[k] * (1 + 0.004 * (torch.rand(1, generator=g).item() - 0.5))
        ph = 2 * math.pi * torch.rand(1, generator=g).item()
        if p["timbre"] == 0: parts = [(1, 1.0)]
        elif p["timbre"] == 1: parts = [(1, 1.0), (2, 0.5), (3, 0.33)]
        else: parts = [(1, 1.0), (3, 0.33), (5, 0.2)]
        s = sum(a * torch.sin(2 * math.pi * f * m * t + ph * m) for m, a in parts if f * m < 3900)
        out.append(s * env)
    x = torch.cat(out) * p["amp"] + 0.003 * torch.randn(CLIP_N, generator=g)
    return x

_MEL = None
def melfb():
    global _MEL
    if _MEL is None:
        def hz2mel(h): return 2595 * math.log10(1 + h / 700)
        def mel2hz(m): return 700 * (10 ** (m / 2595) - 1)
        nb = NFFT // 2 + 1; fr = torch.linspace(0, SR / 2, nb)
        mp = torch.linspace(hz2mel(0), hz2mel(SR / 2), NMEL + 2); hz = torch.tensor([mel2hz(float(m)) for m in mp])
        fb = torch.zeros(NMEL, nb)
        for i in range(NMEL):
            l, c, h = hz[i], hz[i + 1], hz[i + 2]
            fb[i] = torch.clamp(torch.minimum((fr - l) / (c - l), (h - fr) / (h - c)), min=0)
        _MEL = fb
    return _MEL

def logmel(x):
    """(B, N) -> (B, NMEL, MEL_T) natural-log mel"""
    S = torch.stft(x, NFFT, HOP, window=torch.hann_window(NFFT), return_complex=True, center=True).abs() ** 2
    M = melfb() @ S
    return torch.log(M + 1e-4)[..., :MEL_T]

def make_set(n, seed, G, keep=lambda p: True):
    r = random.Random(seed); P = []
    while len(P) < n:
        p = draw_params(r, G)
        if keep(p): P.append(p)
    mels = []
    for i in range(0, n, 64):
        xs = torch.stack([render(p) for p in P[i:i + 64]]); mels.append(logmel(xs))
    return P, torch.cat(mels)

def heldout_combo(p):   # compositional hold-out: timbre 'odd' with a first note in {a, b}
    return p["timbre"] == 2 and p["notes"][0] in (0, 1)
