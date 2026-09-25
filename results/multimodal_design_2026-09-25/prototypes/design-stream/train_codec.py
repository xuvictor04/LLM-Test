import os, sys, json, time, math
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch, torch.nn.functional as F; torch.set_num_threads(1)
import codec_lib as C, audgen as A
stride = int(sys.argv[1]); minutes = float(sys.argv[2]); out = sys.argv[3]
torch.manual_seed(0)
C.SR[0] = A.SR; C.FSQ_ENT[0] = 0.1; C.PRENORM[0] = True
q = C.FSQ(64, [8, 5, 5, 5]); m = C.Codec(stride, 16, 64, q)
opt = torch.optim.AdamW(m.parameters(), lr=1e-3, betas=(0.8, 0.99))
ev, evc = A.batch(32, 999_001)
t0 = time.time(); step = 0; log = []; seed = 10_000
while time.time() - t0 < minutes * 60:
    x, _ = A.batch(8, seed + step)
    off = int(torch.randint(0, A.N // 2, (1,))); x = x[..., off:off + A.N // 2]
    m.train(); y, codes, aux, T = m(x)
    loss = C.mel_dist(x, y) + C.stft_loss(x, y) + F.l1_loss(y, x) + aux
    opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
    step += 1
    for gp in opt.param_groups: gp["lr"] = 1e-3 * min(1, step / 200) * max(0.05, 1 - (time.time() - t0) / (minutes * 60))
    if step % 100 == 0:
        m.eval()
        with torch.no_grad():
            ye, ce, _, _ = m(ev[:8]); used = int(torch.unique(ce).numel())
        log.append((round(time.time() - t0), step, round(loss.item(), 3), round(C.mel_dist(ev[:8], ye).item(), 3), used)); print(log[-1], flush=True)
m.eval()
with torch.no_grad():
    tt = time.time(); y, codes, _, T = m(ev); rt = time.time() - tt
    h = torch.bincount(codes.reshape(-1), minlength=1000).float(); p = h / h.sum()
    ent = -(p[p > 0] * p[p > 0].log2()).sum().item()
    res = dict(stride=stride, frames_per_s=A.SR / stride, steps=step, train_s=round(time.time() - t0),
               mel=C.mel_dist(ev, y).item(), mel_silence=C.mel_dist(ev, torch.zeros_like(ev) + 1e-4 * torch.randn_like(ev)).item(),
               snr=C.snr(ev.squeeze(1), y.squeeze(1)), used=int((h > 0).sum()), perplexity=2 ** ent, entropy_bits=ent,
               rtf=rt / 32.0, params=sum(p.numel() for p in m.parameters()), log=log)
print(json.dumps(res)); json.dump(res, open(out + ".json", "w"))
torch.save(m.state_dict(), out + ".pt")
