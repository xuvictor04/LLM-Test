#!/usr/bin/env python3
"""probe_signature.py -- IS THE DOMAIN SIGNATURE CORPUS-DISCRIMINATIVE AT ALL?

The self-assembly thesis needs one thing from `sig_of`: two windows of the SAME corpus must be CLOSER than two
windows of DIFFERENT corpora, at the scale the assembler queries it (a WIN-byte window, or the mean of a short
run, against a 40-window centroid). Domain COUNTS cannot answer this -- a count is the joint outcome of the
signature, SHIFT_DIST, SUSTAIN, NEW_DIST, merge and the MAX_DOMAINS cap. This probe measures the signature
geometry DIRECTLY, with the TRUE corpus label known for every window, and never runs the assembler at all.

It answers:
  (a) mean +- sd cosine distance WITHIN a corpus and BETWEEN corpora
  (b) separability of those two distributions: AUC (Mann-Whitney, tie-corrected) and d-prime
  (c) the same at several ENC_POS_MAX values -- does a wider InfoNCE positive radius buy corpus-scale invariance
  (d) the fraction of WITHIN-corpus pairs beyond NEW_DIST (=would spawn a new domain), and the operational
      version of the same number: a held-out window vs the centroid of 40 windows of its own corpus drawn from
      DIFFERENT segments (exactly the _assign query on re-entry), for run-smoothing R = 1, 2, 4 windows.
Plus two diagnostics the above implies but does not isolate:
  (e) same-corpus distance as a function of BYTE SEPARATION -- if the encoder's invariance radius tracks
      ENC_POS_MAX rather than the corpus, distance rises with separation and saturates near the between-corpus
      level. That is the encoder failing, not the assembler.
  (f) adjacent-window distance WITHIN a segment vs ACROSS a true splice boundary, against SHIFT_DIST -- the
      boundary detector's own signal-to-noise (proxy: previous window, not the EMA run_sig).
  (g) CONTROLS: the untrained bigram-histogram and frozen-embedding signatures (SIG_MODE=bigram/frozen). If a
      trivial featurizer separates the corpora and the learned encoder does not, the encoder is the problem.

Reads the SAME code path as the run: self_organize.build_stream / SigEncoder / contrastive_step / sig_of_batch.
CPU default is ~15 min. On the GPU, raise PROBE_STREAM_LEN / PROBE_STEPS.

  python3 probe_signature.py
  DEVICE=cuda PROBE_STREAM_LEN=1000000 PROBE_STEPS=0,200,1000,4000,16000 PROBE_POSMAX=2,4,8,16 \
      DATA_DIR=/path/to/data python3 probe_signature.py
"""
import os, sys, json, math, random, time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# ---- configure self_organize BEFORE importing it (it builds corpora at import time) -------------------------
os.environ.setdefault("DATA_MODE", "real")
os.environ.setdefault("DOMAINS", "eng,py,num,c")
os.environ.setdefault("DATA_DIR", os.path.join(_HERE, "data"))
os.environ["STREAM_LEN"] = os.environ.get("PROBE_STREAM_LEN", os.environ.get("STREAM_LEN", "120000"))
os.environ.setdefault("PHASED", "0")

import torch
import torch.nn.functional as F
import self_organize as S

WIN, SIG_D, NEW_DIST, SHIFT_DIST = S.WIN, S.SIG_D, S.NEW_DIST, S.SHIFT_DIST
DEV = S.DEV
SEED      = int(os.environ.get("PROBE_SEED", 0))
STEPS     = [int(x) for x in os.environ.get("PROBE_STEPS", "0,200,1000,4000").split(",")]
POSMAX    = [int(x) for x in os.environ.get("PROBE_POSMAX", "2,4,8").split(",")]        # multiples of WIN
K_CENT    = int(os.environ.get("PROBE_K_CENT", S.DOM_WINS))     # windows per centroid (= the domain reservoir)
MAXEVAL   = int(os.environ.get("PROBE_MAXEVAL", 4000))          # cap on eval windows PER CLASS
ENC_LR    = float(os.environ.get("PROBE_ENC_LR", 2e-3))         # matches main(): AdamW(enc, lr=2e-3)
RUNS      = [int(x) for x in os.environ.get("PROBE_RUNS", "1,2,4").split(",")]  # run-smoothing widths
SWEEP     = bool(int(os.environ.get("PROBE_SWEEP", 1)))         # 0 = skip (a)-(g), run ONLY the rekey-lag probe
DRIFT_ON  = bool(int(os.environ.get("PROBE_DRIFT_ON", 1)))      # append the rekey-lag probe after the sweep
OUT_JSON  = os.environ.get("PROBE_JSON", "")


