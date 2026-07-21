"""Train the overarching system.  Usage:
    python get_data.py            # once, to download/build the corpus
    python train.py               # train (auto-resumes from runs/ckpt.pt if present)
Outputs land in runs/:  ckpt.pt (weights+state, resumable) and train_log.jsonl (one JSON record per eval).
Override any config knob via env vars, e.g.:  STEPS=50000 DEVICE=cuda BATCH=48 python train.py
"""
import os, json, time, random, torch
from optimizers import make_opt
from config import cfg
from data_utils import load_corpus, sample_batch, dyn_batch
from system import (build_system, load_system, save_system, warmup_base, seed_node,
                    evaluate_system, embed_mix, sense_mix, ce, ReverseSurprise)
from adaptive_gate import AdaptiveGate

def main():
    torch.manual_seed(cfg.SEED); random.seed(cfg.SEED)
    dev = torch.device(cfg.DEVICE)
    os.makedirs(cfg.RUN_DIR, exist_ok=True)
    ckpt_path = os.path.join(cfg.RUN_DIR, "ckpt.pt"); log_path = os.path.join(cfg.RUN_DIR, "train_log.jsonl")

    print(f"device={dev}  model d{cfg.D_MODEL}/L{cfg.N_LAYERS}  ctx={cfg.CTX}  batch={cfg.BATCH}  steps={cfg.STEPS}")
    TRAIN, HELD, OOD = load_corpus(cfg)
    print(f"corpus: {len(TRAIN)} train chunks | held domains {list(HELD)} | OOD sets {list(OOD)}")
    if getattr(cfg, "TOKENIZER", "") == "dynamic" and len(TRAIN) < 20000:
        print(f"  !! WARNING: only {len(TRAIN)} train chunks -- that's a SMALL corpus (a few MB). enwik8 is likely")
        print(f"  !! missing; expect tens of thousands with it. The model WILL overfit. Check data/train/eng/enwik8.txt (~96MB).")

    if os.path.exists(ckpt_path):
        sysm, ck = load_system(ckpt_path, cfg, dev)
        total, ema, last_spawn = ck["total"], ck["ema"], ck["last_spawn"]
        opt = make_opt(sysm.parameters(), cfg)
        if "opt" in ck:
            try: opt.load_state_dict(ck["opt"])
            except Exception: pass
        print(f"RESUMED at step {total} | nodes {len(sysm.bodies)} | mem {sysm.mem.n}/{cfg.MEMCAP}")
    else:
        sysm = build_system(cfg, dev)
        print("warming up base (language pretrain)...")
        warmup_base(sysm.base, TRAIN, cfg, dev)
        for _ in range(cfg.N0): sysm.add_node()
        opt = make_opt(sysm.parameters(), cfg)
        total, ema, last_spawn = 0, None, -10**9
        print(f"FRESH | nodes {len(sysm.bodies)}")

    if os.environ.get("PROBE_PEAK") == "1":            # MEMORY probe: force the TRUE end-state footprint before the loop
        while len(sysm.bodies) < cfg.NMAX:             # grow experts to the cap (memory grows with expert count)
            try: sysm.add_node()
            except Exception: break
        sysm.V = sysm.VMAX; sysm.base.V = sysm.base.VMAX   # logit activations are (B,L,V); force FULL width -- the dominant late-training term
        if getattr(sysm, "_comp_cache", None) is not None: sysm._comp_dirty = True
        opt = make_opt(sysm.parameters(), cfg)         # re-include the grown experts so backward is representative
        print(f"[probe-peak] forced worst-case footprint: V={sysm.V} experts={len(sysm.bodies)} layers={len(sysm.base.blocks)}")

    if (os.environ.get("SURPRISE") or os.environ.get("NOVELTY") or "reverse") == "reverse" and not isinstance(sysm.surprise, ReverseSurprise):
        sysm.surprise = ReverseSurprise(sysm.base, dev)
        print("[surprise] REVERSE-PREDICTOR active")

    from growth import GrowthController
    DEPTH_GROWTH = os.environ.get("DEPTH_GROWTH", "0") == "1"
    MAX_LAYERS = int(os.environ.get("MAX_LAYERS", len(sysm.base.blocks)))
    gc = GrowthController(len(sysm.bodies), nmax=cfg.NMAX, minn=cfg.MINN,
                          max_layers=(MAX_LAYERS if DEPTH_GROWTH else None), n_layers=len(sysm.base.blocks),
                          grace=cfg.GRACE, patience=cfg.PATIENCE, rel_improve=cfg.REL_IMPROVE,
                          prune_frac=cfg.PRUNE_FRAC, cooldown=cfg.COOLDOWN,
                          prune=cfg.PRUNE, require_balance=cfg.REQUIRE_BALANCE)
    print(f"[growth] population | nodes {len(sysm.bodies)} (<= {cfg.NMAX}) | grace {cfg.GRACE} patience {cfg.PATIENCE} | "
          f"prune {'ON' if cfg.PRUNE else 'OFF (grow-only)'} | balance-gate {'on' if cfg.REQUIRE_BALANCE else 'off'} | "
          f"depth {'on -> ' + str(MAX_LAYERS) + ' layers' if DEPTH_GROWTH else 'off'}")

    REENC_BASE = cfg.ENABLE_REENCODE                    # warmup gate below can hold it off early
    # ---- replay (surprise-gated) -- first-class in the main trainer; same design as continual.py ----
    import random as _rnd
    REPLAY = os.environ.get("REPLAY", "0") == "1"       # off by default (IID pretrain unchanged); on for streams
    SURPRISE_REPLAY = os.environ.get("SURPRISE_REPLAY", "1") == "1"
    REPLAY_CAP = int(os.environ.get("REPLAY_CAP", 8192))
    _rep = {"buf": [], "seen": 0, "gate": AdaptiveGate(theta=3.0)}
    def _buf_add(row):
        _rep["seen"] += 1; b = _rep["buf"]
        if len(b) < REPLAY_CAP: b.append(row.detach().cpu().clone())
        else:
            j = _rnd.randint(0, _rep["seen"] - 1)
            if j < REPLAY_CAP: b[j] = row.detach().cpu().clone()
    def _buf_sample(n):
        b = _rep["buf"]
        if not b or n <= 0: return None
        idx = _rnd.sample(range(len(b)), min(n, len(b)))
        return torch.stack([b[i] for i in idx])
    if REPLAY: print(f"[replay] ON  cap {REPLAY_CAP}  ({'surprise-gated' if SURPRISE_REPLAY else 'uniform'})")
    import contextlib
    _dt = "cuda" if "cuda" in str(dev) else "cpu"
    AMPCTX = (lambda: torch.autocast(_dt, dtype=torch.bfloat16)) if getattr(cfg, "AMP", False) else (lambda: contextlib.nullcontext())
    if getattr(cfg, "AMP", False): print(f"[amp] bf16 autocast ON ({_dt})")
    # ---- background batch prefetch: overlaps the single-threaded tokenizer with GPU compute ----
    import threading, queue as _queue
    PREFETCH = os.environ.get("PREFETCH", "1") == "1" and bool(TRAIN)
    _bq = _queue.Queue(maxsize=8); _pstop = threading.Event()
    MP_WORKERS = int(os.environ.get("MP_WORKERS", "0"))         # parallel-tokenizer worker PROCESSES (0 = off, use prefetch thread)
    _mpprod = None
    if MP_WORKERS > 0 and sysm.dyntok is not None and TRAIN:
        from mp_tokenizer import MPBatchProducer
        _mpprod = MPBatchProducer(TRAIN, sysm.dyntok, cfg.CTX, cfg.BATCH, MP_WORKERS)
        PREFETCH = False                                       # MP producer replaces the single-thread prefetch
        print(f"[mp-tokenizer] {MP_WORKERS} worker processes ON (parallel segmentation across cores)")
    def _producer():
        while not _pstop.is_set():
            try:
                b = dyn_batch(TRAIN, sysm.dyntok, cfg.BATCH, cfg.CTX) if sysm.dyntok is not None else sample_batch(TRAIN, cfg)
            except Exception:
                continue
            if b is None: continue
            while not _pstop.is_set():
                try: _bq.put(b, timeout=0.5); break
                except _queue.Full: continue
    if PREFETCH:
        threading.Thread(target=_producer, daemon=True).start()
        print("[prefetch] batch worker ON (overlaps tokenizer with GPU)")
    sysm.train(); t0 = time.time(); step = 0
    import math as _math
    _SCHED = str(getattr(cfg, "LR_SCHEDULE", "constant")); _LMIN = cfg.LR * float(getattr(cfg, "LR_MIN_FRAC", 0.1)); _WSD = float(getattr(cfg, "WSD_DECAY_FRAC", 0.2))
    def _lr_at(gstep):                                      # warmup, then {constant | cosine decay | wsd stable-then-decay}
        if cfg.LR_WARMUP > 0 and gstep < cfg.LR_WARMUP: return cfg.LR * (gstep + 1) / cfg.LR_WARMUP
        prog = min(1.0, (gstep - cfg.LR_WARMUP) / max(1, cfg.STEPS - cfg.LR_WARMUP))
        if _SCHED == "wsd":
            if prog < 1 - _WSD: return cfg.LR
            return _LMIN + (cfg.LR - _LMIN) * (1 - (prog - (1 - _WSD)) / _WSD)
        return cfg.LR                                       # constant (current default)
    _DENOISE = float(getattr(cfg, "DENOISE", 0.0)); _DMODE = str(getattr(cfg, "DENOISE_MODE", "sub"))
    _FUZZY = int(getattr(cfg, "FUZZY", 0)); _FZ_REB = max(1, int(getattr(cfg, "FUZZY_REBUILD", 2000)))
    if _FUZZY and sysm.dyntok is not None:
        sysm.dyntok.set_fuzzy(True); print(f"[fuzzy] model input uses the edit-distance-1 correcting tokenizer (index rebuild every {_FZ_REB} steps)")
    _UNMERGE = int(getattr(cfg, "UNMERGE", 0)); _UNMERGE_MIN = float(getattr(cfg, "UNMERGE_MIN", 3.0))
    if _UNMERGE and sysm.dyntok is not None:
        sysm.dyntok.track_usage(True); print(f"[un-merge] retiring merged tokens unused over {_UNMERGE}-step windows (min use {_UNMERGE_MIN})")
    _DIFF = int(getattr(cfg, "DIFFICULTY_CURR", 0)); _train_easy = None
    if _DIFF > 0 and sysm.dyntok is not None:
        _order = sorted(range(len(TRAIN)), key=lambda i: len(set(TRAIN[i].tolist())) / max(1, len(TRAIN[i])))
        _train_easy = [TRAIN[i] for i in _order]; print(f"[difficulty] easy (low-byte-diversity) windows first, widening to full over {_DIFF} steps")
    _RECON = float(getattr(cfg, "RECON", 0.0))
    _CTX0 = int(getattr(cfg, "CTX_START", 0)); _CRAMP = max(1, int(getattr(cfg, "CTX_RAMP_STEPS", 2000))); _GROW0 = int(getattr(cfg, "GROWTH_START", 0))
    if _RECON > 0: print(f"[reconstruct] per-position clean-token head on (w={_RECON}); use sysm.reconstruct(x) for the correction loop")
    if _CTX0 > 0: print(f"[curriculum] sequence length {_CTX0} -> {cfg.CTX} over {_CRAMP} steps (short first)")
    if _GROW0 > 0: print(f"[curriculum] growth/turnover held until step {_GROW0} (form foundation experts first)")
    def _cur_len(gstep):                                        # curriculum sequence length at this step
        if _CTX0 <= 0 or _CTX0 >= cfg.CTX: return cfg.CTX
        return min(cfg.CTX, _CTX0 + (cfg.CTX - _CTX0) * gstep // _CRAMP)
    if _DENOISE > 0: print(f"[denoise] corrupting {_DENOISE:.0%} of input tokens ({_DMODE}); targets stay clean -> error correction")
    def _corrupt(x):                                            # corrupt INPUT tokens; caller keeps clean targets
        xc = x.clone(); B, L = xc.shape; V = max(2, sysm.V)
        m = torch.rand(B, L) < _DENOISE; m[:, 0] = False        # keep first token as an anchor
        if _DMODE in ("sub", "mix") and int(m.sum()) > 0:       # substitution: replace with a random valid token
            xc[m] = torch.randint(0, V, (int(m.sum()),), dtype=xc.dtype)
        if _DMODE in ("swap", "mix"):                           # adjacent swap: transpose neighboring tokens
            for b, i in (torch.rand(B, L - 1) < _DENOISE * 0.5).nonzero().tolist():
                xc[b, i], xc[b, i + 1] = xc[b, i + 1].clone(), xc[b, i].clone()
        return xc
    _GA = max(1, int(getattr(cfg, "GRAD_ACCUM", 1))); _mtp_k = max(1, int(getattr(cfg, "MTP_K", 1)))
    if _GA > 1: print(f"[grad-accum] {_GA} microbatches/step -> effective batch {cfg.BATCH * _GA}")
    if _mtp_k > 1: print(f"[multi-token] predicting next {_mtp_k} tokens (aux heads on t+2..t+{_mtp_k})")
    import torch.nn.functional as _F
    def _mtp_aux_loss(mtp_logits, x, k):                        # extra heads predict tokens 2..K ahead
        tot = 0.0
        for i, lgi in enumerate(mtp_logits):                   # head i -> token at offset (i+2)
            off = i + 2
            if x.size(1) <= off: continue
            tot = tot + _F.cross_entropy(lgi[:, :-off].reshape(-1, lgi.size(-1)), x[:, off:].reshape(-1))
        return tot / max(1, len(mtp_logits))
    _WEMA = float(getattr(cfg, "EMA_DECAY", 0.0)); _wema = {}          # weight EMA (separate from the loss-ema logging var)
    def _wema_update():
        if _WEMA <= 0: return
        for n, p in sysm.named_parameters():
            s = _wema.get(n)
            if s is None or s.shape != p.shape: _wema[n] = p.detach().clone()   # (re)seed grown/culled params
            else: s.mul_(_WEMA).add_(p.detach(), alpha=1 - _WEMA)
    def _wema_swap():                                                  # swap EMA weights in for eval; return live to restore
        if _WEMA <= 0: return None
        live = {}
        for n, p in sysm.named_parameters():
            if n in _wema and _wema[n].shape == p.shape:
                live[n] = p.detach().clone(); p.data.copy_(_wema[n])
        return live
    def _wema_restore(live):
        if live is None: return
        for n, p in sysm.named_parameters():
            if n in live: p.data.copy_(live[n])
    _best_ood = 1e9; _no_improve = 0; _best_path = ckpt_path.replace("ckpt.pt", "best.pt")
    while total + step < cfg.STEPS:
        gstep = total + step
        for pg in opt.param_groups: pg["lr"] = _lr_at(gstep)   # warmup + LR schedule (constant/cosine/wsd)
        cfg.ENABLE_REENCODE = REENC_BASE and (total + step) >= cfg.REENCODE_WARMUP
        if _DIFF > 0 and _train_easy is not None:              # difficulty curriculum: sample from an expanding easy prefix
            cur = max(64, int(len(_train_easy) * min(1.0, gstep / _DIFF)))
            fresh = dyn_batch(_train_easy[:cur], sysm.dyntok, cfg.BATCH, cfg.CTX)
            if fresh is None: continue
        elif _mpprod is not None:
            try: fresh = _mpprod.get(timeout=60)               # parallel workers segment; get() also tallies pairs
            except Exception: continue
        elif PREFETCH:
            try: fresh = _bq.get(timeout=60)
            except _queue.Empty: continue
        elif sysm.dyntok is not None:
            fresh = dyn_batch(TRAIN, sysm.dyntok, cfg.BATCH, cfg.CTX)
            if fresh is None: continue
        else:
            fresh = sample_batch(TRAIN, cfg)
        x_cpu = fresh
        if REPLAY:                                       # rehearse buffered surprising rows alongside fresh
            ex = _buf_sample(cfg.BATCH // 4)
            if ex is not None: x_cpu = torch.cat([fresh, ex], 0)
        if _CTX0 > 0:                                           # curriculum: short sequences first, growing to full CTX
            cl = _cur_len(gstep)
            if cl < x_cpu.size(1): x_cpu = x_cpu[:, :cl].contiguous()
        posnov = sysm.surprise.score_pos(x_cpu).to(dev); x = x_cpu.to(dev)   # x = CLEAN target
        x_in = _corrupt(x_cpu).to(dev) if _DENOISE > 0 else x                # denoising: forward on corrupted input
        with AMPCTX():
            lg, aux = sysm(x_in, posnov)                        # predict from (possibly) corrupted context...
            loss = ce(lg, x) + cfg.PONDER * aux["depth"] + cfg.REENC_COST * aux["enc"] + cfg.COUNTERPART_COST * aux["cpl"] + float(getattr(cfg, "LB_COST", 0.0)) * aux.get("lb", 0.0)   # ...against CLEAN tokens (learns to correct)
            if _mtp_k > 1 and aux.get("mtp"):                   # multi-token prediction: heads predict t+2..t+K
                loss = loss + _mtp_aux_loss(aux["mtp"], x, _mtp_k)
            if _RECON > 0 and aux.get("recon") is not None:     # denoise-AE: reconstruct the CLEAN token at each position
                _r = aux["recon"]; loss = loss + _RECON * _F.cross_entropy(_r.reshape(-1, _r.size(-1)), x.reshape(-1))
        (loss / _GA).backward()                                 # scale for gradient accumulation
        if (gstep + 1) % _GA == 0:                              # optimizer step once per _GA microbatches
            torch.nn.utils.clip_grad_norm_(sysm.parameters(), cfg.GRAD_CLIP); opt.step(); opt.zero_grad()
            _wema_update()                                      # weight EMA (no-op if EMA_DECAY=0)
        sysm.surprise.update(x_cpu)
        sysm.promote_senses(x, posnov)                      # sparse sense: spawn folders for surprising tokens (no-op if dense/off)
        if sysm.dyntok is not None:                         # EMERGENT vocab: mint hot pairs (multi per step)
            for _ in range(cfg.MINT_PER_STEP):
                mg = sysm.dyntok.maybe_grow()
                if not mg: break
                sysm.grow_vocab(mg[1], mg[2])              # (no optimizer rebuild: rows pre-allocated at VMAX)
                if _mpprod is not None: _mpprod.broadcast([(mg[1], mg[2])])   # keep worker vocab replicas in sync
        if hasattr(sysm.mem, "gate"):                       # MirroredMemory: adaptive-gated write
            gate_nov = getattr(sysm.surprise, "last_ce", None)
            if gate_nov is None: gate_nov = posnov.mean(1).detach().cpu()
            via = int(aux["mass"][:len(sysm.bodies)].argmax())
            sysm.mem.write(aux["gist"].detach(), aux["hf"].mean(1).detach(), gate_nov, via)
        else:
            sysm.mem.write(aux["gist"].detach(), aux["hf"].mean(1).detach())
        if REPLAY:                                       # buffer surprising FRESH rows (fresh = first BATCH rows of x)
            se = getattr(sysm.surprise, "last_ce", None)
            for j in range(fresh.size(0)):
                if (not SURPRISE_REPLAY) or se is None or _rep["gate"].step(float(se[j])):
                    _buf_add(fresh[j])

        fl = float(ce(lg, x).detach()); ema = fl if ema is None else 0.99 * ema + 0.01 * fl
        for i in range(len(sysm.bodies)): sysm.usage[i] = 0.99 * sysm.usage[i] + 0.01 * float(aux["mass"][i])
        g = total + step

        if g > cfg.WARMUP_STEPS and g >= _GROW0:               # curriculum: no growth until foundation experts formed
            act = gc.decide(g, fl, sysm.usage)
            if act is not None:
                kind = act[0]
                if kind == "spawn":
                    sysm.add_node(); seed_node(sysm, x[:1], posnov[:1], cfg); gc.on_spawn()
                    print(f"  [grow] -> {len(sysm.bodies)} nodes @ step {g}")
                elif kind == "prune":
                    sysm.prune_node(act[1]); gc.on_prune(act[1])
                    print(f"  [prune] -> {len(sysm.bodies)} nodes @ step {g}")
                elif kind == "depth":
                    nl = sysm.base.grow_depth(); gc.on_depth()
                    print(f"  [grow-depth] -> {nl} layers @ step {g}  (breadth saturated)")
                opt = make_opt(sysm.parameters(), cfg)
                last_spawn = g

        if _FUZZY and sysm.dyntok is not None and g > 0 and g % _FZ_REB == 0:
            sysm.dyntok.build_fuzzy_index()                    # refresh fuzzy index with newly-minted tokens
        if _UNMERGE and sysm.dyntok is not None and g > 0 and g % _UNMERGE == 0:
            r = sysm.dyntok.retire_stale(_UNMERGE_MIN)         # un-merge tokens that stopped paying off
            if r: print(f"  [un-merge] retired {r} stale merged tokens @ step {g}")
        if getattr(cfg, "PRUNE_ECO", 0) == 1 and g > cfg.WARMUP_STEPS and g % cfg.PRUNE_EVERY == 0 and g >= _GROW0:
            if sysm.cull_worst():                               # evolutionary turnover: cull the weakest...
                sysm.add_node(); seed_node(sysm, x[:1], posnov[:1], cfg)   # ...and respawn (mutation of the best if MUTATE=1)
                print(f"  [turnover] culled weakest + respawned -> {len(sysm.bodies)} experts @ step {g}")
                opt = make_opt(sysm.parameters(), cfg)

        if g % cfg.LOG_EVERY == 0:
            sps = (step + 1) / max(1e-9, time.time() - t0)
            print(f"step {g:>7} | train_ce {fl:.3f} | ema {ema:.3f} | nodes {len(sysm.bodies)} | layers {len(sysm.base.blocks)} | {sps:.1f} it/s")
        if g % cfg.EVAL_EVERY == 0:
            _wlive = _wema_swap()                            # evaluate + save-best on the EMA weights (if EMA on)
            m = evaluate_system(sysm, HELD, OOD, cfg)
            rec = {"step": g, "train_ce": round(fl, 4), "ema": round(ema, 4), "nodes": len(sysm.bodies),
                   "reenc_share": round(float(aux["mass"][len(sysm.bodies) + 1]), 3), **m}
            with open(log_path, "a") as f: f.write(json.dumps(rec) + "\n")
            print(f"  [eval@{g}] in-held {m['in_held']} | OOD {m['ood']} | surprise held/OOD {m['nov_held']}/{m['nov_ood']} | mem-conf {m['memconf_held']}/{m['memconf_ood']}")
            if hasattr(sysm.mem, "gate"):
                print(f"           mem(mirror) {sysm.mem.n}/{cfg.MEMCAP} filled | writes {sysm.mem.writes} skips {sysm.mem.skips} | gate θ {sysm.mem.gate.theta:.2f} | in_sync {sysm.mem.in_sync()}")
            if m["ood"] < _best_ood - 1e-3:                  # track best held OOD; save the best model
                _best_ood = m["ood"]; _no_improve = 0
                if cfg.EARLY_STOP > 0: save_system(sysm, _best_path, total=total + step, ema=ema, last_spawn=last_spawn, opt=opt.state_dict())
            else:
                _no_improve += 1
                if cfg.EARLY_STOP > 0 and _no_improve >= cfg.EARLY_STOP:
                    print(f"  [early-stop] held OOD hasn't improved in {cfg.EARLY_STOP} evals (best {_best_ood}); stopping. best model -> best.pt")
                    _wema_restore(_wlive); break
            _wema_restore(_wlive)                            # restore LIVE weights: continued training + resume ckpt use live
        if g % cfg.CKPT_EVERY == 0 and g > 0:
            save_system(sysm, ckpt_path, total=total + step, ema=ema, last_spawn=last_spawn, opt=opt.state_dict())
            print(f"  [ckpt] saved @ step {g}")
        step += 1

    save_system(sysm, ckpt_path, total=total + step, ema=ema, last_spawn=last_spawn, opt=opt.state_dict())
    if PREFETCH: _pstop.set()                               # stop the prefetch worker before final eval/save
    if _mpprod is not None: _mpprod.stop()                  # stop MP tokenizer workers + clean temp corpus file
    print(f"\nDONE @ step {total + step}")
    print(f"  embedder mix per domain: {embed_mix(sysm, HELD)}")
    if getattr(sysm, "sense_k", 0) > 0:
        print(f"  sense mix per domain:    {sense_mix(sysm, HELD)}")
        if getattr(sysm, "sense_slots", 0) > 0:
            print(f"  sparse sense: {sysm.n_promoted}/{sysm.sense_slots} folders spawned")
    print(f"  checkpoint: {ckpt_path}\n  log: {log_path}")

if __name__ == "__main__":
    main()
