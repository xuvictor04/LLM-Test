"""Route 1 prototype: the TREE's own LM (lm_api.build_model via compose: GRU, width 128, ctx 128,
vocab_slots 4096) and the TREE's own WORLD (world_api.loss_terms / forecast) consume one shared
discrete stream: tree-TOK text ids (the 4-area synthetic corpus) and learned-FSQ codec ids in a
RESERVED id range [BASE, BASE+1000) plus two boundary ids. Paired caption<->clip examples in both
orders (caption first = generation, clip first = understanding).

usage: python3 lm_proto.py ARM CODEC_HZ STEPS OUT
ARM: T | Jshared | Jmask | Cpure | Creplay  (see p_audio)
"""
import os, sys, json, time, math, random
os.environ.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", DATA_STREAM_BYTES="120000")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "tree", "src"))
import torch, torch.nn.functional as F
torch.set_num_threads(1)
import audgen as A, codec_lib as C, probe as P
from spine.compose import compose
from lm import api as lm_api
from world import api as world_api
from tok import api as tok_api

ARM, HZ, STEPS, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
MASKED = ARM != "Jshared"
t_setup = time.time()
sysm = compose(environ=dict(os.environ))
LMC, WC, TOKC = sysm.configs["LM"], sysm.configs["WORLD"], sysm.configs["TOK"]
model, world = sysm.model, sysm.world
SLOTS = int(LMC.vocab_slots); CTX = int(LMC.ctx)
LIVE_TEXT = int(sysm.vocab.size()); BPT = float(sysm.segmentation.bytes_per_token)
BASE = 3072; NCODE = 1000; OPEN, CLOSE = BASE + NCODE, BASE + NCODE + 1
assert OPEN < SLOTS and LIVE_TEXT < BASE

# ---- RISK 3 made concrete: the tree's decode masks [live_vocab:] -> every codec row is -inf.
with torch.no_grad():
    lg = lm_api.decode(LMC, model, torch.zeros(1, 1, int(LMC.width)), live_vocab=LIVE_TEXT, retired_ids=())
risk3_codec_rows_neg_inf = bool(torch.isinf(lg[0, 0, BASE:BASE + NCODE]).all())

# ---- text stream: the tree's own segmentation of its own synthetic corpus
ids = torch.tensor(sysm.segmentation.ids, dtype=torch.long)
text_train, text_held = ids[:-8192], ids[-8192:]

# ---- codec (frozen), offline pre-tokenisation
stride = A.SR // HZ
C.SR[0] = A.SR; C.PRENORM[0] = True
codec = C.Codec(stride, 16, 64, C.FSQ(64, [8, 5, 5, 5])); codec.load_state_dict(torch.load(sys.argv[5] if len(sys.argv) > 5 else os.path.join(HERE, f"codec{HZ}.pt"))); codec.eval()
def enc(x):
    with torch.no_grad():
        return torch.cat([codec.q(codec.enc(x[i:i + 64]))[1][..., 0] for i in range(0, len(x), 64)])