# ---------------- stream + labelled window universe ----------------------------------------------------------
def build_universe():
    """Grid windows (stride WIN -- exactly what the main loop steps over). `gp` is EVERY grid window (the boundary
    detector sees those too); `pos/lab/seg` are the subset whose TRUE corpus label is unambiguous (no splice inside)."""
    import bisect
    random.seed(SEED); torch.manual_seed(SEED)
    stream, labels, sw = S.build_stream()
    S.set_enc_tensor(stream)
    starts = sorted(int(x) for x in sw)                          # splice-segment starts
    gp = list(range(0, len(stream) - WIN, WIN))
    pos, lab, seg, pidx = [], [], [], []
    for k, p in enumerate(gp):
        a = labels[p]
        if labels[p + WIN - 1] != a: continue                    # window straddles a splice -> impure, drop
        si = bisect.bisect_right(starts, p) - 1
        if bisect.bisect_right(starts, p + WIN - 1) - 1 != si: continue   # same label, different segment: still impure
        pos.append(p); lab.append(a); seg.append(si); pidx.append(k)
    # adjacency categories for consecutive grid windows (k, k+1): 0 = no splice in the 2*WIN span,
    # 1 = splice joining two segments of the SAME corpus, 2 = splice joining DIFFERENT corpora.
    acat = []
    for k in range(len(gp) - 1):
        p = gp[k]; hi = min(p + 2 * WIN, len(stream)) - 1
        nsp = bisect.bisect_left(starts, hi + 1) - bisect.bisect_right(starts, p)
        acat.append(0 if nsp == 0 else (1 if labels[p] == labels[hi] else 2))
    return {"stream": stream, "labels": labels, "starts": starts, "gp": gp, "pos": pos, "lab": lab,
            "seg": seg, "pidx": pidx, "acat": acat}


def split_pools(pos, lab, seg, nclass):
    """Split SEGMENTS (not windows) per class into a centroid pool and an eval pool, so the centroid a query is
    scored against never contains a window from the query's own segment -- i.e. the RE-ENTRY case."""
    rng = random.Random(SEED + 1)
    by_seg = {}
    for i, (p, y, s) in enumerate(zip(pos, lab, seg)):
        by_seg.setdefault((y, s), []).append(i)
    cent_idx = {c: [] for c in range(nclass)}
    eval_idx = {c: [] for c in range(nclass)}
    for c in range(nclass):
        segs = sorted([k[1] for k in by_seg if k[0] == c]); rng.shuffle(segs)
        need, si = K_CENT, 0
        while need > 0 and si < len(segs) - 1:                   # keep >=1 segment for eval
            take = by_seg[(c, segs[si])]
            cent_idx[c] += take[:need]; need -= len(take[:need]); si += 1
        for s in segs[si:]:
            eval_idx[c] += by_seg[(c, s)]
    return cent_idx, eval_idx


# ---------------- metrics ------------------------------------------------------------------------------------
def _auc(w, b):
    """P(between-pair distance > within-pair distance) + 0.5 P(tie); Mann-Whitney U with tie-averaged ranks."""
    if w.numel() == 0 or b.numel() == 0: return float("nan")
    x = torch.cat([w, b]).double()
    y = torch.cat([torch.zeros(w.numel()), torch.ones(b.numel())]).to(x.device)
    o = torch.argsort(x); xs, ys = x[o], y[o]
    vals, cnt = torch.unique_consecutive(xs, return_counts=True)
    start = torch.cumsum(torch.cat([torch.zeros(1, dtype=cnt.dtype, device=cnt.device), cnt[:-1]]), 0)
    ranks = torch.repeat_interleave((2 * start.double() + cnt.double() + 1) / 2.0, cnt)
    nb, nw = float(b.numel()), float(w.numel())
    U = float(ranks[ys == 1].sum()) - nb * (nb + 1) / 2.0
    return U / (nw * nb)


