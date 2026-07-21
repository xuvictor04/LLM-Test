"""Analysis tooling -- UNDERSTAND the system, not just score it. Reads checkpoints + run logs only; never touches
the training path (safe to run against a live experiment's saved dirs).

  python3 control.py analyze <run_dir_or_ckpt> [sec1,sec2 ...]   # pass the arch knobs/preset you trained with
Sections (default all): growth (log-based), experts, compose (need the model), fuzzy (tokenizer-only).

  growth   -- does OOD actually drop after each grow/depth event, or is growth just adding parameters?
  experts  -- do experts SPECIALIZE by domain, or are they redundant? (tests the whole MoE premise)
  compose  -- do composed embeddings put byte/morphologically related tokens near each other?
  fuzzy    -- which typos the fuzzy tokenizer corrects in practice (real, not synthetic)
"""
import os, sys, json, glob, random
import torch
import torch.nn.functional as F
random.seed(0)


def _find_ckpt(arg):
    if arg.endswith(".pt"): return arg, os.path.dirname(arg) or "."
    for name in ("best.pt", "ckpt.pt"):
        p = os.path.join(arg, name)
        if os.path.exists(p): return p, arg
    return None, arg


# ---------------- growth payoff (log only, no model) ----------------
def sec_growth(run_dir):
    print("== growth payoff: does OOD drop after growth events? ==")
    logp = os.path.join(run_dir, "train_log.jsonl")
    if not os.path.exists(logp):
        print("  (no train_log.jsonl here)"); return
    recs = [json.loads(l) for l in open(logp)]
    if len(recs) < 3:
        print("  (too few evals)"); return
    prev_n = prev_l = None; events = []
    for r in recs:
        n = r.get("nodes"); l = r.get("layers"); ood = r.get("ood")
        if prev_n is not None and n is not None and n != prev_n: events.append((r["step"], f"experts {prev_n}->{n}", ood))
        if prev_l is not None and l is not None and l != prev_l: events.append((r["step"], f"layers {prev_l}->{l}", ood))
        prev_n, prev_l = n, l
    o0, o1 = recs[0].get("ood"), recs[-1].get("ood")
    print(f"  OOD {o0:.3f} -> {o1:.3f} over {recs[-1]['step']} steps ({len(recs)} evals) | {len(events)} growth events")
    # OOD change in the window straddling each growth event
    for step, what, _ in events[:8]:
        around = [r for r in recs if abs(r["step"] - step) <= max(1, recs[-1]["step"] // len(recs))]
        if len(around) >= 2:
            d = around[-1].get("ood", 0) - around[0].get("ood", 0)
            print(f"    @step {step:6d} {what:18s} | OOD {'dropped' if d < 0 else 'rose'} {d:+.3f} nearby")
    if not events: print("    (no growth events in the log -- fixed-size run)")


# ---------------- model loader for the model-based sections ----------------
def _load(ckpt):
    from config import cfg
    from system import load_system
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sysm, _ = load_system(ckpt, cfg, dev); sysm.eval()
    return sysm, cfg, dev


def _domain_batches(sysm, cfg, dev, per=8, ln=None):
    ln = ln or min(cfg.CTX, 128)
    dyn = getattr(sysm, "dyntok", None); out = {}
    for d in sorted(glob.glob("data/train/*")):
        if not os.path.isdir(d): continue
        files = glob.glob(d + "/*")
        if not files: continue
        txt = b"".join(open(f, "rb").read() for f in files[:2])[:200000]
        if len(txt) < ln * per: continue
        ids = (dyn.seg(list(txt), count=False) if dyn else list(txt))
        rows = [ids[i * ln:(i + 1) * ln] for i in range(min(per, len(ids) // ln))]
        if rows: out[os.path.basename(d)] = torch.tensor(rows, device=dev)
    return out


# ---------------- expert specialization ----------------
def sec_experts(ckpt):
    print("\n== expert specialization: do experts differentiate by domain? ==")
    try:
        from barry import SparseMoE
        sysm, cfg, dev = _load(ckpt)
    except Exception as e:
        print(f"  (needs the model + matching arch env: {str(e)[:80]})"); return
    moes = [m for m in sysm.modules() if isinstance(m, SparseMoE)]
    if not moes:
        print("  (no sparse-MoE layers -- FABRIC != sparse?)"); return
    batches = _domain_batches(sysm, cfg, dev)
    if len(batches) < 2:
        print("  (need >=2 domains of data)"); return
    # hook each router: record top-1 expert per token
    counts = {}                                            # domain -> tensor[num_experts] pick-counts (summed over layers)
    cur = {"d": None}
    handles = []
    def hook(mod, inp, out):
        if cur["d"] is None: return
        pick = out.detach().argmax(-1).flatten()           # top-1 expert per token
        c = counts.setdefault(cur["d"], torch.zeros(out.size(-1) + 8))
        if c.numel() < out.size(-1): c = torch.cat([c, torch.zeros(out.size(-1) - c.numel() + 8)]); counts[cur["d"]] = c
        for e in pick.tolist(): counts[cur["d"]][e] += 1
    for m in moes: handles.append(m.router.register_forward_hook(hook))
    with torch.no_grad():
        for dname, xb in batches.items():
            cur["d"] = dname
            pn = sysm.surprise.score_pos(xb).to(dev); sysm(xb, pn)
    for h in handles: h.remove()
    cur["d"] = None
    doms = list(batches.keys())
    N = max(int(counts[d].nonzero().max()) + 1 for d in doms if counts[d].sum() > 0)
    mat = torch.stack([counts[d][:N] / counts[d][:N].sum().clamp(min=1) for d in doms])   # domain x expert (normalized)
    # specialization = for each expert, how concentrated its usage is in one domain (max share). 1/len(doms)=uniform.
    share = mat / mat.sum(0, keepdim=True).clamp(min=1e-9)                                 # of picks for expert e, fraction from each domain
    peak = share.max(0).values                                                            # per-expert dominant-domain share
    print(f"  {len(doms)} domains {doms} x {N} experts (top-1 routing)")
    print(f"  mean dominant-domain share per expert: {peak.mean():.2f}  (1/{len(doms)}={1/len(doms):.2f}=redundant, 1.0=fully specialized)")
    # show the most specialized experts
    order = peak.argsort(descending=True)
    for e in order[:min(6, N)].tolist():
        top = int(share[:, e].argmax())
        print(f"    expert {e:3d}: {peak[e]:.2f} -> mostly '{doms[top]}'")


# ---------------- composition neighborhood ----------------
def sec_compose(ckpt):
    print("\n== composition structure: are embedding-neighbors byte-related? ==")
    try:
        sysm, cfg, dev = _load(ckpt)
    except Exception as e:
        print(f"  (needs the model: {str(e)[:80]})"); return
    dyn = getattr(sysm, "dyntok", None); V = sysm.V
    E = F.normalize(sysm.init_emb.weight[:V], dim=1)
    composed = [v for v in range(256, V)]
    if not composed:
        print("  (no minted tokens yet)"); return
    random.shuffle(composed); overlap = 0; shown = 0
    for v in composed[:200]:
        sim = E[v] @ E.t(); sim[v] = -2
        nn = int(sim.argmax())
        if dyn:
            bv, bn = dyn.id2bytes[v], dyn.id2bytes[nn]
            share = len(set(bv) & set(bn)) / max(1, len(set(bv) | set(bn)))               # byte-set Jaccard
            overlap += share
            if shown < 6:
                print(f"    {bv!r:>16} ~ {bn!r:<16} (byte overlap {share:.2f})"); shown += 1
    print(f"  mean byte-overlap of a token with its nearest embedding-neighbor: {overlap/min(200,len(composed)):.2f}")
    print("  (higher = embedding space groups byte/morphologically related tokens = composition is structuring it)")


# ---------------- fuzzy correction audit ----------------
def sec_fuzzy(ckpt):
    print("\n== fuzzy correction in practice ==")
    from collections import Counter
    try:
        sysm, cfg, dev = _load(ckpt); dyn = sysm.dyntok
    except Exception:
        dyn = None
    if dyn is None:
        print("  (no dynamic tokenizer in checkpoint)"); return
    dyn.build_fuzzy_index()
    txt = b"".join(open(f, "rb").read() for f in glob.glob("data/train/eng/*")[:1])[:300000]
    words = [w for w, _ in Counter(w for w in txt.split() if len(w) >= 5 and w.isalpha()).most_common(80)]
    def typo(w):
        i = random.randrange(len(w) - 1); b = bytearray(w); b[i], b[i + 1] = b[i + 1], b[i]; return bytes(b)
    rec = tot = 0
    for w in words:
        clean = dyn.segment(list(w), count=False); tw = typo(w)
        if tw == w: continue
        tot += 1
        if dyn.fuzzy_segment(list(tw)) == clean: rec += 1
    if tot: print(f"  typos recovered to the clean tokenization by the trained fuzzy index: {rec}/{tot} ({100*rec/tot:.0f}%)")


SECS = {"growth": None, "experts": sec_experts, "compose": sec_compose, "fuzzy": sec_fuzzy}
if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("usage: python3 control.py analyze <run_dir_or_ckpt> [growth,experts,compose,fuzzy]"); sys.exit(0)
    target = args[0]
    which = (args[1].split(",") if len(args) > 1 else list(SECS.keys()))
    ckpt, run_dir = _find_ckpt(target)
    print(f"analyzing {target}  (ckpt: {ckpt})\n")
    if "growth" in which: sec_growth(run_dir)
    if ckpt:
        if "experts" in which: sec_experts(ckpt)
        if "compose" in which: sec_compose(ckpt)
        if "fuzzy" in which: sec_fuzzy(ckpt)
    elif set(which) - {"growth"}:
        print("\n(model sections skipped -- no checkpoint found at that path)")
