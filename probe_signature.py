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
OUT_JSON  = os.environ.get("PROBE_JSON", "")


# ---------------- stream + labelled window universe ----------------------------------------------------------
def build_universe():
    """Grid windows (stride WIN, exactly what the main loop steps over) whose TRUE corpus label is unambiguous."""
    random.seed(SEED); torch.manual_seed(SEED)
    stream, labels, sw = S.build_stream()
    S.set_enc_tensor(stream)
    starts = sorted(int(x) for x in sw)                          # splice-segment starts
    segof = []                                                   # segment index per byte position (grid only)
    import bisect
    pos, lab, seg = [], [], []
    for p in range(0, len(stream) - WIN, WIN):
        a = labels[p]
        if labels[p + WIN - 1] != a:                             # window straddles a splice -> impure, drop
            continue
        si = bisect.bisect_right(starts, p) - 1
        if bisect.bisect_right(starts, p + WIN - 1) - 1 != si:    # same-label but different segment: still impure
            continue
        pos.append(p); lab.append(a); seg.append(si)
    return stream, labels, starts, pos, lab, seg


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


def adjacent_metrics(Zall, pos, lab, seg):
    """(f) boundary-detector SNR proxy: distance between consecutive grid windows, same segment vs across a splice."""
    same, cross = [], []
    for i in range(len(pos) - 1):
        j = i + 1
        if pos[j] != pos[i] + WIN: continue                       # an impure window was dropped between them
        d = float(1.0 - torch.dot(Zall[i], Zall[j]))
        (same if seg[i] == seg[j] else cross).append(d)
    ts, tc = torch.tensor(same), torch.tensor(cross)
    ms, ss = _ms(ts); mc, sc = _ms(tc)
    tp = float((tc > SHIFT_DIST).float().mean()) if tc.numel() else float("nan")
    fp = float((ts > SHIFT_DIST).float().mean()) if ts.numel() else float("nan")
    prec = (tp * tc.numel()) / max(1e-9, tp * tc.numel() + fp * ts.numel())
    return {"n_same": int(ts.numel()), "n_cross": int(tc.numel()), "same_mean": ms, "same_sd": ss,
            "cross_mean": mc, "cross_sd": sc, "auc": _auc(ts, tc), "dprime": _dprime(ts, tc),
            "trip_rate_cross": tp, "trip_rate_same": fp, "implied_precision_1win": prec}


# ---------------- signature backends -------------------------------------------------------------------------
def sigs_for(idx_pos, stream, enc, chunk=1024):
    """Signatures for a list of window START positions, through the SAME sig_of_batch the run uses."""
    out = []
    for a in range(0, len(idx_pos), chunk):
        wins = [list(stream[p:p + WIN]) for p in idx_pos[a:a + chunk]]
        out.append(S.sig_of_batch(wins, enc))
    return torch.cat(out) if out else torch.zeros(0, SIG_D, device=DEV)


