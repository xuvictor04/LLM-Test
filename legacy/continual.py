"""continual.py -- run GREG (system.py) as a CONTINUAL learner with backward-transfer (BWT) logging.

This is the faithful continual extension of train.py: it reuses Greg's *exact* training step
(forward -> ce + ponder + re-encode cost -> adaptive-gated memory write -> self-scaling
breadth/depth growth + pruning), but instead of one stationary pass it:

  1. joint-pretrains on everything under data/train/<domain>/      (the "earliest" knowledge)
  2. streams in each phase under data/continual/<NN_name>/ in order (domains ARRIVE over time)
  3. at every phase: measures bits/byte on ALL previously-seen domains BEFORE and AFTER adapting,
     so we can log drift-vs-first-seen == backward transfer (negative = the old domain IMPROVED,
     positive = it was FORGOTTEN).

It is built as an ABLATION so the make-or-break question is answerable:
    MEMORY=off    + REPLAY=0   -> the forgetting baseline (no recall, no rehearsal)
    MEMORY=mirror + REPLAY=0   -> does Greg's memory ALONE reduce forgetting?   <-- the real test
    MEMORY=mirror + REPLAY=1   -> rehearsal bracket (replay is known to help; it's partial "cheating")

Toggles (env):
    MEMORY=off|ring|mirror   NOVELTY=reverse|trigram   DEPTH_GROWTH=0|1   MAX_LAYERS   DEPTH_THROTTLE
    REPLAY=0|1   REPLAY_CAP=4000   CONSOLIDATE=0|1
    PRETRAIN_STEPS=3000   ADAPT_STEPS=1500
    + every config.py knob (D_MODEL, CTX, BATCH, LR, NMAX, TARGET, MEMCAP, DATA_DIR, RUN_DIR, ...)

Output: <RUN_DIR>/continual_log.jsonl  (one record per phase + a final summary with the BWT table).
"""
import os, json, time, random
import torch
from config import cfg
from data_utils import _read_folder, _chunk, load_corpus, _make_encoder, dyn_batch, dyn_window
from system import (build_system, warmup_base, seed_node, evaluate_system, ce, ReverseSurprise, save_system)
from growth import GrowthController
from adaptive_gate import AdaptiveGate

# ---- continual-specific knobs ----
PRETRAIN_STEPS = int(os.environ.get("PRETRAIN_STEPS", 3000))
ADAPT_STEPS    = int(os.environ.get("ADAPT_STEPS", 1500))
REPLAY         = os.environ.get("REPLAY", "1") == "1"
REPLAY_CAP     = int(os.environ.get("REPLAY_CAP", 4000))
SURPRISE_REPLAY = os.environ.get("SURPRISE_REPLAY", "1") == "1"  # buffer only SURPRISING examples for replay
CONSOLIDATE    = os.environ.get("CONSOLIDATE", "1") == "1"
DEPTH_GROWTH   = os.environ.get("DEPTH_GROWTH", "0") == "1"
MAX_LAYERS     = int(os.environ.get("MAX_LAYERS", cfg.N_LAYERS))
DEPTH_THROTTLE = int(os.environ.get("DEPTH_THROTTLE", 200))


def load_phases(root, L, enc):
    """Each subfolder of data/continual/ is one phase (one arriving domain). 80/20 adapt/held split."""
    phases = []
    if not os.path.isdir(root): return phases
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if not os.path.isdir(folder): continue
        cs = _chunk(_read_folder(folder, name, cfg.DATA_CAP), L, enc)
        if len(cs) < 4: continue
        k = int(len(cs) * 0.8)
        phases.append((name, cs[:k], cs[k:k + cfg.HELD]))
    return phases


class Reservoir:
    """Bounded reservoir-sampling replay buffer of past byte-chunks (only used when REPLAY=1)."""
    def __init__(self, cap): self.cap = cap; self.b = []; self.seen = 0
    def add(self, w):
        self.seen += 1
        if len(self.b) < self.cap: self.b.append(w)
        else:
            j = random.randint(0, self.seen - 1)
            if j < self.cap: self.b[j] = w
    def sample(self, n): return random.sample(self.b, min(n, len(self.b))) if self.b else []


