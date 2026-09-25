"""Codec-only drift sweep for the two-timescale design (no LM): the nested student keeps training from the
codec-phase checkpoint (tones for A codec steps, then melody+tones 50/50 for B codec steps); EMA teachers
at several decays track it. On a fixed probe set we read, per teacher: per-frame code flip fraction over
time, latent drift, reconstruction error per area. At the start and end we read the rate allocation for
several tolerances rho (positions/s by kind, mel with Griffin-Lim, analytic-probe exact on reconstructions).
Usage: python3 drift.py SEED OUT.json [A B]"""
import os, sys, time, json, copy
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import d3lib as D

DECAYS = [0.0, 0.9, 0.99, 0.995, 0.999, 1.0]
RHOS = [0.0, 0.05, 0.1, 0.2, 0.5, 1.0]


@torch.no_grad()
def alloc_table(m, pr):
    out = {}
    for tag, kw in [(f"rho{r}", dict(rho=r)) for r in RHOS] + [(f"force{s}", dict(rho=0.0, force=s)) for s in (1, 2, 4)]:
        row = {}
        for ar in ("tones", "melody"):
            ps, X = pr[ar]
            ids, smap, z = m.encode(X, **kw)
            Y = m.decode(ids)
            A = D.AREAS[ar]
            acc = [A["acc"](A["probe"](Y[i]), p) for i, p in enumerate(ps)]
            kinds = {}
            for i, p in enumerate(ps):
                kinds.setdefault(D.kind_of(ar, p), []).append(len(ids[i]))
            row[ar] = dict(pos_per_s=round(sum(len(x) for x in ids) / len(ids), 2),
                           by_kind={k: round(sum(v) / len(v), 2) for k, v in kinds.items()},
                           mel=round(D.mel(X, Y), 4), probe_exact=round(sum(a["exact"] for a in acc) / len(acc), 3),
                           stride_frac={s: round((smap == s).float().mean().item(), 3) for s in (1, 2, 4)})
        out[tag] = row
    return out


def main():
    seed = int(sys.argv[1]); outp = sys.argv[2]
    A_ = int(sys.argv[3]) if len(sys.argv) > 3 else 500; B_ = int(sys.argv[4]) if len(sys.argv) > 4 else 500
    st = torch.load(os.path.join(HERE, "ck", f"nested_s{seed}.pt"))
    m = D.make_codec("nested", seed); m.load_state_dict(st["student"]); m.eval()
    opt = torch.optim.AdamW(m.parameters(), lr=3e-4, betas=(0.8, 0.99)); opt.load_state_dict(st["opt"])
    for gp in opt.param_groups:
        gp["lr"] = 3e-4
    T = {d: D.Teacher(m, d) for d in DECAYS}
    pr = {ar: D.eval_set(ar, per, sd) for ar, per, sd in (("tones", 1, 777), ("melody", 2, 778))}
    g = torch.Generator().manual_seed(900 + seed)
    rec = dict(seed=seed, A=A_, B=B_, decays=DECAYS, alloc_start=alloc_table(T[0.995].m, pr), curve=[])
    hist = {d: [] for d in DECAYS}
    t0 = time.time()
    for step in range(0, A_ + B_ + 1):
        if step % 50 == 0:
            row = dict(codec_step=step)
            for d, t in T.items():
                cur = {}
                for ar in ("tones", "melody"):
                    ps, X = pr[ar]
                    ids, smap, z = t.m.encode(X, rho=0.1)
                    idsf, _, _ = t.m.encode(X, rho=0.0, force=2)
                    fc = D.frame_codes(ids, "nested"); ff = D.frame_codes(idsf, "nested")
                    lmr = t.m.decode(ids, want_lm=True)[..., :50]
                    cur[ar] = dict(fc=fc, ff=ff, z=z)
                    row[f"{d}/{ar}/l1"] = round((lmr - D.logmag(X)[..., :50]).abs().mean().item(), 4)
                    row[f"{d}/{ar}/pos"] = round(sum(len(x) for x in ids) / len(ids), 2)
                    for back, key in ((1, "d50"), (5, "d250"), (10, "d500")):
                        if len(hist[d]) >= back:
                            old = hist[d][-back][ar]
                            row[f"{d}/{ar}/flip_{key}"] = round((old["fc"] != fc).float().mean().item(), 4)
                            row[f"{d}/{ar}/flipS2_{key}"] = round((old["ff"] != ff).float().mean().item(), 4)
                            row[f"{d}/{ar}/zdrift_{key}"] = round(((z - old["z"]).norm() / z.norm()).item(), 4)
                hist[d].append(cur); hist[d] = hist[d][-10:]
            rec["curve"].append(row)
            print(step, round(time.time() - t0), {k: v for k, v in row.items() if k.startswith("0.995/") or k.startswith("0.0/")}, flush=True)
        if step == A_ + B_:
            break
        mix = [("tones", 1.0)] if step < A_ else [("melody", 1.0), ("tones", 1.0)]
        m.train(); xb = D.media_batch(g, mix, 16)
        loss, codes = m.train_loss(xb, g)
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); m.eval()
        for t in T.values():
            t.update(m)
    rec["train_s"] = round(time.time() - t0)
    rec["alloc_end"] = alloc_table(T[0.995].m, pr)
    rec["alloc_end_frozen"] = alloc_table(T[1.0].m, pr)
    json.dump(rec, open(outp, "w"), indent=1)
    print("DONE", rec["train_s"])


if __name__ == "__main__":
    main()
