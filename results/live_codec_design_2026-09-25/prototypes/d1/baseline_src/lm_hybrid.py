"""The discrete half of the hybrid: a width-128 GRU LM over ONE id space (bytes | specials | reserved
codec block) trained phase-wise: P1 text only, then P2 audio tasks (text->audio generation and
audio->text understanding). Arms: joint softmax vs typed-segment modality mask, +/- text replay.

Usage: lm_hybrid.py ARM P1_STEPS P2_STEPS OUT.json   (ARM in joint | mask | mask_replay | joint_replay)
"""
import os, sys, time, json, math, copy
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import synth as S
import importlib; TC = importlib.import_module(os.environ.get("HYB_CODEC_MOD", "spec_codec"))
import corpus as CO

T2A, A2T, AUD_B, AUD_E, EOT, PAD = 256, 257, 258, 259, 260, 261
CODE_BASE, NCODE = 264, 1000
V = CODE_BASE + NCODE
L = 96          # window length (positions)
W = int(os.environ.get("HYB_W", "128"))  # LM width (LM_WIDTH default 128)
FRAMES = 50

TEXT_OK = torch.zeros(V, dtype=torch.bool); TEXT_OK[:CODE_BASE] = True; TEXT_OK[PAD] = False
AUD_OK = torch.zeros(V, dtype=torch.bool); AUD_OK[CODE_BASE:] = True; AUD_OK[AUD_E] = True


class LM(nn.Module):
    def __init__(self):
        super().__init__()
        self.emb = nn.Embedding(V, W); self.rnn = nn.GRU(W, W, 2, batch_first=True); self.head = nn.Linear(W, V)
    def forward(self, x, h=None):
        o, h = self.rnn(self.emb(x), h)
        return self.head(o), h


def seq_t2a(p, codes):
    s = [T2A] + list(S.caption(p).encode()) + [AUD_B] + [CODE_BASE + int(c) for c in codes] + [AUD_E]
    mod = [0] * (len(s) - FRAMES - 1) + [1] * (FRAMES + 1)  # modality of each TOKEN
    return s, mod


def seq_a2t(p, codes):
    s = [A2T, AUD_B] + [CODE_BASE + int(c) for c in codes] + [AUD_E] + list(S.caption(p).encode()) + [EOT]
    mod = [0, 0] + [1] * (FRAMES + 1) + [0] * (len(s) - FRAMES - 3)
    return s, mod


def pad(s, mod):
    s = s[:L + 1]; mod = mod[:L + 1]
    n = len(s)
    return s + [PAD] * (L + 1 - n), mod + [0] * (L + 1 - n), n


def audio_batch(ps, cs, idx):
    X, M, N = [], [], []
    for j, i in enumerate(idx):
        f = seq_t2a if j % 2 == 0 else seq_a2t
        s, m, n = pad(*f(ps[i], cs[i])); X.append(s); M.append(m); N.append(n)
    X = torch.tensor(X); M = torch.tensor(M)
    valid = torch.arange(L + 1).unsqueeze(0) < torch.tensor(N).unsqueeze(1)
    return X, M, valid


def text_batch(text, g, bs):
    starts = torch.randint(0, len(text) - L - 2, (bs,), generator=g).tolist()
    X = torch.tensor([list(text[s:s + L + 1]) for s in starts])
    return X, torch.zeros_like(X), torch.ones_like(X, dtype=torch.bool)


def masked_logits(logits, tmod, use_mask):
    if not use_mask:
        return logits
    allow = torch.where(tmod.unsqueeze(-1) == 1, AUD_OK, TEXT_OK)
    return logits.masked_fill(~allow, float("-inf"))


def loss_fn(model, X, M, valid, use_mask):
    logits, _ = model(X[:, :-1])
    lg = masked_logits(logits, M[:, 1:], use_mask)
    y = X[:, 1:]; v = valid[:, 1:]
    nll = F.cross_entropy(lg.reshape(-1, V), y.reshape(-1), reduction="none").view_as(y)
    return nll, v