def _dprime(w, b):
    if w.numel() < 2 or b.numel() < 2: return float("nan")
    vw, vb = float(w.var(unbiased=True)), float(b.var(unbiased=True))
    den = math.sqrt(max(1e-12, 0.5 * (vw + vb)))
    return (float(b.mean()) - float(w.mean())) / den


def _ms(t):
    return (float(t.mean()), float(t.std(unbiased=True))) if t.numel() > 1 else (float("nan"), float("nan"))


def pair_metrics(Z, y, seg, p):
    """All pairwise (a),(b),(d),(e) numbers for a matrix of unit signatures."""
    n = Z.size(0)
    iu = torch.triu_indices(n, n, offset=1, device=Z.device)
    d = (1.0 - Z @ Z.t())[iu[0], iu[1]]
    same = y[iu[0]] == y[iu[1]]
    sseg = seg[iu[0]] == seg[iu[1]]
    gap = (p[iu[0]] - p[iu[1]]).abs().float()
    w, b = d[same], d[~same]
    mw, sw_ = _ms(w); mb, sb = _ms(b)
    out = {"n_win": n, "n_within": int(w.numel()), "n_between": int(b.numel()),
           "within_mean": mw, "within_sd": sw_, "between_mean": mb, "between_sd": sb,
           "gap": mb - mw, "auc": _auc(w, b), "dprime": _dprime(w, b),
           "within_gt_NEWDIST": float((w > NEW_DIST).float().mean()),
           "between_lt_NEWDIST": float((b < NEW_DIST).float().mean()),
           "within_same_seg_mean": _ms(d[same & sseg])[0],
           "within_diff_seg_mean": _ms(d[same & ~sseg])[0],
           "within_diff_seg_gt_NEWDIST": float((d[same & ~sseg] > NEW_DIST).float().mean())
           if d[same & ~sseg].numel() else float("nan")}
    bins = [(0, 2 * WIN), (2 * WIN, 8 * WIN), (8 * WIN, 32 * WIN), (32 * WIN, 128 * WIN), (128 * WIN, 1 << 30)]
    out["sep_curve"] = []
    for lo, hi in bins:
        m = same & (gap >= lo) & (gap < hi)
        out["sep_curve"].append((lo, hi, int(m.sum()), _ms(d[m])[0]))
    return out


def centroid_metrics(Q, qy, C):
    """(d) operational: query (window, or mean of an R-window run) vs the 40-window centroid of each corpus."""
    Dq = 1.0 - Q @ C.t()
    ar = torch.arange(Q.size(0), device=Q.device)
    d_own = Dq[ar, qy]
    Do = Dq.clone(); Do[ar, qy] = float("inf")
    d_oth = Do.min(1).values
    return {"n": int(Q.size(0)), "d_own": float(d_own.mean()), "d_own_sd": float(d_own.std(unbiased=True)),
            "d_other": float(d_oth.mean()), "margin": float((d_oth - d_own).mean()),
            "nn_acc": float((Dq.argmin(1) == qy).float().mean()),
            "spawn_rate": float((d_own > NEW_DIST).float().mean()),        # own centroid too far -> NEW DOMAIN
            "absorb_wrong": float((d_oth < NEW_DIST).float().mean())}      # a WRONG corpus is close enough to absorb


def adjacent_metrics(Zg, acat):
    """(f) boundary-detector SNR: distance between CONSECUTIVE grid windows (the run's own stride), split by whether
    a true splice falls between them, and if so whether it joins the same corpus or two different corpora."""
    d = (1.0 - (Zg[:-1] * Zg[1:]).sum(-1)).cpu()
    c = torch.tensor(acat[:d.numel()])
    ts, t1, t2 = d[c == 0], d[c == 1], d[c == 2]
    tb = d[c > 0]                                                 # ground-truth boundary set = every splice
    ms, ss = _ms(ts); mb, sb = _ms(tb)
    tp = float((tb > SHIFT_DIST).float().mean()) if tb.numel() else float("nan")
    fp = float((ts > SHIFT_DIST).float().mean()) if ts.numel() else float("nan")
    prec = (tp * tb.numel()) / max(1e-9, tp * tb.numel() + fp * ts.numel())
    return {"n_same": int(ts.numel()), "n_splice": int(tb.numel()), "n_splice_same_corpus": int(t1.numel()),
            "n_splice_diff_corpus": int(t2.numel()), "same_mean": ms, "same_sd": ss,
            "splice_mean": mb, "splice_sd": sb, "splice_same_corpus_mean": _ms(t1)[0],
            "splice_diff_corpus_mean": _ms(t2)[0], "auc": _auc(ts, tb), "dprime": _dprime(ts, tb),
            "trip_rate_splice": tp, "trip_rate_same": fp, "implied_precision_1win": prec}


