from worldarms import *
arm = sys.argv[1]; STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
torch.manual_seed(0)
d = load(); (Ptr, Mtr), (Pho, Mho), (Phc, Mhc) = d["train"], d["hold"], d["combo"]; G = d["G"]
s1 = torch.load(P + "/stage1.pt"); codec = AudCodec(); codec.load_state_dict(s1["codec"]); probe = Probe(); probe.load_state_dict(s1["probe"])
for p in codec.parameters(): p.requires_grad_(False)
with torch.no_grad(): Ztr = codec.encode(Mtr).transpose(1, 2); Zho = codec.encode(Mho).transpose(1, 2)   # (B,64,32) frozen codec latents
wm = {"W0": lambda: RealWorld(), "W1": lambda: CtxWorld(), "W1F": lambda: CtxWorld(), "W2": lambda: CtxWorld(gmm=True), "W2D": lambda: CtxWorld(gmm=True, detach_target=True)}[arm]()
ao = AudObs()
opt = torch.optim.AdamW(list(wm.parameters()) + list(ao.parameters()), 1e-3)
t0 = time.time(); curve = []
for it in range(STEPS):
    i = torch.randint(0, len(Ptr), (32,)); m = Ztr[i]
    obs = ao.to_obs(m)
    wl, st = wm.loss(obs)
    z = wm.latent(obs); rd = F.mse_loss(ao.from_world(z), m)
    loss = wl + rd
    if arm == "W1F":   # free-running continuation loss: roll 32 frames from the 32-frame prompt, match in media-latent space
        zr = wm.rollout(z[:, :32], 32); loss = loss + F.mse_loss(ao.from_world(zr), m[:, 32:])
    opt.zero_grad(); loss.backward(); opt.step()
    if it % 250 == 0 or it == STEPS - 1:
        inv = st.inv if not isinstance(st, dict) else st["inv"]; ls = st.latent_std if not isinstance(st, dict) else st["latent_std"]
        curve.append((it, round(float(wl), 4), round(float(inv), 5), round(float(ls), 3), round(rd.item(), 5))); print(arm, curve[-1], round(time.time() - t0), flush=True)
train_s = time.time() - t0
# ---------- evaluation
res = {"arm": wm.kind, "steps": STEPS, "train_s": round(train_s), "curve[it,world_loss,inv,latent_std,readout_mse]": curve}
with torch.no_grad():
    obs = ao.to_obs(Zho); z = wm.latent(obs)
    if arm == "W0": pred, _ = wm.step_pred(z[:, :-1])
    else:
        c, _ = wm.ctx(z); _, pred, _ = wm.nll_or_mse(z[:, :-1], c[:, :-1], z[:, 1:])
    tgt = z[:, 1:]; pers = z[:, :-1]
    e = ((pred - tgt) ** 2).mean(-1); ep = ((pers - tgt) ** 2).mean(-1)
    bnd = torch.zeros(63, dtype=torch.bool); bnd[[15, 31, 47]] = True   # predicting the first frame of notes 2,3,4
    res["onestep_mse_over_persistence_all"] = round((e.mean() / ep.mean()).item(), 4)
    res["onestep_mse_over_persistence_within_note"] = round((e[:, ~bnd].mean() / ep[:, ~bnd].mean()).item(), 4)
    res["onestep_mse_over_persistence_note_boundary"] = round((e[:, bnd].mean() / ep[:, bnd].mean()).item(), 4)
    res["readout_mse_hold"] = round(F.mse_loss(ao.from_world(z), Zho).item(), 5)
    res["codec_latent_var"] = round(Zho.var().item(), 5)
    # continuation: prompt = notes 1-2 (32 frames), roll out 32 frames (notes 3-4), readout -> decode -> probe
    def gen_eval(sample):
        t1 = time.time(); zr = wm.rollout(z[:, :32], 32, sample=sample); roll_s = time.time() - t1
        mgen = ao.from_world(zr); mel_prompt = codec.decode(Zho[:, :32].transpose(1, 2))
        mel = torch.cat([mel_prompt, codec.decode(torch.cat([Zho[:, :32], mgen], 1).transpose(1, 2))[..., 64:]], -1)
        ln, lt = probe(mel); pr = ln.softmax(-1)
        n3 = ln.argmax(-1)[:, 2]; n4 = ln.argmax(-1)[:, 3]
        legal3 = mode3 = legal4 = 0
        for j, p in enumerate(Pho):
            a, b = p["notes"][0], p["notes"][1]; succ = G[(a, b)]
            legal3 += int(n3[j]) in (succ[0][0], succ[1][0]); mode3 += int(n3[j]) == succ[0][0]
            succ4 = G[(b, int(n3[j]))]; legal4 += int(n4[j]) in (succ4[0][0], succ4[1][0])
        N = len(Pho); tim = (lt.argmax(-1) == labels(Pho)[1]).float().mean().item()
        conf = pr[:, 2:].amax(-1).mean().item()
        l1_true = (mel[..., 64:] - Mho[..., 64:]).abs().mean().item()
        return {"note3_legal": round(legal3 / N, 3), "note3_mode(0.7)": round(mode3 / N, 3), "note4_legal": round(legal4 / N, 3),
                "timbre_kept": round(tim, 3), "probe_conf_gen_notes": round(conf, 3), "L1_vs_true_continuation": round(l1_true, 3),
                "rollout_ms_per_frame_B400": round(1000 * roll_s / 32, 2)}
    res["gen_argmax"] = gen_eval(False)
    if arm in ("W2", "W2D"): torch.manual_seed(1); res["gen_sampled"] = gen_eval(True)
    # oracle continuation (true latents for notes 3-4) for reference
    ln, _ = probe(codec.decode(Zho.transpose(1, 2))); res["ref_true_note3_legal"] = 1.0
    res["chance_note3_legal"] = 0.25; res["order1_best_note3_legal_estimate"] = "see stage2 notes"
print(json.dumps(res)); json.dump(res, open(P + f"/stage2_{arm}.json", "w"))
torch.save({"wm": wm.state_dict(), "ao": ao.state_dict()}, P + f"/stage2_{arm}.pt")
