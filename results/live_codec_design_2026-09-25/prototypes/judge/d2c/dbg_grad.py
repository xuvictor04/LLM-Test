import os, sys, torch
os.environ.update(D2_T1="30", D2_C1="60", D2_P2="150", D2_P3="0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d2run as R
r = R.Run("d2", 0)
for _ in range(30): r.text_step()
for _ in range(60): r.codec_only_step()
def norms():
    rows, clips = [], []
    for i in range(12):
        p, x, cap = R.area_sample("A", r.g); rows.append(("t2a" if i % 2 == 0 else "a2t", cap, i)); clips.append(x)
    lmx = R.logmag(torch.stack(clips)); enc = r.codec.encode(lmx)
    bt = R.build(rows, True, enc["c"].detach(), enc["cnt"], enc["M"])
    res = R.lm_forward(r.lm, bt, True, r.text_ok, r.aud_ok)
    capm = bt["capm"][:, 1:] & res["v"]
    parts = dict(cap_ce=res["ce"][capm].mean(), all_ce=res["ce"][res["v"]].mean(), gmm=R.GMM_W * res["nll"].mean() / R.DLAT, dur=res["dce"].mean())
    out = {}
    for k, l in parts.items():
        r.lm.zero_grad(); l.backward(retain_graph=True)
        out[k] = (round(l.item(), 3), round(torch.sqrt(sum((p.grad ** 2).sum() for p in r.lm.parameters() if p.grad is not None)).item(), 3))
    lg, mu, ls = R.gmm_split(r.lm, res["o"][res["sel"]])
    out["logsig_mean"] = round(ls.mean().item(), 3); out["frac_at_clamp"] = round((ls <= -4.99).float().mean().item(), 3)
    return out
print("before P2", norms())
for s in range(150):
    r.media_step([("A", 12)])
    if s % 50 == 49: print(s, norms())