def evaluate(stream, enc, pos, lab, seg, cent_idx, eval_idx):
    nclass = len(cent_idx)
    Zall = sigs_for(pos, stream, enc)                               # ONE encode of every pure grid window
    # --- centroids: normalize(mean of K_CENT window signatures) -- exactly DomainAssembler.rekey
    C = torch.stack([F.normalize(Zall[torch.tensor(cent_idx[c], device=Zall.device)].mean(0), dim=0)
                     for c in range(nclass)])
    # --- balanced eval set (held-out SEGMENTS)
    rng = random.Random(SEED + 2)
    per = min(min(len(v) for v in eval_idx.values()), MAXEVAL)
    ev = []
    for c in range(nclass):
        v = list(eval_idx[c]); rng.shuffle(v); ev += v[:per]
    ev.sort()
    evt = torch.tensor(ev, device=Zall.device)
    Ze = Zall[evt]
    ye = torch.tensor([lab[i] for i in ev], device=Zall.device)
    se = torch.tensor([seg[i] for i in ev], device=Zall.device)
    pe = torch.tensor([pos[i] for i in ev], device=Zall.device)
    res = {"per_class_eval": per, "pairs": pair_metrics(Ze, ye, se, pe), "centroid": {}}
    # --- (d) run-smoothed queries: mean of R CONSECUTIVE grid windows of the same segment (the _pend mean)
    in_eval = set().union(*[set(v) for v in eval_idx.values()])
    for R in RUNS:
        rows, rl = [], []
        for i in ev:
            run = [i + t for t in range(R)]
            if run[-1] >= len(pos): continue
            if any((j not in in_eval) or seg[j] != seg[i] or pos[j] != pos[i] + t * WIN
                   for t, j in enumerate(run)): continue
            rows.append(F.normalize(Zall[torch.tensor(run, device=Zall.device)].mean(0), dim=0)); rl.append(lab[i])
        if not rows: continue
        res["centroid"][R] = centroid_metrics(torch.stack(rows), torch.tensor(rl, device=Zall.device), C)
    res["adjacent"] = adjacent_metrics(Zall, pos, lab, seg)
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


def main():
    t0 = time.time()
    stream, labels, starts, pos, lab, seg = build_universe()
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

    # ---- (g) CONTROLS: untrained, non-learned signatures ----
    for mode in ("bigram", "frozen"):
        old = S.SIG_MODE; S.SIG_MODE = mode
        try:
            r = evaluate(stream, None, pos, lab, seg, cent_idx, eval_idx)
        finally:
            S.SIG_MODE = old
        results["controls"][mode] = r
        m = r["pairs"]
        print(f"[CONTROL {mode:>6} (untrained, dim {S.SIG_DIM if mode=='bigram' else S.D})]")
        hdr_pairs(); row_pairs("-", m)
        hdr_cent()
        for R in sorted(r["centroid"]): row_cent("-", R, r["centroid"][R])
        a = r["adjacent"]
        print(f"  adjacent windows: same-seg {a['same_mean']:.3f}+-{a['same_sd']:.3f} | across-splice "
              f"{a['cross_mean']:.3f}+-{a['cross_sd']:.3f} | AUC {a['auc']:.3f}\n")

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
            r = evaluate(stream, enc, pos, lab, seg, cent_idx, eval_idx)
            results["runs"][f"posmax{pm}_N{N}"] = r
            row_pairs(N, r["pairs"]); rows_c.append((N, r))
        print()
        hdr_cent()
        for N, r in rows_c:
            for R in sorted(r["centroid"]): row_cent(N, R, r["centroid"][R])
        a = rows_c[-1][1]["adjacent"]
        print(f"  [boundary SNR @N={rows_c[-1][0]}] adjacent same-seg {a['same_mean']:.3f}+-{a['same_sd']:.3f} "
              f"({100*a['trip_rate_same']:.1f}% > SHIFT_DIST) | across-splice {a['cross_mean']:.3f}+-{a['cross_sd']:.3f} "
              f"({100*a['trip_rate_cross']:.1f}% trip) | AUC {a['auc']:.3f} | implied 1-window precision "
              f"{a['implied_precision_1win']:.2f}")
        print(f"  [same-corpus distance vs BYTE SEPARATION @N={rows_c[-1][0]}]  (between-corpus = "
              f"{rows_c[-1][1]['pairs']['between_mean']:.3f})")
        for lo, hi, n, mu in rows_c[-1][1]["pairs"]["sep_curve"]:
            if n: print(f"      {lo:>6}-{'inf' if hi > (1<<29) else hi:>6} bytes  n={n:>7}  mean d = {mu:.3f}")
        print()

    if OUT_JSON:
        with open(OUT_JSON, "w") as f: json.dump(results, f, indent=1)
        print(f"[saved] {OUT_JSON}")
    print(f"[probe done in {time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
