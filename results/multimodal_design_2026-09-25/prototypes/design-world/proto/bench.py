"""per-window cost of the route-2 media pieces at the loop's batch (OPT_BATCH_WINDOWS=1), 1 thread, CPU.
Also the REAL WORLD.loss_terms on a text window vs an audio window."""
from lmarms import *
torch.manual_seed(0)
s1 = torch.load(P + "/stage1.pt"); codec = AudCodec(); codec.load_state_dict(s1["codec"])
def tm(f, n=30):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); f(); ts.append(time.perf_counter() - t)
    ts.sort(); return round(1000 * ts[len(ts) // 2], 2)
d = load(); mel = d["hold"][1][:1]
out = {}
out["codec_encode_ms_per_2.56s"] = tm(lambda: codec.encode(mel))
def cod_train():
    z = codec.encode(mel); l = (codec.decode(z) - mel).abs().mean(); l.backward()
out["codec_train_fwd_bwd_ms_per_2.56s"] = tm(cod_train)
rw = RealWorld()
obs_txt = torch.randn(1, 128, 128, requires_grad=True); obs_aud = torch.randn(1, 64, 128, requires_grad=True)
def wl(o):
    l, _ = rw.loss(o); l.backward()
out["REAL_world_loss_terms_fwd_bwd_ms_text_window_128"] = tm(lambda: wl(obs_txt))
out["REAL_world_loss_terms_fwd_bwd_ms_audio_64_frames"] = tm(lambda: wl(obs_aud))
cw = CtxWorld(cond_dim=128)
def cl(o):
    l, _ = cw.loss(o); l.backward()
out["ctx_world_loss_fwd_bwd_ms_audio_64"] = tm(lambda: cl(obs_aud))
z0 = torch.zeros(1, 1, LAT); c = torch.randn(1, 128); ao = AudObs()
def free():
    zr = cw.gen_from_cond(c, z0, 64); ao.from_world(zr).pow(2).mean().backward()
out["ctx_world_free_run_64_fwd_bwd_ms"] = tm(free, 10)
for cond, K in (("none", 8), ("extra_attn", 8), ("prefix", 8), ("prefix", 64), ("xattn", 8)):
    lm = TinyLM(cond=cond, K=K); x = torch.randint(0, 256, (1, 128)); med = torch.randn(1, 64, LAT)
    def f():
        lg, _ = lm(x, med); lg.mean().backward()
    out[f"lm_ctx128_fwd_bwd_ms_{cond}{K if cond=='prefix' else ''}"] = tm(f)
print(json.dumps(out, indent=1)); json.dump(out, open(P + "/bench.json", "w"))
