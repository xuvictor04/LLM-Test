from lmarms import *
cond = sys.argv[1]; src = sys.argv[2]; K = int(sys.argv[3]) if len(sys.argv) > 3 else 8; STEPS = 1500
torch.manual_seed(0)
d = load(); (Ptr, Mtr), (Pho, Mho), (Phc, Mhc) = d["train"], d["hold"], d["combo"]
s1 = torch.load(P + "/stage1.pt"); codec = AudCodec(); codec.load_state_dict(s1["codec"])
with torch.no_grad():
    Z = {k: codec.encode(M).transpose(1, 2) for k, M in (("tr", Mtr), ("ho", Mho), ("hc", Mhc))}
    if src == "world":   # the LM reads WORLD's latent state z (frozen, from the W1 run) -- route 2's literal reading
        s2 = torch.load(P + "/stage2_W1.pt"); wm = CtxWorld(); wm.load_state_dict(s2["wm"]); ao = AudObs(); ao.load_state_dict(s2["ao"])
        Z = {k: wm.latent(ao.to_obs(v)) for k, v in Z.items()}
lm = TinyLM(cond=cond, K=K); opt = torch.optim.AdamW(lm.parameters(), 2e-3)
Xtr = cap_batch(Ptr); t0 = time.time(); curve = []
def evaluate(Ps, Zs):
    x, y, m = cap_batch(Ps); lm.eval()
    with torch.no_grad():
        lg, _ = lm(x, Zs); nll = F.cross_entropy(lg.reshape(-1, 256), y.reshape(-1), reduction="none").reshape(y.shape) * m
        bits = (nll.sum(1) / 0.6931).mean().item(); bpb = (nll.sum() / m.sum() / 0.6931).item()
        # greedy decode
        cur = torch.full((len(Ps), 1), 2); out = []
        for t in range(y.shape[1]):
            lg, _ = lm(cur, Zs); nx = lg[:, -1].argmax(-1); out.append(nx); cur = torch.cat([cur, nx[:, None]], 1)
        out = torch.stack(out, 1)
    lm.train()
    exact = ((out == y) | (m == 0)).all(1).float().mean().item()
    # attribute accuracy: parse "timbre:notes."
    ta = na = 0
    for i, p in enumerate(Ps):
        s = bytes(out[i].tolist()).split(b".")[0].decode("latin1")
        tt, _, nn_ = s.partition(":"); ta += tt == S.TIMBRES[p["timbre"]]
        na += sum(1 for j in range(4) if j < len(nn_) and nn_[j] == S.LETTERS[p["notes"][j]])
    return {"caption_bits": round(bits, 3), "bits_per_byte": round(bpb, 4), "exact": round(exact, 3),
            "timbre_acc": round(ta / len(Ps), 3), "note_acc": round(na / (4 * len(Ps)), 3)}
for it in range(STEPS):
    i = torch.randint(0, len(Ptr), (32,)); x, y, m = Xtr[0][i], Xtr[1][i], Xtr[2][i]
    lg, _ = lm(x, Z["tr"][i]); loss = (F.cross_entropy(lg.reshape(-1, 256), y.reshape(-1), reduction="none") * m.reshape(-1)).sum() / m.sum()
    opt.zero_grad(); loss.backward(); opt.step()
    if it % 300 == 0 or it == STEPS - 1:
        curve.append((it, round(loss.item() / 0.6931, 4))); print(cond, src, curve[-1], round(time.time() - t0), flush=True)
res = {"cond": cond, "src": src, "K": K if cond == "prefix" else None, "train_s": round(time.time() - t0), "curve_bits_per_byte": curve,
       "hold": evaluate(Pho, Z["ho"]), "combo": evaluate(Phc, Z["hc"])}
# throughput of one real-size LM window (128 text tokens) with this conditioning, B=16, fwd+bwd
x = torch.randint(0, 256, (16, 128)); med = Z["tr"][:16]; tt = []
for r in range(6):
    t1 = time.time(); lg, _ = lm(x, med); lg.float().mean().backward(); tt.append(time.time() - t1)
res["ms_per_B16_ctx128_fwd_bwd"] = round(1000 * sorted(tt)[2], 1)
print(json.dumps(res)); json.dump(res, open(P + f"/stage3_{cond}_{src}_{K}.json", "w"))
