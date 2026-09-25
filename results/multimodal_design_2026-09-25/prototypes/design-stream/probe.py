"""Parameter-recovery probe: log-mel CNN trained on REAL synthetic clips -> 16 caption classes.
It never sees codec output, so it scores codec reconstructions and LM generations independently."""
import os, sys, time, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch, torch.nn as nn, torch.nn.functional as F
import audgen as A, codec_lib as C
C.SR[0] = A.SR
def feats(x):
    w = torch.hann_window(256); M = C.melmat(256, A.SR, 48)
    S = M @ torch.stft(x.squeeze(1), 256, 128, window=w, return_complex=True).abs()
    L = torch.log10(S.clamp_min(1e-6)); L = L - L.amax((1, 2), keepdim=True)
    return L.clamp_min(-3.0).unsqueeze(1)  # per-clip normalised, 60 dB floor: robust to codec noise floors
class Probe(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                                 nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                                 nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d((4, 4)),
                                 nn.Flatten(), nn.Linear(512, 16))
    def forward(self, x): return self.net(feats(x))
if __name__ == "__main__":
    os.environ["OMP_NUM_THREADS"] = "1"; torch.set_num_threads(1); torch.manual_seed(0)
    p = Probe(); opt = torch.optim.Adam(p.parameters(), 2e-3)
    C.PRENORM[0] = True; codecs = []; t00 = time.time()
    for hz in (50, 25):
        m = C.Codec(A.SR // hz, 16, 64, C.FSQ(64, [8, 5, 5, 5]))
        m.load_state_dict(torch.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"codec{hz}.pt"))); m.eval(); codecs.append(m)
    pool_x, pool_c = A.batch(1536, 60_001); pools = []
    with torch.no_grad():
        for m in codecs: pools.append(torch.cat([m(pool_x[i:i + 64])[0] for i in range(0, len(pool_x), 64)]))
    print("pool built", round(time.time() - t00), flush=True)
    def aug(x, k):
        r = k % 3
        if r == 0: return x + 10 ** (-3 + 2 * torch.rand(x.shape[0], 1, 1)) * torch.randn_like(x), None
        j = torch.randint(len(pool_x), (32,)); return pools[r - 1][j], pool_c[j]
    ev, evc = A.batch(512, 777_001)
    t0 = time.time(); step = 0
    while time.time() - t0 < float(sys.argv[1]) * 60:
        x, c = A.batch(32, 50_000 + step)
        x, c2 = aug(x, step); c = c if c2 is None else c2
        loss = F.cross_entropy(p(x), c); opt.zero_grad(); loss.backward(); opt.step(); step += 1
        if step % 50 == 0:
            with torch.no_grad(): acc = (p(ev).argmax(-1) == evc).float().mean().item()
            print(step, round(loss.item(), 3), acc, flush=True)
    with torch.no_grad():
        acc = (p(ev).argmax(-1) == evc).float().mean().item()
        accr = [(p(m(ev[:256])[0]).argmax(-1) == evc[:256]).float().mean().item() for m in codecs]
    print("recon acc 50/25", accr)
    torch.save(p.state_dict(), os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe.pt"))
    print(json.dumps(dict(steps=step, heldout_acc=acc)))