def main():
    torch.manual_seed(cfg.SEED); random.seed(cfg.SEED)
    dev = torch.device(cfg.DEVICE)
    os.makedirs(cfg.RUN_DIR, exist_ok=True)
    log_path = os.path.join(cfg.RUN_DIR, "continual_log.jsonl")
    logf = open(log_path, "w")
    def log(rec): logf.write(json.dumps(rec) + "\n"); logf.flush(); print(rec)

    TRAIN, HELD0, OOD = load_corpus(cfg)                       # pretrain domains == earliest knowledge
    phases = load_phases(os.path.join(cfg.DATA_DIR, "continual"), dyn_window(cfg), _make_encoder(cfg))
    mode = f"MEMORY={os.environ.get('MEMORY','ring')} SURPRISE={os.environ.get('SURPRISE') or os.environ.get('NOVELTY') or 'reverse'} REPLAY={int(REPLAY)}{'(surprise-gated)' if REPLAY and SURPRISE_REPLAY else ''} CONSOLIDATE={int(CONSOLIDATE)}"
    print(f"device={dev}  d{cfg.D_MODEL}/L{cfg.N_LAYERS}  ctx={cfg.CTX}  batch={cfg.BATCH}  | {mode}")
    print(f"pretrain domains {list(HELD0)} | continual phases {[p[0] for p in phases]}")
    assert phases, "no phases under data/continual/<NN_name>/ -- populate it (see CONTINUAL.md / the data plan)"

    # ---- build Greg + base warmup + initial nodes (fresh path from train.py) ----
    sysm = build_system(cfg, dev)
    print("warming up base (language pretrain)...")
    warmup_base(sysm.base, TRAIN, cfg, dev)
    for _ in range(cfg.N0): sysm.add_node()
    if (os.environ.get("SURPRISE") or os.environ.get("NOVELTY") or "reverse") == "reverse" and not isinstance(sysm.surprise, ReverseSurprise):
        sysm.surprise = ReverseSurprise(sysm.base, dev); print("[surprise] REVERSE-PREDICTOR active")
    if DEPTH_GROWTH: print(f"[depth] two-tier growth ON | seed {len(sysm.base.blocks)} -> max {MAX_LAYERS} layers")

    opt = torch.optim.AdamW(sysm.parameters(), lr=cfg.LR, weight_decay=cfg.WEIGHT_DECAY)
    state = {"g": 0, "ema": None, "last_spawn": -10**9, "last_depth": -10**9, "opt": opt}
    buf = Reservoir(REPLAY_CAP)
    REENC_BASE = cfg.ENABLE_REENCODE                     # warmup gate can hold re-encode off early
    import contextlib
    _dt = "cuda" if "cuda" in str(dev) else "cpu"
    AMPCTX = (lambda: torch.autocast(_dt, dtype=torch.bfloat16)) if getattr(cfg, "AMP", False) else (lambda: contextlib.nullcontext())
    if getattr(cfg, "AMP", False): print(f"[amp] bf16 autocast ON ({_dt})")
    rgate = AdaptiveGate(theta=3.0)                      # self-calibrating: buffers examples above recent surprise
    gc = GrowthController(len(sysm.bodies), nmax=cfg.NMAX, minn=cfg.MINN,
                          max_layers=(MAX_LAYERS if DEPTH_GROWTH else None), n_layers=len(sysm.base.blocks),
                          grace=cfg.GRACE, patience=cfg.PATIENCE, rel_improve=cfg.REL_IMPROVE,
                          prune_frac=cfg.PRUNE_FRAC, cooldown=cfg.COOLDOWN,
                          prune=cfg.PRUNE, require_balance=cfg.REQUIRE_BALANCE)

    def batch_from(chunks, n):
        if not chunks: return None
        if sysm.dyntok is not None:                         # dynamic: segment byte windows -> CTX token rows
            return dyn_batch(chunks, sysm.dyntok, n, cfg.CTX)
        return torch.stack(random.sample(chunks, min(n, len(chunks))))

    def buffer_rows(rows, surp):
        """Add rows to the replay buffer. When SURPRISE_REPLAY, only buffer the surprising ones
        (per-example surprise above the self-calibrating gate) -- replay is fed BY surprise."""
        if not (SURPRISE_REPLAY and surp is not None):
            for w in rows: buf.add(w)
            return
        for j, w in enumerate(rows):
            if rgate.step(float(surp[j])): buf.add(w)

    def greg_step(x_cpu):
        """ONE training step -- identical to train.py's inner loop (growth/depth/prune included)."""
        opt = state["opt"]
        cfg.ENABLE_REENCODE = REENC_BASE and state["g"] >= cfg.REENCODE_WARMUP
        posnov = sysm.surprise.score_pos(x_cpu).to(dev); x = x_cpu.to(dev)
        with AMPCTX():
            lg, aux = sysm(x, posnov)
            loss = ce(lg, x) + cfg.PONDER * aux["depth"] + cfg.REENC_COST * aux["enc"] + cfg.COUNTERPART_COST * aux["cpl"] + float(getattr(cfg, "LB_COST", 0.0)) * aux.get("lb", 0.0)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(sysm.parameters(), cfg.GRAD_CLIP); opt.step()
        sysm.promote_senses(x, posnov)                      # sparse sense: spawn folders for surprising tokens (no-op if dense/off)
        sysm.surprise.update(x_cpu)
        if sysm.dyntok is not None:                            # EMERGENT vocab: mint hot pairs (multi per step)
            for _ in range(cfg.MINT_PER_STEP):
                mg = sysm.dyntok.maybe_grow()
                if not mg: break
                sysm.grow_vocab(mg[1], mg[2])
        if hasattr(sysm.mem, "gate"):                          # MirroredMemory: adaptive-gated write
            gate_nov = getattr(sysm.surprise, "last_ce", None)
            if gate_nov is None: gate_nov = posnov.mean(1).detach().cpu()
            via = int(aux["mass"][:len(sysm.bodies)].argmax())
            sysm.mem.write(aux["gist"].detach(), aux["hf"].mean(1).detach(), gate_nov, via)
        else:
            sysm.mem.write(aux["gist"].detach(), aux["hf"].mean(1).detach())

        fl = float(ce(lg, x).detach())
        state["ema"] = fl if state["ema"] is None else 0.99 * state["ema"] + 0.01 * fl
        for i in range(len(sysm.bodies)): sysm.usage[i] = 0.99 * sysm.usage[i] + 0.01 * float(aux["mass"][i])
        g = state["g"]
        # ---- self-regulating population (growth.py): plateau-spawn / grace-protected relative-prune ----
        if g > cfg.WARMUP_STEPS:
            act = gc.decide(g, fl, sysm.usage)
            if act is not None:
                kind = act[0]
                if kind == "spawn":
                    sysm.add_node(); seed_node(sysm, x[:1], posnov[:1], cfg); gc.on_spawn()
                    print(f"  [grow] -> {len(sysm.bodies)} nodes @ {g}")
                elif kind == "prune":
                    sysm.prune_node(act[1]); gc.on_prune(act[1])
                    print(f"  [prune] -> {len(sysm.bodies)} nodes @ {g}")
                elif kind == "depth":
                    nl = sysm.base.grow_depth(); gc.on_depth()
                    print(f"  [grow-depth] -> {nl} layers @ {g}")
                state["opt"] = torch.optim.AdamW(sysm.parameters(), lr=cfg.LR, weight_decay=cfg.WEIGHT_DECAY)
        state["g"] += 1
        return fl

    def per_domain_bb(held_dict):
        return evaluate_system(sysm, held_dict, {}, cfg)["held_by_domain"]

    # ---- 1) joint pretrain on data/train ----
    sysm.train(); t0 = time.time()
    for i in range(PRETRAIN_STEPS):
        bw = batch_from(TRAIN, cfg.BATCH)
        if bw is None: continue
        greg_step(bw)
        if REPLAY:                                          # surprise-gated buffering (last_ce now set)
            buffer_rows(bw, getattr(sysm.surprise, "last_ce", None))
        if i % max(1, PRETRAIN_STEPS // 10) == 0:
            print(f"  [pretrain {i}/{PRETRAIN_STEPS}] ema {state['ema']:.3f} nodes {len(sysm.bodies)} layers {len(sysm.base.blocks)} {(i+1)/max(1e-9,time.time()-t0):.1f} it/s")

    HELD_all = dict(HELD0)
    baseline = per_domain_bb(HELD_all)                          # first-seen bits/byte for pretrain domains
    log({"phase": "pretrain_done", "mode": mode, "nodes": len(sysm.bodies),
         "layers": len(sysm.base.blocks), "baseline_bb": baseline})

    # ---- 2) stream phases, measuring BWT around each ----
    for name, adapt_cs, held_cs in phases:
        HELD_all[name] = held_cs
        before = per_domain_bb(HELD_all)
        baseline[name] = before[name]                           # first time this domain is seen
        new_before = before[name]

        for _ in range(ADAPT_STEPS):
            new = None
            if REPLAY:
                new = batch_from(adapt_cs, cfg.BATCH // 2)       # token rows (dynamic) or chunk rows
                if new is None: continue
                extra = buf.sample(cfg.BATCH - new.size(0))
                bw = torch.stack([r for r in new] + extra) if extra else new
            else:
                bw = batch_from(adapt_cs, cfg.BATCH)             # pure new-domain only (the hard test)
                if bw is None: continue
            greg_step(bw)
            if REPLAY and new is not None:                       # buffer only surprising NEW rows
                se = getattr(sysm.surprise, "last_ce", None)
                buffer_rows(new, se[:new.size(0)] if se is not None else None)

        if CONSOLIDATE and hasattr(sysm.mem, "consolidate"):    # phase-boundary "sleep"/review pass
            try: sysm.mem.consolidate()
            except Exception as e: print(f"  [consolidate] skipped: {e}")

        after = per_domain_bb(HELD_all)
        drift = {dm: round(after[dm] - baseline[dm], 3) for dm in HELD_all}   # negative = improved (BWT)
        log({"phase": "shift", "domain": name, "new_before": new_before, "new_after": after[name],
             "drift_vs_first_seen": drift, "nodes": len(sysm.bodies), "layers": len(sysm.base.blocks),
             "mem_filled": getattr(sysm.mem, "n", 0), "replay_buffer": len(buf.b)})

    # ---- 3) final summary: forgetting / backward transfer over the OLD domains ----
    final = per_domain_bb(HELD_all)
    old = [d for d in baseline if d != phases[-1][0]]           # everything except the last-added domain
    drift_final = {d: round(final[d] - baseline[d], 3) for d in baseline}
    mean_bwt = round(sum(final[d] - baseline[d] for d in old) / max(1, len(old)), 3)
    log({"phase": "done", "mode": mode, "final_bb": final, "baseline_bb": baseline,
         "drift_final": drift_final, "mean_backward_transfer_old_domains": mean_bwt,
         "nodes": len(sysm.bodies), "layers": len(sysm.base.blocks)})
    print(f"\n=== mean drift on OLD domains (negative = improved, positive = forgot): {mean_bwt} ===")
    print("per-domain final drift vs first-seen:", drift_final)

    ckpt = os.path.join(cfg.RUN_DIR, "ckpt.pt")
    save_system(sysm, ckpt, total=state["g"], ema=state["ema"], last_spawn=state["last_spawn"])
    print(f"checkpoint: {ckpt}\nlog: {log_path}")
    logf.close()


if __name__ == "__main__":
    main()