# ---------------- signature backends -------------------------------------------------------------------------
def sigs_for(idx_pos, stream, enc, chunk=1024):
    """Signatures for a list of window START positions, through the SAME sig_of_batch the run uses."""
    out = []
    for a in range(0, len(idx_pos), chunk):
        wins = [list(stream[p:p + WIN]) for p in idx_pos[a:a + chunk]]
        out.append(S.sig_of_batch(wins, enc))
    return torch.cat(out) if out else torch.zeros(0, SIG_D, device=DEV)


def encode_all(U, enc):
    """(Zall over pure windows in `pos` order, Zg over EVERY grid window)."""
    Zg = sigs_for(U["gp"], U["stream"], enc)                        # ONE encode of EVERY grid window
    return Zg[torch.tensor(U["pidx"], device=Zg.device)], Zg


def centroids_of(Zall, cent_idx):
    """normalize(mean of K_CENT window signatures) -- exactly DomainAssembler.rekey."""
    return torch.stack([F.normalize(Zall[torch.tensor(cent_idx[c], device=Zall.device)].mean(0), dim=0)
                        for c in range(len(cent_idx))])


def balanced_eval(eval_idx):
    rng = random.Random(SEED + 2)
    per = min(min(len(v) for v in eval_idx.values()), MAXEVAL)
    ev = []
    for c in range(len(eval_idx)):
        v = list(eval_idx[c]); rng.shuffle(v); ev += v[:per]
    ev.sort(); return ev, per


def queries_R(Zall, U, ev, in_eval, R):
    """The assembler's actual _assign query: normalize(mean of the R-window run that tripped the boundary)."""
    pos, lab, seg = U["pos"], U["lab"], U["seg"]
    rows, rl = [], []
    for i in ev:
        run = [i + t for t in range(R)]
        if run[-1] >= len(pos): continue
        if any((j not in in_eval) or seg[j] != seg[i] or pos[j] != pos[i] + t * WIN
               for t, j in enumerate(run)): continue
        rows.append(F.normalize(Zall[torch.tensor(run, device=Zall.device)].mean(0), dim=0)); rl.append(lab[i])
    if not rows: return None, None
    return torch.stack(rows), torch.tensor(rl, device=Zall.device)


def evaluate(U, enc, cent_idx, eval_idx):
    stream, pos, lab, seg = U["stream"], U["pos"], U["lab"], U["seg"]
    nclass = len(cent_idx)
    Zall, Zg = encode_all(U, enc)
    C = centroids_of(Zall, cent_idx)
    ev, per = balanced_eval(eval_idx)
    evt = torch.tensor(ev, device=Zall.device)
    Ze = Zall[evt]
    ye = torch.tensor([lab[i] for i in ev], device=Zall.device)
    se = torch.tensor([seg[i] for i in ev], device=Zall.device)
    pe = torch.tensor([pos[i] for i in ev], device=Zall.device)
    res = {"per_class_eval": per, "pairs": pair_metrics(Ze, ye, se, pe), "centroid": {}}
    # --- (d) run-smoothed queries: mean of R CONSECUTIVE grid windows of the same segment (the _pend mean)
    in_eval = set().union(*[set(v) for v in eval_idx.values()])
    for R in RUNS:
        Q, qy = queries_R(Zall, U, ev, in_eval, R)
        if Q is None: continue
        res["centroid"][R] = centroid_metrics(Q, qy, C)
    res["adjacent"] = adjacent_metrics(Zg, U["acat"])
    return res


# ---------------- report -------------------------------------------------------------------------------------
def hdr_pairs():
    print(f"  {'N':>6} | {'within d (mu+-sd)':>19} | {'between d (mu+-sd)':>19} | {'gap':>6} | {'AUC':>5} | "
          f"{chr(100)+chr(39):>5} | {'%w>.35':>7} | {'%b<.35':>7} | {'w same/diff seg':>16}")


