import sys, time, torch, torch.nn.functional as F
sys.path.insert(0, "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm/research-codecs")
import codec as C
torch.set_num_threads(1); torch.manual_seed(0)
m = C.Codec2(320, 16, 64, C.NoQ())
g = torch.Generator().manual_seed(1)
x = C.batch(8, 8000, 16000, g)
print("x rms", x.pow(2).mean().sqrt().item())
lr = float(sys.argv[1])
opt = torch.optim.Adam(m.parameters(), lr=lr)
t0=time.time()
for i in range(151):
    y, *_ = m(x)
    sc = C.mel_dist(x, y) + C.stft_loss(x,y); l1 = F.l1_loss(y, x)
    loss = sc + 1.0*l1
    opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
    if i % 25 == 0: print(i, round(sc.item(),3), round(l1.item(),4), round(C.snr(x.squeeze(1), y.squeeze(1)),2), round(time.time()-t0,1), flush=True)
