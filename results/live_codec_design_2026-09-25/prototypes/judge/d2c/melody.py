"""Second media area 'aud/melody': 1 s clips at 8 kHz, 4 notes x 0.25 s from 6 pitches, timbre pure/buzzy.
Caption 'pure melody cafe'-style. Analytic inverse probe (fixed signal processing, no learned weights)."""
import math, re, torch
import synth as S
SR = S.SR
PITCH = [250.0 * 2 ** (k * 2 / 7) for k in range(6)]  # 250 .. 673 Hz, ratio 1.219 per step
LET = "abcdef"
NN = 4; NOTE_N = SR // NN


def sample(g):
    t = S.TIMBRES[int(torch.randint(2, (1,), generator=g))]
    notes = tuple(int(v) for v in torch.randint(6, (NN,), generator=g))
    return ("melody", t, notes), render(("melody", t, notes), g)


def render(p, g):
    _, t, notes = p
    amp = 0.3 + 0.6 * torch.rand(1, generator=g).item()
    xs = []
    for k in notes:
        f0 = PITCH[k] * (1 + 0.01 * (torch.rand(1, generator=g).item() - 0.5))
        seg = S._osc(torch.full((NOTE_N,), f0), t, NOTE_N) * S._env(NOTE_N, g)
        xs.append(seg)
    x = amp * torch.cat(xs)
    if torch.rand(1, generator=g).item() < 0.3:
        x += 0.005 * torch.randn(SR, generator=g)
    return x.clamp(-1, 1)


def caption(p):
    return f"{p[1]} melody {''.join(LET[k] for k in p[2])}"


def parse_caption(s):
    m = re.fullmatch(r"(pure|buzzy) melody ([a-f]{4})", s.strip())
    if not m:
        return None
    return ("melody", m.group(1), tuple(LET.index(c) for c in m.group(2)))


_W = torch.hann_window(512)


def probe(x):
    X = torch.stft(x, 512, 128, window=_W, return_complex=True).abs()
    T = X.shape[1]; hz = SR / 512
    q = T / NN; notes = []; hf = []
    for i in range(NN):
        a, b = int(i * q + 0.25 * q), int(i * q + 0.75 * q)
        s = X[:, a:max(a + 1, b)].mean(1)
        cand = torch.arange(8, 120)
        sc = s[cand] + 0.5 * s[(2 * cand).clamp(max=256)] + 0.33 * s[(3 * cand).clamp(max=256)]
        b0 = int(cand[sc.argmax()]); f = b0 * hz
        notes.append(int(torch.tensor([abs(math.log2(f / pp)) for pp in PITCH]).argmin()))
        p2 = s.pow(2); fund = p2[max(0, b0 - 3):b0 + 4].sum(); hf.append(float(1 - fund / (p2.sum() + 1e-12)))
    tim = "buzzy" if float(torch.tensor(hf).median()) > 0.15 else "pure"
    return ("melody", tim, tuple(notes))


def attr_acc(pred, true):
    if pred is None:
        return dict(timbre=0, note=0.0, exact=0)
    d = dict(timbre=int(pred[1] == true[1]), note=sum(int(a == b) for a, b in zip(pred[2], true[2])) / NN)
    d["exact"] = int(d["timbre"] == 1 and d["note"] == 1.0)
    return d


if __name__ == "__main__":
    g = torch.Generator().manual_seed(3); tot = {}; n = 300
    for _ in range(n):
        p, x = sample(g); d = attr_acc(probe(x), p)
        for k, v in d.items(): tot[k] = tot.get(k, 0) + v
    print({k: round(v / n, 3) for k, v in tot.items()})
    print(caption(p), parse_caption(caption(p)) == p)