def dec_codes(codes):  # (n, T) ints in [0,1000) -> (n,1,N) audio
    q = codec.q; L = q.levels; hw = (L // 2).float()
    digits = (codes.unsqueeze(-1) // q.basis) % L
    val = (digits.float() - hw) / hw
    with torch.no_grad():
        y = codec.dec(q.pout(val.transpose(1, 2)))
    return F.pad(y, (0, max(0, A.N - y.shape[-1])))[..., :A.N]
t0 = time.time()
aud_tr, cls_tr = A.batch(3000, 2024)
codes_tr = enc(aud_tr); t_enc = time.time() - t0
aud_ho, cls_ho = A.batch(128, 999_777); codes_ho = enc(aud_ho)
FR = codes_tr.shape[1]
cap_ids = [tok_api.tokenize(TOKC, sysm.vocab, (c + ".").encode()).ids for c in A.CLASSES]
cap_len = sum(len(c) for c in cap_ids) / len(cap_ids)
DOT = tok_api.tokenize(TOKC, sysm.vocab, b".").ids[0]

def example(codes, cls, gen):
    a = [OPEN] + [BASE + int(c) for c in codes] + [CLOSE]
    return (list(cap_ids[cls]) + a) if gen else (a + list(cap_ids[cls]))
def build_stream(codes, cls, seed, n_ex, with_w=False):
    r = random.Random(seed); s = []; wts = []
    for _ in range(n_ex):
        i = r.randrange(len(codes)); gen = r.random() < 0.5; e = example(codes[i], int(cls[i]), gen)
        s += e; k = len(cap_ids[int(cls[i])])
        # weight of PREDICTING token j of this example: 1 on the output segment, 0 on the prompt
        wts += ([0.0] * k + [1.0] * (len(e) - k)) if gen else ([0.0] * (FR + 2) + [1.0] * k)
    t = torch.tensor(s, dtype=torch.long)
    return (t, torch.tensor(wts)) if with_w else t
aud_stream, aud_w = build_stream(codes_tr, cls_tr, 1, 40000, with_w=True)
aud_held = build_stream(codes_ho, cls_ho, 2, 600)

def modality(y):  # 0 text, 1 audio (codes + CLOSE), OPEN is predicted in text context
    return ((y >= BASE) & (y != OPEN)).long()
TEXT_ALLOWED = torch.zeros(SLOTS, dtype=torch.bool); TEXT_ALLOWED[:LIVE_TEXT] = True; TEXT_ALLOWED[OPEN] = True
AUD_ALLOWED = torch.zeros(SLOTS, dtype=torch.bool); AUD_ALLOWED[BASE:BASE + NCODE] = True; AUD_ALLOWED[CLOSE] = True
SHARED_ALLOWED = TEXT_ALLOWED | AUD_ALLOWED
NEG = -1e9
def logits_of(x):
    obs = lm_api.embed(LMC, model, x)
    h = lm_api.encode(LMC, model, x, extra=world_api.forecast(WC, world, obs))
    return model.head(model.drop(h)), obs
def masked(lg, y=None, mode=None):
    if not MASKED:
        return lg.masked_fill(~SHARED_ALLOWED, NEG)
    m = modality(y) if mode is None else mode
    allow = torch.where(m.unsqueeze(-1).bool(), AUD_ALLOWED, TEXT_ALLOWED)
    return lg.masked_fill(~allow, NEG)

params = list(model.parameters()) + list(world.parameters())
opt = torch.optim.AdamW(params, lr=2e-3, weight_decay=0.0)
WARM = 300
def lr_at(s): return 2e-3 * min(1, (s + 1) / WARM) * (0.05 + 0.95 * 0.5 * (1 + math.cos(math.pi * min(1, s / STEPS))))

def p_audio(step):
    if ARM == "T": return 0.0
    if ARM in ("Jshared", "Jmask", "Jout"): return 0.5
    if ARM == "Cpure": return 0.0 if step < STEPS // 2 else 1.0
    if ARM == "Creplay": return 0.0 if step < STEPS // 2 else 0.7
    raise SystemExit(ARM)
rng = random.Random(0)
def window(stream):
    a = rng.randrange(0, len(stream) - CTX - 1); w = stream[a:a + CTX + 1]
    wt = aud_w[a + 1:a + CTX + 1] if (stream is aud_stream and ARM == "Jout") else torch.ones(CTX)
    return w[:-1].unsqueeze(0), w[1:].unsqueeze(0), wt

def eval_stream(stream, n_win=48):
    """bits per target token, split by target modality; WORLD loss on the same windows."""
    tot = torch.zeros(2); cnt = torch.zeros(2); wl = 0.0; winv = []
    with torch.no_grad():
        for k in range(n_win):
            a = k * ((len(stream) - CTX - 1) // n_win); w = stream[a:a + CTX + 1]
            x, y = w[:-1].unsqueeze(0), w[1:].unsqueeze(0)
            lg, obs = logits_of(x); lg = masked(lg, y)
            nll = F.cross_entropy(lg.view(-1, SLOTS), y.view(-1), reduction="none") / math.log(2)
            md = modality(y).view(-1)
            for j in (0, 1):
                tot[j] += nll[md == j].sum(); cnt[j] += (md == j).sum()
            ws = world_api.loss_terms(WC, world, obs); wl += float(ws.loss)
            if ws.inv is not None: winv.append(float(ws.inv) if not torch.is_tensor(ws.inv) else float(ws.inv.mean()))
    return dict(bits_text=(tot[0] / cnt[0].clamp_min(1)).item(), bits_audio=(tot[1] / cnt[1].clamp_min(1)).item(),
                n_text=int(cnt[0]), n_audio=int(cnt[1]), world_loss=wl / n_win,
                world_inv=(sum(winv) / len(winv)) if winv else None)

def audio_code_bits_conditioned(shift=0):
    """bits per codec token of held-out clips given their caption (generation direction only).
    shift>0 pairs each clip with ANOTHER class's caption: the gap is what the caption tells the LM."""
    tot = 0.0; n = 0
    with torch.no_grad():
        for i in range(64):
            ci = (int(cls_ho[i]) + shift) % len(A.CLASSES)
            s = torch.tensor(list(cap_ids[ci]) + [OPEN] + [BASE + int(c) for c in codes_ho[i]] + [CLOSE]).unsqueeze(0)
            x, y = s[:, :-1], s[:, 1:]
            lg, _ = logits_of(x); lg = masked(lg, y)
            nll = F.cross_entropy(lg.view(-1, SLOTS), y.view(-1), reduction="none") / math.log(2)
            k0 = len(cap_ids[ci]); tot += nll[k0:k0 + FR].sum().item(); n += FR
    return tot / n

def understand(n=64):
    ok = 0
    with torch.no_grad():
        for i in range(n):
            s = [OPEN] + [BASE + int(c) for c in codes_ho[i]] + [CLOSE]; out = []
            for _ in range(10):
                lg, _ = logits_of(torch.tensor(s).unsqueeze(0))
                lg = masked(lg[:, -1:], mode=torch.zeros(1, 1, dtype=torch.long))
                t = int(lg.argmax(-1)); s.append(t); out.append(t)
                if t == DOT or t >= BASE: break
            ok += int(out == list(cap_ids[int(cls_ho[i])]))
    return ok / n

def generate(per_class=4, temp=1.0, seed=0):
    g = torch.Generator().manual_seed(seed); gens, want, viol = [], [], 0
    with torch.no_grad():
        for c in range(len(A.CLASSES)):
            for _ in range(per_class):
                s = list(cap_ids[c]) + [OPEN]; codes = []
                for _ in range(FR):
                    lg, _ = logits_of(torch.tensor(s).unsqueeze(0))
                    lg = masked(lg[:, -1:], mode=torch.ones(1, 1, dtype=torch.long))[0, 0]
                    t = int(torch.multinomial(F.softmax(lg / temp, -1), 1, generator=g))
                    if not (BASE <= t < BASE + NCODE): viol += 1; t = BASE
                    s.append(t); codes.append(t - BASE)
                gens.append(codes); want.append(c)
    return torch.tensor(gens), torch.tensor(want), viol

probe = P.Probe(); probe.load_state_dict(torch.load(os.path.join(HERE, "probe.pt"))); probe.eval()
def probe_acc(audio, want):
    with torch.no_grad(): return (probe(audio).argmax(-1) == want).float().mean().item()

res = dict(arm=ARM, hz=HZ, steps=STEPS, frames_per_clip=FR, live_text=LIVE_TEXT, bpt=BPT, cap_len_tokens=cap_len,
           risk3_tree_decode_kills_codec_rows=risk3_codec_rows_neg_inf, lm_mask_dead_rows_default=bool(LMC.mask_dead_rows), encode_s_per_audio_s=t_enc / 3000,
           setup_s=round(time.time() - t_setup, 1), curve=[])
rec = dec_codes(codes_ho[:128])
res["probe_real"] = probe_acc(aud_ho, cls_ho); res["probe_codec_recon"] = probe_acc(rec, cls_ho)
res["probe_random_codes"] = probe_acc(dec_codes(torch.randint(0, NCODE, (64, FR))), cls_ho[:64])
res["codec_mel_heldout"] = C.mel_dist(aud_ho, rec).item()

t0 = time.time(); ev_every = max(1, STEPS // 6); step_time = 0.0
for step in range(STEPS):
    for gp in opt.param_groups: gp["lr"] = lr_at(step)
    ts = time.time()
    x, y, wt = window(aud_stream if rng.random() < p_audio(step) else text_train)
    lg, obs = logits_of(x); lg = masked(lg, y)
    ce = F.cross_entropy(lg.view(-1, SLOTS), y.view(-1), reduction="none")
    loss = (ce * wt).sum() / wt.sum().clamp_min(1.0) + world_api.loss_terms(WC, world, obs).loss
    opt.zero_grad(); loss.backward(); opt.step(); step_time += time.time() - ts
    if (step + 1) % ev_every == 0 or step + 1 == STEPS or (ARM.startswith("C") and step + 1 == STEPS // 2):
        et = eval_stream(text_held); ea = eval_stream(aud_held)
        row = dict(step=step + 1, text_bits_tok=et["bits_text"], text_bpb=et["bits_text"] / BPT,
                   aud_bits_code=ea["bits_audio"], aud_caption_bits=ea["bits_text"],
                   world_loss_text=et["world_loss"], world_loss_aud=ea["world_loss"],
                   world_inv_text=et["world_inv"], world_inv_aud=ea["world_inv"], wall=round(time.time() - t0, 1))
        res["curve"].append(row); print(json.dumps(row), flush=True)
res["ms_per_window_train"] = 1000 * step_time / STEPS
if ARM != "T":
    res["aud_bits_per_code_given_caption"] = audio_code_bits_conditioned()
    res["aud_bits_per_code_wrong_caption"] = audio_code_bits_conditioned(shift=7)
    res["aud_bits_per_second_given_caption"] = res["aud_bits_per_code_given_caption"] * HZ
    res["understand_exact_caption_acc"] = understand()
    tg = time.time(); gcodes, want, viol = generate(); res["gen_s_per_clip"] = (time.time() - tg) / len(want)
    gaud = dec_codes(gcodes)
    res["gen_probe_acc"] = probe_acc(gaud, want); res["gen_format_violations"] = viol
    res["gen_code_perplexity"] = 2 ** (-(lambda p: (p[p > 0] * p[p > 0].log2()).sum().item())(torch.bincount(gcodes.view(-1), minlength=NCODE).float() / gcodes.numel()))
    g2, w2, _ = generate(temp=0.7, seed=1); res["gen_probe_acc_t0.7"] = probe_acc(dec_codes(g2), w2)
    g3, w3, _ = generate(temp=0.3, seed=2); res["gen_probe_acc_t0.3"] = probe_acc(dec_codes(g3), w3)
    # the same probe on the codec's reconstruction of REAL held-out clips of the SAME classes = the ceiling
    torch.save(dict(model=model.state_dict()), OUT.replace(".json", ".pt"))
res["wall_s"] = round(time.time() - t_setup, 1)
print(json.dumps({k: v for k, v in res.items() if k != "curve"}))
json.dump(res, open(OUT, "w"), indent=1)