def row_pairs(N, m):
    print(f"  {N:>6} | {m['within_mean']:>8.3f} +- {m['within_sd']:<7.3f} | {m['between_mean']:>8.3f} +- "
          f"{m['between_sd']:<7.3f} | {m['gap']:>6.3f} | {m['auc']:>5.3f} | {m['dprime']:>5.2f} | "
          f"{100*m['within_gt_NEWDIST']:>6.1f}% | {100*m['between_lt_NEWDIST']:>6.1f}% | "
          f"{m['within_same_seg_mean']:>6.3f}/{m['within_diff_seg_mean']:<6.3f}")


def hdr_cent():
    print(f"  {'N':>6} {'R':>2} | {'d(own cent)':>13} | {'d(other)':>8} | {'margin':>7} | {'1-NN acc':>8} | "
          f"{'SPAWN%':>7} | {'absorb-wrong%':>13}")


def row_cent(N, R, c):
    print(f"  {N:>6} {R:>2} | {c['d_own']:>6.3f} +- {c['d_own_sd']:<4.3f} | {c['d_other']:>8.3f} | "
          f"{c['margin']:>7.3f} | {100*c['nn_acc']:>7.1f}% | {100*c['spawn_rate']:>6.1f}% | "
          f"{100*c['absorb_wrong']:>12.1f}%")


def drift_probe(U, cent_idx, eval_idx):
    """REKEY LAG. The frozen-encoder numbers above are the BEST case: they encode the centroid and the query with
    the SAME encoder. The live system does not. `asm.rekey` re-encodes the reservoir every REKEY_EVERY(=200) steps,
    while contrastive_step updates the encoder EVERY step (ENC_EVERY=1 near a boundary). So a query is matched
    against centroids that are up to REKEY_EVERY encoder updates STALE, in an embedding space that moved underneath
    them. This measures d(own centroid) as a function of that lag -- if it crosses NEW_DIST, every re-entry spawns a
    new domain no matter how discriminative the signature is at a fixed instant."""
    import copy
    pm = int(os.environ.get("PROBE_DRIFT_POSMAX", POSMAX[0]))
    base = int(os.environ.get("PROBE_DRIFT_BASE", 1000))
    lags = sorted(int(x) for x in os.environ.get("PROBE_DRIFT", "0,25,50,100,200,400,800").split(","))
    R = int(os.environ.get("PROBE_DRIFT_R", 2))
    os.environ["ENC_POS_MAX"] = str(pm * WIN)
    torch.manual_seed(SEED); random.seed(SEED + 7)
    enc = S.SigEncoder(S.D, SIG_D).to(DEV)
    opt = torch.optim.AdamW(enc.parameters(), lr=ENC_LR, weight_decay=0.0)
    for _ in range(base): S.contrastive_step(enc, opt, U["stream"], len(U["stream"]))
    enc.eval()
    Zall0, _ = encode_all(U, enc)
    C_old = centroids_of(Zall0, cent_idx)                            # what rekey STORED at t = base
    ev, _ = balanced_eval(eval_idx); in_eval = set().union(*[set(v) for v in eval_idx.values()])
    print(f"[REKEY LAG | ENC_POS_MAX {pm}*WIN | centroids frozen at step {base}, queries R={R} from the LIVE "
          f"encoder | REKEY_EVERY={S.REKEY_EVERY}, ENC_EVERY={S.ENC_EVERY}]")
    print(f"  {'lag':>5} | {'d_own STALE cent':>16} | {'SPAWN%':>7} | {'1-NN':>6} | {'d_own FRESH cent':>16} | "
          f"{'SPAWN%':>7} | {'1-NN':>6} | {'self-drift':>10}")
    out, done = {}, 0
    for lg in lags:
        while done < lg:
            enc.train(); S.contrastive_step(enc, opt, U["stream"], len(U["stream"])); done += 1
        enc.eval()
        Zall, _ = encode_all(U, enc)
        Q, qy = queries_R(Zall, U, ev, in_eval, R)
        st = centroid_metrics(Q, qy, C_old)                          # stale centroid (the live system)
        fr = centroid_metrics(Q, qy, centroids_of(Zall, cent_idx))   # re-keyed this instant (the ideal)
        sd = float((1 - (Zall * Zall0).sum(-1)).mean())              # how far the SAME windows moved in `lg` steps
        out[lg] = {"stale": st, "fresh": fr, "self_drift": sd}
        print(f"  {lg:>5} | {st['d_own']:>7.3f} +-{st['d_own_sd']:<6.3f} | {100*st['spawn_rate']:>6.1f}% | "
              f"{100*st['nn_acc']:>5.1f}% | {fr['d_own']:>7.3f} +-{fr['d_own_sd']:<6.3f} | "
              f"{100*fr['spawn_rate']:>6.1f}% | {100*fr['nn_acc']:>5.1f}% | {sd:>10.3f}")
    print()
    return out


