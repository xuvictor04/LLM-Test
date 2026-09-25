from common import *
torch.manual_seed(0)
d = load(); (Ptr, Mtr), (Pho, Mho), (Phc, Mhc) = d["train"], d["hold"], d["combo"]
# ---- probe on true mels
probe = Probe(); opt = torch.optim.Adam(probe.parameters(), 2e-3)
ntr, ttr = labels(Ptr)
for it in range(600):
    i = torch.randint(0, len(Ptr), (64,))
    ln, lt = probe(Mtr[i]); loss = F.cross_entropy(ln.reshape(-1, 8), ntr[i].reshape(-1)) + F.cross_entropy(lt, ttr[i])
    opt.zero_grad(); loss.backward(); opt.step()
print("probe on TRUE mel: hold", probe_acc(probe, Mho, Pho), "combo", probe_acc(probe, Mhc, Phc), flush=True)
# ---- codec
codec = AudCodec(); opt = torch.optim.AdamW(codec.parameters(), 1e-3)
nparam = sum(p.numel() for p in codec.parameters() if p.requires_grad)
base = (Mho - Mtr.mean(0, keepdim=True)).abs().mean().item()   # "ignore the codes" decoder: mean spectrogram
curve = []; t0 = time.time(); STEPS = 1500
for it in range(STEPS):
    i = torch.randint(0, len(Ptr), (32,)); m = Mtr[i]
    z = codec.encode(m); zh = z + 0.05 * torch.randn_like(z)      # noise: decoder robust to predicted latents
    rec = codec.decode(zh); loss = (rec - m).abs().mean()
    opt.zero_grad(); loss.backward(); opt.step()
    if it % 100 == 0 or it == STEPS - 1:
        with torch.no_grad(): hl = (codec.decode(codec.encode(Mho)) - Mho).abs().mean().item()
        curve.append((it, round(loss.item(), 4), round(hl, 4))); print(curve[-1], round(time.time() - t0), flush=True)
train_s = time.time() - t0
with torch.no_grad():
    t1 = time.time(); z = codec.encode(Mho); rec = codec.decode(z); enc_dec_s = time.time() - t1
    rec_c = codec.decode(codec.encode(Mhc))
res = {"codec_params": nparam, "latent": list(z.shape[1:]), "latent_hz": 25, "train_steps": STEPS, "train_s": round(train_s),
       "hold_L1_logmel": round((rec - Mho).abs().mean().item(), 4), "combo_L1_logmel": round((rec_c - Mhc).abs().mean().item(), 4),
       "mean_spectrogram_baseline_L1": round(base, 4),
       "probe_on_recon_hold": probe_acc(probe, rec, Pho), "probe_on_recon_combo": probe_acc(probe, rec_c, Phc),
       "enc_dec_rtf_1thread": round(enc_dec_s / (len(Pho) * 2.56), 5), "curve": curve}
print(json.dumps(res)); json.dump(res, open(P + "/stage1.json", "w"))
torch.save({"codec": codec.state_dict(), "probe": probe.state_dict()}, P + "/stage1.pt")
