"""Score a codec checkpoint on the fixed eval clips of both areas (same sets run_arm.py uses):
mel distance, analytic-probe exact on reconstructions, codes used, entropy, adjacent-frame repeat rate.
Usage: python eval_codec.py ck/codec25.pt ck/codec50.pt"""
import os, sys, json
os.environ.setdefault("OMP_NUM_THREADS", "1")
import torch
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import synth as S, melody as M, codec as K, codec_lib as C


def sets():
    out = {}
    for area, mod, seed, reps in (("A", S, 555, 4), ("B", M, 556, 6)):
        ge = torch.Generator().manual_seed(seed); ps, xs = [], []
        for p in mod.all_combos():
            for _ in range(reps):
                ps.append(p); xs.append(mod.render(p, ge))
        out[area] = (mod, ps, torch.stack(xs))
    return out


def main():
    ev = sets(); res = {}
    for path in sys.argv[1:]:
        ck = torch.load(path); m = K.make_codec(ck["stride"]); m.load_state_dict(ck["model"]); m.eval()
        r = dict(fps=m.fps)
        for area, (mod, ps, X) in ev.items():
            codes, b = K.encode(m, X)
            Y = K.decode_codes(m, codes)
            ex = sum(mod.attr_acc(mod.probe(Y[i]), ps[i])["exact"] for i in range(len(ps))) / len(ps)
            h = torch.bincount(codes.reshape(-1), minlength=1000).float(); pr = h / h.sum()
            ent = -(pr[pr > 0] * pr[pr > 0].log2()).sum().item()
            rep = (codes[:, 1:] == codes[:, :-1]).float().mean().item()
            sil = torch.zeros(len(ps), S.SR) + 1e-4 * torch.randn(len(ps), S.SR, generator=torch.Generator().manual_seed(0))
            r[area] = dict(mel=round(C.mel_dist(X.unsqueeze(1), Y.unsqueeze(1)).item(), 4),
                           mel_silence=round(C.mel_dist(X.unsqueeze(1), sil.unsqueeze(1)).item(), 4),
                           recon_probe_exact=round(ex, 3), codes_used=int((h > 0).sum()), entropy_bits=round(ent, 3),
                           adjacent_repeat=round(rep, 3))
        res[os.path.basename(path)] = r
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