def verdict(res):
    """ASSEMBLER or ENCODER? The learned signature is only 'fine' if it beats the untrained controls AND its own
    operating point (R=2, the SUSTAIN=2 smoothed query vs a 40-window centroid) can re-identify a corpus."""
    print("=" * 118)
    ctl = max((r["pairs"]["auc"] for r in res["controls"].values()), default=float("nan"))
    best = None
    for k, r in res["runs"].items():
        a = r["pairs"]["auc"]
        if best is None or a > best[1]: best = (k, a)
    print(f"VERDICT INPUTS: best UNTRAINED control AUC {ctl:.3f} | best LEARNED AUC {best[1]:.3f} ({best[0]})")
    print(f"  window-pair AUC 0.5 = signature carries NO corpus information; 1.0 = perfectly separable.")
    for k, r in res["runs"].items():
        c = r["centroid"].get(2) or r["centroid"].get(1)
        if not c: continue
        print(f"  {k:<18} R=2 query vs own 40-window centroid: d_own {c['d_own']:.3f} (NEW_DIST {NEW_DIST}) -> "
              f"SPAWN {100*c['spawn_rate']:.1f}% | 4-way 1-NN {100*c['nn_acc']:.1f}% | margin {c['margin']:+.3f}")
    print("  A high SPAWN% with a high 1-NN accuracy = the signature RANKS corpora correctly but the SCALE is wrong")
    print("     -> ASSEMBLER/threshold problem (raise NEW_DIST, or normalize distances per-domain).")
    print("  A ~chance 1-NN accuracy (25% at 4 corpora) = the signature genuinely cannot tell the corpora apart at")
    print("     window scale -> ENCODER problem (positive radius / objective), thresholds cannot fix it.")
    print("=" * 118)


def bnd_line(a, tag):
    return (f"  [boundary SNR{tag}] adjacent-window d: WITHIN segment {a['same_mean']:.3f}+-{a['same_sd']:.3f} "
            f"({100*a['trip_rate_same']:.1f}% > SHIFT_DIST={SHIFT_DIST}) | ACROSS splice {a['splice_mean']:.3f}"
            f"+-{a['splice_sd']:.3f} ({100*a['trip_rate_splice']:.1f}% trip) | AUC {a['auc']:.3f} d' "
            f"{a['dprime']:.2f} | splice same-corpus {a['splice_same_corpus_mean']:.3f} vs diff-corpus "
            f"{a['splice_diff_corpus_mean']:.3f} | implied 1-window precision {a['implied_precision_1win']:.2f} "
            f"(n {a['n_same']}/{a['n_splice']})")


