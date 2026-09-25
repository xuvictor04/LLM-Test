import os, sys, torch
os.environ.update(D2_T1="30", D2_C1="60", D2_P2="150", D2_P3="0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d2run as R
r = R.Run("d2", 0)
for _ in range(30): r.text_step()
for _ in range(60): r.codec_only_step()
for _ in range(150): r.media_step([("A", 12)])
r.lm.eval(); r.codec.eval()
pack = r.encode_eval("A"); ps, X, lmx, enc = pack
with torch.no_grad():
    rows = [("a2t", R.cap_of("A", p), i) for i, p in enumerate(ps[:4])]
    bt = R.build(rows, True, enc["c"], enc["cnt"], enc["M"])
    res = R.lm_forward(r.lm, bt, True, r.text_ok, r.aud_ok)
    am = res["lg"].argmax(-1)
    for i in range(4):
        cm = bt["capm"][i, 1:]
        print("TF argmax:", bytes([int(t) for t in am[i][cm] if int(t) < 256]).decode(errors="replace"), "| true:", R.S.caption(ps[i]))
    # greedy via prompt path for the same 4
    i = 0; M = int(enc["M"][i]); pr = [R.A2T, R.AUD_B] + [R.SLOT] * M + [R.AUD_E]
    cv = torch.zeros(len(pr), R.DLAT); cv[2:2 + M] = enc["c"][i, :M]
    dv = torch.zeros(len(pr), dtype=torch.long); dv[2:2 + M] = enc["cnt"][i, :M]
    slot = torch.zeros(len(pr)); slot[2:2 + M] = 1
    o1, _ = r.lm.trunk(torch.tensor([pr]), cv[None], dv[None], slot[None])
    o2 = res["o"][0, :len(pr)]
    print("prompt-path vs batch-path max diff:", (o1[0] - o2).abs().max().item())
    print("batch ids", bt["ids"][0, :len(pr) + 3].tolist()); print("prompt ids", pr)
    print("dv batch", bt["dv"][0, :len(pr)].tolist()); print("dv prompt", dv.tolist())
    print("cv diff", (bt["cv"][0, :len(pr)] - cv).abs().max().item())
    print(r.understand("A", pack)["samples"])