@torch.no_grad()
def eval_text(model, text, use_mask, nwin=60):
    g = torch.Generator().manual_seed(77); tot = 0.0; n = 0
    for _ in range(nwin // 20):
        X, M, v = text_batch(text, g, 20)
        nll, v = loss_fn(model, X, M, v, use_mask)
        tot += nll[:, 16:].sum().item(); n += nll[:, 16:].numel()  # skip warm-up positions
    return tot / n / math.log(2)


@torch.no_grad()
def eval_audio_bits(model, ps, cs, use_mask):
    idx = list(range(len(ps)))
    X, M, valid = audio_batch(ps, cs, idx)
    nll, v = loss_fn(model, X, M, valid, use_mask)
    tm = M[:, 1:]; y = X[:, 1:]
    code = (y >= CODE_BASE) & v
    t2a = torch.zeros_like(v); t2a[0::2] = True
    cap_a2t = (tm == 0) & v & (~t2a) & (torch.arange(L).unsqueeze(0) > FRAMES + 2)
    return dict(bits_per_code_t2a=nll[code & t2a].mean().item() / math.log(2),
                bits_per_code_a2t=nll[code & ~t2a].mean().item() / math.log(2),
                caption_bits_per_byte_a2t=nll[cap_a2t].mean().item() / math.log(2))


@torch.no_grad()
def understand(model, ps, cs, use_mask):
    """A2T greedy captioning; exact attribute accuracy against the TRUE generating parameters."""
    B = len(ps)
    prompt = torch.tensor([[A2T, AUD_B] + [CODE_BASE + int(c) for c in cs[i]] + [AUD_E] for i in range(B)])
    logits, h = model(prompt)
    out = [[] for _ in range(B)]; done = [False] * B
    nxt = logits[:, -1]
    for _ in range(32):
        lg = masked_logits(nxt, torch.zeros(B, dtype=torch.long), use_mask)
        tok = lg.argmax(-1)
        for i in range(B):
            if not done[i]:
                if int(tok[i]) == EOT or int(tok[i]) >= 256:
                    done[i] = True
                else:
                    out[i].append(int(tok[i]))
        logits, h = model(tok.unsqueeze(1), h); nxt = logits[:, -1]
    res = {"train_combos": [], "heldout_combos": []}
    for i in range(B):
        cap = bytes(out[i]).decode(errors="replace")
        d = S.attr_acc(S.parse_caption(cap), ps[i])
        res["heldout_combos" if ps[i] in S.HELDOUT_COMBOS else "train_combos"].append(d)
    return {k: _agg(v) for k, v in res.items()}


def _agg(ds):
    if not ds:
        return {}
    return {k: round(sum(d[k] for d in ds) / len(ds), 3) for k in ds[0]} | {"n": len(ds)}


@torch.no_grad()
def generate(model, codec, use_mask, reps=3, temp=1.0, seed=5):
    """T2A sampling from each caption; decode with the frozen codec; score with the analytic probe."""
    g = torch.Generator().manual_seed(seed)
    ps = [p for p in S.all_combos() for _ in range(reps)]
    B = len(ps)
    caps = [[T2A] + list(S.caption(p).encode()) + [AUD_B] for p in ps]
    # captions differ in length: run each prompt separately to get its hidden state (cheap), then batch
    hs, last = [], []
    for c in caps:
        lg, h = model(torch.tensor([c])); hs.append(h); last.append(lg[:, -1])
    h = torch.cat(hs, 1); nxt = torch.cat(last, 0)
    codes = torch.zeros(B, FRAMES, dtype=torch.long); invalid = 0
    for t in range(FRAMES):
        lg = masked_logits(nxt, torch.ones(B, dtype=torch.long), use_mask) / temp
        tok = torch.multinomial(lg.softmax(-1), 1, generator=g)[:, 0]
        bad = tok < CODE_BASE
        invalid += int(bad.sum())
        if bad.any():  # joint arm: a non-code id inside an audio segment; replace by best code
            tok = torch.where(bad, lg[:, CODE_BASE:].argmax(-1) + CODE_BASE, tok)
        codes[:, t] = tok - CODE_BASE
        logits, h = model(tok.unsqueeze(1), h); nxt = logits[:, -1]
    wav = CO.decode_codes(codec, codes)
    res = {"train_combos": [], "heldout_combos": []}
    for i, p in enumerate(ps):
        d = S.attr_acc(S.probe(wav[i]), p)
        res["heldout_combos" if p in S.HELDOUT_COMBOS else "train_combos"].append(d)
    out = {k: _agg(v) for k, v in res.items()}
    out["invalid_id_rate"] = round(invalid / (B * FRAMES), 4)
    out["distinct_codes"] = int(torch.unique(codes).numel())
    return out


def main():
    arm, p1, p2, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    use_mask = arm.startswith("mask"); replay = arm.endswith("replay")
    D = torch.load(os.path.join(HERE, os.environ.get("HYB_CORPUS", "corpus.pt")))
    codec = TC.make_codec(); codec.load_state_dict(torch.load(os.path.join(HERE, os.environ.get("HYB_CODEC", "codec.pt")))); codec.eval()
    tr_p, trc, ev_p, evc = D["tr_p"], D["trc"], D["ev_p"], D["evc"]
    torch.manual_seed(0); model = LM()
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=0.0)
    g = torch.Generator().manual_seed(3); bs = 16
    rec = dict(arm=arm, p1=p1, p2=p2, V=V, L=L, W=W, params=sum(p.numel() for p in model.parameters()))
    ev_train = [i for i, p in enumerate(ev_p) if p not in S.HELDOUT_COMBOS]
    # ---------------- P1: text only
    t0 = time.time(); curve = []
    for step in range(p1):
        X, M, v = text_batch(D["text_tr"], g, bs)
        nll, v = loss_fn(model, X, M, v, use_mask)
        loss = nll[v].mean(); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if step % 250 == 0:
            curve.append(("P1", step, round(loss.item() / math.log(2), 3)))
    rec["p1_s_per_step"] = round((time.time() - t0) / max(1, p1), 4)
    rec["after_p1"] = dict(text_bpb=round(eval_text(model, D["text_ev"], use_mask), 4))
    print(arm, "after P1", rec["after_p1"], flush=True)
    # ---------------- P2: audio tasks (+ optional 25% text replay)
    t0 = time.time(); ntr = len(tr_p)
    for step in range(p2):
        idx = torch.randint(0, ntr, (bs,), generator=g).tolist()
        X, M, v = audio_batch(tr_p, trc, idx)
        if replay:
            k = bs // 4
            Xt, Mt, vt = text_batch(D["text_tr"], g, k)
            X = torch.cat([X[:bs - k], Xt]); M = torch.cat([M[:bs - k], Mt]); v = torch.cat([v[:bs - k], vt])
        nll, v = loss_fn(model, X, M, v, use_mask)
        loss = nll[v].mean(); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if step % 250 == 0:
            curve.append(("P2", step, round(loss.item() / math.log(2), 3)))
            print(curve[-1], round(time.time() - t0), flush=True)
    p2_s = time.time() - t0
    rec["p2_s_per_step"] = round(p2_s / max(1, p2), 4)
    rec["p2_s_per_window"] = round(p2_s / max(1, p2) / bs, 5)
    model.eval()
    rec["after_p2"] = dict(text_bpb=round(eval_text(model, D["text_ev"], use_mask), 4),
                           text_bpb_evaluated_with_mask=round(eval_text(model, D["text_ev"], True), 4))
    rec["after_p2"].update({k: round(v, 4) for k, v in eval_audio_bits(model, [ev_p[i] for i in ev_train], evc[ev_train], use_mask).items()})
    rec["understand_a2t"] = understand(model, ev_p, evc, use_mask)
    t1 = time.time()
    rec["generate_t2a_temp1"] = generate(model, codec, use_mask, temp=1.0)
    rec["generate_t2a_temp0.7"] = generate(model, codec, use_mask, temp=0.7)
    rec["generate_s"] = round(time.time() - t1, 1)
    rec["curve"] = curve
    rec["forgetting_text_bpb"] = round(rec["after_p2"]["text_bpb"] - rec["after_p1"]["text_bpb"], 4)
    print(json.dumps(rec, indent=1)); json.dump(rec, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