def main():
    t0 = time.time()
    U = build_universe()
    stream, starts, pos, lab, seg = U["stream"], U["starts"], U["pos"], U["lab"], U["seg"]
    nclass = S.NP
    cent_idx, eval_idx = split_pools(pos, lab, seg, nclass)
    dn = os.environ.get("DOMAINS", "eng,py,num,c").split(",")
    print(f"=== SIGNATURE PROBE === corpora {dn} | stream {len(stream)} bytes | {len(starts)} splice segments | "
          f"WIN {WIN} SIG_D {SIG_D} | NEW_DIST {NEW_DIST} SHIFT_DIST {SHIFT_DIST} | dev {DEV}")
    print(f"  pure grid windows {len(pos)} " + " ".join(f"{dn[c]}:{sum(1 for x in lab if x == c)}" for c in range(nclass)))
    print(f"  centroid pool {K_CENT}/class from HELD-OUT SEGMENTS | eval pool "
          + " ".join(f"{dn[c]}:{len(eval_idx[c])}" for c in range(nclass)))
    print(f"  encoder: AdamW lr={ENC_LR} wd=0, ENC_BATCH {S.ENC_BATCH}, TEMP {S.TEMP}; "
          f"real run trains it ~ENC_WARMUP({os.environ.get('ENC_WARMUP', 800)}) + one step/window\n")
    results = {"config": {"stream_len": len(stream), "segments": len(starts), "win": WIN, "sig_d": SIG_D,
                          "new_dist": NEW_DIST, "shift_dist": SHIFT_DIST, "k_cent": K_CENT,
                          "steps": STEPS, "posmax_mult": POSMAX, "domains": dn}, "runs": {}, "controls": {}}

    if not SWEEP:
        results["drift"] = {str(k): v for k, v in drift_probe(U, cent_idx, eval_idx).items()}
        if OUT_JSON:
            with open(OUT_JSON, "w") as f: json.dump(results, f, indent=1)
            print(f"[saved] {OUT_JSON}")
        print(f"[probe done in {time.time()-t0:.0f}s]"); return

    # ---- (g) CONTROLS: untrained, non-learned signatures ----
    for mode in ("bigram", "frozen"):
        old = S.SIG_MODE; S.SIG_MODE = mode
        try:
            r = evaluate(U, None, cent_idx, eval_idx)
        finally:
            S.SIG_MODE = old
        results["controls"][mode] = r
        print(f"[CONTROL {mode:>6} -- untrained non-learned signature, dim {S.SIG_DIM if mode=='bigram' else S.D}"
              f" (NEW_DIST is calibrated for the LEARNED sig, so read AUC/d', not the % columns)]")
        hdr_pairs(); row_pairs("-", r["pairs"])
        hdr_cent()
        for R in sorted(r["centroid"]): row_cent("-", R, r["centroid"][R])
        print(bnd_line(r["adjacent"], "") + "\n")

    # ---- (c) learned encoder at each ENC_POS_MAX ----
    for pm in POSMAX:
        os.environ["ENC_POS_MAX"] = str(pm * WIN)
        torch.manual_seed(SEED); random.seed(SEED + 7)                 # identical init across configs -> N=0 comparable
        enc = S.SigEncoder(S.D, SIG_D).to(DEV)
        opt = torch.optim.AdamW(enc.parameters(), lr=ENC_LR, weight_decay=0.0)
        print(f"[LEARNED encoder | ENC_POS_MAX = {pm}*WIN = {pm*WIN} bytes  (segment mean 1250 bytes)]")
        hdr_pairs()
        rows_c, trained = [], 0
        for N in STEPS:
            while trained < N:
                S.contrastive_step(enc, opt, stream, len(stream)); trained += 1
            enc.eval()
            r = evaluate(U, enc, cent_idx, eval_idx)
            results["runs"][f"posmax{pm}_N{N}"] = r
            row_pairs(N, r["pairs"]); rows_c.append((N, r)); enc.train()
        print()
        hdr_cent()
        for N, r in rows_c:
            for R in sorted(r["centroid"]): row_cent(N, R, r["centroid"][R])
        for N, r in rows_c: print(bnd_line(r["adjacent"], f" @N={N}"))
        sc = rows_c[-1][1]["pairs"]["sep_curve"]
        print("  [SAME-corpus mean d vs BYTE SEPARATION of the two windows]  " +
              " ".join(f"{lo}-{'inf' if hi > (1<<29) else hi:>5}" for lo, hi, _, _ in sc) + "   | BETWEEN-corpus")
        for N, r in rows_c:
            print(f"      N={N:<6} " + " ".join(f"{mu:>10.3f}" for _, _, n, mu in r["pairs"]["sep_curve"]) +
                  f"   | {r['pairs']['between_mean']:.3f}")
        print("      n pairs   " + " ".join(f"{n:>10}" for _, _, n, _ in sc))
        print()

    if DRIFT_ON: results["drift"] = {str(k): v for k, v in drift_probe(U, cent_idx, eval_idx).items()}
    verdict(results)
    if OUT_JSON:
        with open(OUT_JSON, "w") as f: json.dump(results, f, indent=1)
        print(f"[saved] {OUT_JSON}")
    print(f"[probe done in {time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
