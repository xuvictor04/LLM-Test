"""Build and cache the tokenised corpus with the FROZEN codec: codes (discrete stream side) and the
pre-quantisation encoder latents (continuous WORLD side), plus an order-2 Markov text area."""
import os, sys, time, json
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import synth as S
import importlib; TC = importlib.import_module(os.environ.get("HYB_CODEC_MOD", "spec_codec"))


def decode_codes(m, codes):
    """(B, T) FSQ code ids -> waveform (B, n). Inverse of FSQ's mixed-radix packing."""
    q = m.q
    L = q.levels; basis = q.basis; hw = (L // 2).float()
    digits = (codes.unsqueeze(-1) // basis) % L  # B T d
    qv = (digits.float() - hw) / hw
    zq = q.pout(qv.transpose(1, 2))
    y = m.dec(zq)
    n = codes.shape[1] * 160
    y = torch.nn.functional.pad(y, (0, max(0, n - y.shape[-1])))[..., :n]
    return y[:, 0]


def markov_text(n, seed):
    alpha = "etaoinshrdlu .,"
    g = torch.Generator().manual_seed(1234)  # the PROCESS is fixed; `seed` picks the sample path
    k = len(alpha)
    # deterministic Dirichlet via gammas from our generator
    gam = -torch.log(torch.rand(k * k, k, generator=g).clamp_min(1e-9))
    gam = gam ** (1 / 0.3)
    P = gam / gam.sum(-1, keepdim=True)
    gs = torch.Generator().manual_seed(seed)
    cdf = P.cumsum(-1).tolist(); u = torch.rand(n, generator=gs).tolist()
    a, b = 0, 1; out = []
    import bisect
    for i in range(n):
        row = cdf[a * k + b]
        c = min(k - 1, bisect.bisect_left(row, u[i]))
        out.append(alpha[c]); a, b = b, c
    return "".join(out).encode()


def build(codec_path, out, n_train=2400, per_combo_eval=4):
    m = TC.make_codec(); m.load_state_dict(torch.load(codec_path)); m.eval()
    t0 = time.time()
    g = torch.Generator().manual_seed(11)
    tr_p, tr_x = [], []
    trc_parts = []
    for _ in range(n_train):
        p, x = S.sample(g); tr_p.append(p); tr_x.append(x)
    ge = torch.Generator().manual_seed(555)
    ev_p, ev_x = [], []
    for p in S.all_combos():
        for _ in range(per_combo_eval):
            ev_p.append(p); ev_x.append(S.render(p, ge))
    gen_s = time.time() - t0
    def enc(xs):
        C, Z = [], []
        with torch.no_grad():
            for i in range(0, len(xs), 64):
                X = torch.stack(xs[i:i + 64]).unsqueeze(1)
                z = m.enc(X); _, codes, _ = m.q(z)
                C.append(codes[..., 0]); Z.append(z.transpose(1, 2)[:, :, :0] if os.environ.get('HYB_NOLAT') else z.transpose(1, 2))
        return torch.cat(C), torch.cat(Z)
    t1 = time.time(); trc, trz = enc(tr_x); evc, evz = enc(ev_x); enc_s = time.time() - t1
    text_tr = markov_text(300_000, 1); text_ev = markov_text(20_000, 2)
    torch.save(dict(tr_p=tr_p, trc=trc, trz=trz, ev_p=ev_p, evc=evc, evz=evz, ev_x=torch.stack(ev_x),
                    text_tr=text_tr, text_ev=text_ev), out)
    info = dict(n_train=n_train, n_eval=len(ev_p), gen_s=round(gen_s, 1), encode_s=round(enc_s, 1),
                audio_s_encoded=n_train + len(ev_p), encode_rtf=round(enc_s / (n_train + len(ev_p)), 4),
                codes_per_clip=int(trc.shape[1]), latent_dim=int(trz.shape[-1]),
                train_codes_used=int(torch.unique(trc).numel()))
    print(json.dumps(info)); json.dump(info, open(out + ".json", "w"))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], n_train=int(sys.argv[3]) if len(sys.argv) > 3 else 2400)
