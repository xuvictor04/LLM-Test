"""text -> audio through WORLD. The caption is read by an LM stand-in; its final hidden state conditions
WORLD's rollout (proposed WORLD.rollout(..., cond=)); AUD.from_world + the frozen codec decoder render it."""
from lmarms import *
arm = sys.argv[1]; STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 2000; NOISE = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0; FREE = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
torch.manual_seed(0)
d = load(); (Ptr, Mtr), (Pho, Mho), (Phc, Mhc) = d["train"], d["hold"], d["combo"]
s1 = torch.load(P + "/stage1.pt"); codec = AudCodec(); codec.load_state_dict(s1["codec"]); probe = Probe(); probe.load_state_dict(s1["probe"])
for p in list(codec.parameters()) + list(probe.parameters()): p.requires_grad_(False)
with torch.no_grad(): Ztr = codec.encode(Mtr).transpose(1, 2); Zho = codec.encode(Mho).transpose(1, 2); Zhc = codec.encode(Mhc).transpose(1, 2)
txt = TinyLM()                                  # caption reader (LM stand-in); cond = its last hidden state
ao = AudObs()
if arm == "T1": wm = CtxWorld(cond_dim=128)
elif arm == "T2": wm = CtxWorld(cond_dim=128, gmm=True)
elif arm == "T0W": wm = RealWorld(); zc = nn.Linear(128, LAT)
elif arm == "T0":  # no WORLD: AR GRU straight on codec latents
    class Direct(nn.Module):
        def __init__(s):
            super().__init__(); s.cond = nn.Linear(128, 128); s.g = nn.GRU(32, 128, batch_first=True); s.o = nn.Linear(128, 32); s.m0 = nn.Parameter(torch.zeros(1, 1, 32))
        def seq(s, c, m): h, _ = s.g(torch.cat([s.m0.expand(m.shape[0], 1, 32), m[:, :-1]], 1), torch.tanh(s.cond(c)).unsqueeze(0)); return s.o(h)
        def gen(s, c, n):
            h = torch.tanh(s.cond(c)).unsqueeze(0); m = s.m0.expand(c.shape[0], 1, 32); out = []
            for _ in range(n):
                y, h = s.g(m, h); m = s.o(y); out.append(m[:, 0])
            return torch.stack(out, 1)
    wm = Direct()
z0 = nn.Parameter(torch.zeros(1, 1, LAT))
params = list(txt.parameters()) + list(ao.parameters()) + list(wm.parameters()) + [z0] + (list(zc.parameters()) if arm == "T0W" else [])
opt = torch.optim.AdamW(params, 1e-3)
def cond_of(Ps):
    x, y, m = cap_batch(Ps); _, h = txt(y); L = m.sum(1).long() - 1
    return h[torch.arange(len(Ps)), L]            # hidden at the caption's final byte '.'
t0 = time.time(); curve = []
for it in range(STEPS):
    i = torch.randint(0, len(Ptr), (32,)); m = Ztr[i]; Ps = [Ptr[j] for j in i.tolist()]; c = cond_of(Ps)
    if arm == "T0":
        loss = F.mse_loss(wm.seq(c, m + NOISE * torch.randn_like(m)), m); rd = loss
    else:
        obs = ao.to_obs(m); z = wm.latent(obs)
        rd = F.mse_loss(ao.from_world(z), m)
        v, cv = world_api._var_cov(z.reshape(-1, LAT))
        if arm == "T0W":
            zin = torch.cat([torch.tanh(zc(c)).unsqueeze(1), z[:, :-1]], 1)
            pred, _ = wm.step_pred(zin + NOISE * torch.randn_like(zin)); pl = F.mse_loss(pred, z)
        else:
            zin = torch.cat([z0.expand(len(Ps), 1, LAT), z[:, :-1]], 1); zin = zin + NOISE * torch.randn_like(zin)
            cc, _ = wm.ctx(zin, wm.h0(c)); pl, _, _ = wm.nll_or_mse(zin, cc, z)
        loss = 0.1 * pl + 1.0 * (v + 0.04 * cv) + rd
    if FREE > 0 and arm in ("T0", "T1"):   # free-running (unrolled) loss: generate 64 frames from the caption alone, match the clip
        mg = wm.gen(c, 64) if arm == "T0" else ao.from_world(wm.gen_from_cond(c, z0, 64))
        loss = loss + FREE * F.mse_loss(mg, m)
    opt.zero_grad(); loss.backward(); opt.step()
    if it % 400 == 0 or it == STEPS - 1:
        curve.append((it, round(loss.item(), 4), round(rd.item(), 5))); print(arm, curve[-1], round(time.time() - t0), flush=True)
res = {"arm": arm, "steps": STEPS, "input_noise": NOISE, "free_w": FREE, "train_s": round(time.time() - t0), "curve[it,loss,readout_or_mse]": curve}
def gen_eval(Ps, Zs, sample=False):
    with torch.no_grad():
        c = cond_of(Ps); t1 = time.time()
        if arm == "T0": mg = wm.gen(c, 64)
        elif arm == "T0W":
            zr = wm.rollout(torch.tanh(zc(c)).unsqueeze(1), 64); mg = ao.from_world(zr)
        else:
            zr = wm.gen_from_cond(c, z0, 64, sample=sample); mg = ao.from_world(zr)
        gen_s = time.time() - t1
        mel = codec.decode(mg.transpose(1, 2)); ln, lt = probe(mel)
        n, t = labels(Ps)
        pern = (ln.argmax(-1) == n).float().mean(0)
        return {"note_acc_by_position": [round(x, 3) for x in pern.tolist()], "note_acc": round(pern.mean().item(), 3),
                "timbre_acc": round((lt.argmax(-1) == t).float().mean().item(), 3),
                "all4_notes_and_timbre": round(((ln.argmax(-1) == n).all(1) & (lt.argmax(-1) == t)).float().mean().item(), 3),
                "L1_logmel_vs_truth": round((mel - codec.decode(Zs.transpose(1, 2))).abs().mean().item(), 3),
                "gen_ms_per_2.56s_clip": round(1000 * gen_s / len(Ps), 2)}
res["hold"] = gen_eval(Pho, Zho); res["combo"] = gen_eval(Phc, Zhc)
if arm == "T2": torch.manual_seed(1); res["hold_sampled"] = gen_eval(Pho, Zho, True)
print(json.dumps(res)); json.dump(res, open(P + f"/stage4_{arm}_n{NOISE}_f{FREE}.json", "w"))
