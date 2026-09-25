"""Do the frozen codec's codes carry the caption? GRU(128) classifier on code sequences: the
upper bound on what the LM's understanding direction can reach from these codes."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch, torch.nn as nn, torch.nn.functional as F; torch.set_num_threads(1)
import audgen as A, codec_lib as C
C.SR[0] = A.SR; C.PRENORM[0] = True; out = {}
xtr, ctr = A.batch(3000, 2024); xho, cho = A.batch(256, 999_777)
for hz in (50,):
    m = C.Codec(A.SR // hz, 16, 64, C.FSQ(64, [8, 5, 5, 5])); m.load_state_dict(torch.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"codec{hz}.pt"))); m.eval()
    with torch.no_grad():
        enc = lambda x: torch.cat([m.q(m.enc(x[i:i + 64]))[1][..., 0] for i in range(0, len(x), 64)])
        ktr, kho = enc(xtr), enc(xho)
    torch.manual_seed(0)
    emb = nn.Embedding(1000, 128); gru = nn.GRU(128, 128, batch_first=True); head = nn.Linear(128, 16)
    ps = list(emb.parameters()) + list(gru.parameters()) + list(head.parameters()); opt = torch.optim.Adam(ps, 2e-3)
    t0 = time.time(); step = 0
    while step < 1200:
        j = torch.randint(3000, (32,)); h, _ = gru(emb(ktr[j])); loss = F.cross_entropy(head(h[:, -1]), ctr[j])
        opt.zero_grad(); loss.backward(); opt.step(); step += 1
        if step in (125, 375, 1125):
            with torch.no_grad(): print("clips", step * 32, (head(gru(emb(kho))[0][:, -1]).argmax(-1) == cho).float().mean().item(), flush=True)
    with torch.no_grad(): acc = (head(gru(emb(kho))[0][:, -1]).argmax(-1) == cho).float().mean().item()
    out[hz] = dict(steps=step, clips_seen=step * 32, heldout_acc=acc)
    print(hz, out[hz], flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs", "codeclf_budget.json"), "w"))
