"""Throughput + memory profiler -- RUN THIS BEFORE committing to a long run so a 3-day surprise can't happen again.
Measures real per-step cost at the END-OF-TRAINING footprint (PROBE_PEAK grows experts->NMAX and forces the output
head to full VMAX width, the dominant late-training term), reports where the GPU time goes, peak VRAM, and projects
the full fulltest wall-clock.

  python3 control.py profile [--preset X] [KNOB=val ...]        # add PROBE_PEAK=1 to measure the real (peak) cost
Honors: PROF_STEPS (timed steps, default 40), PROF_WARMUP (default 8), STEPS/SWEEP_STEPS (for projection).
"""
import os, sys, time
import torch


def main():
    from config import cfg
    from system import build_system, ce
    from optimizers import make_opt
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    on_cuda = dev.type == "cuda"
    sysm = build_system(cfg, dev)
    for _ in range(int(getattr(cfg, "N0", 6))): sysm.add_node()

    peak = int(getattr(cfg, "PROBE_PEAK", 0)) == 1 or os.environ.get("PROBE_PEAK") == "1"
    if peak:                                                   # force the real end-of-training footprint
        while len(sysm.bodies) < int(cfg.NMAX):
            try: sysm.add_node()
            except Exception: break
        sysm.V = sysm.VMAX; sysm.base.V = sysm.base.VMAX       # logits are (B,L,VMAX) -- the dominant late term
        if getattr(sysm, "_comp_cache", None) is not None: sysm._comp_dirty = True
    sysm.train()
    B, L, V = int(cfg.BATCH), int(cfg.CTX), int(sysm.V)
    print(f"profiling  d{cfg.D_MODEL} L{len(sysm.base.blocks)}  batch {B}  ctx {L}  vocab {V}  experts {len(sysm.bodies)}"
          f"{'  [PEAK footprint]' if peak else '  (fresh vocab -- pass PROBE_PEAK=1 for the real cost)'}  on {dev.type}\n")

    opt = make_opt(sysm.parameters(), cfg)
    def batch():
        return torch.randint(0, max(2, V), (B, L + 1), device=dev)   # compute depends on shape+V, not token values

    def step():
        xb = batch(); x, y = xb[:, :-1], xb[:, 1:]
        pn = sysm.surprise.score_pos(x)
        lg, aux = sysm(x, pn)
        loss = ce(lg, y) + (aux.get("lb", 0.0) if isinstance(aux, dict) else 0.0)
        opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
        return float(loss)

    for _ in range(int(getattr(cfg, "PROF_WARMUP", 8))): step()     # warmup: build lazy state, pick kernels
    if on_cuda: torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()

    N = int(getattr(cfg, "PROF_STEPS", 40))
    t0 = time.time()
    for _ in range(N): step()
    if on_cuda: torch.cuda.synchronize()
    dt = time.time() - t0
    its = N / dt; ms = 1000.0 / its; toks = its * B * L
    print(f"THROUGHPUT: {its:.2f} it/s  |  {ms:.0f} ms/step  |  {toks:,.0f} tokens/s")
    if on_cuda:
        tot = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"PEAK VRAM:  {torch.cuda.max_memory_allocated()/1e9:.1f} GB / {tot:.0f} GB   (room for a bigger batch if well under total)")
    print()

    try:                                                            # where does the time go?
        from torch.profiler import profile as tprofile, ProfilerActivity
        acts = [ProfilerActivity.CPU] + ([ProfilerActivity.CUDA] if on_cuda else [])
        with tprofile(activities=acts) as prof:
            for _ in range(5): step()
        key = "self_cuda_time_total" if on_cuda else "self_cpu_time_total"
        print("TOP OPS BY TIME (big vocab head shows as aten::mm + log_softmax/nll; MoE dispatch as index/scatter):")
        print(prof.key_averages().table(sort_by=key, row_limit=12))
    except Exception as e:
        print(f"(op breakdown unavailable: {str(e)[:60]})")

    STEPS = int(getattr(cfg, "STEPS", 30000)); SW = int(getattr(cfg, "SWEEP_STEPS", 8000))
    rung1 = 6 * STEPS; rung2 = (10 + 11 + 8 + 6) * SW; total = rung1 + rung2
    hrs = total / its / 3600
    print(f"\nPROJECTED fulltest wall-clock at {its:.2f} it/s (peak config = the slow end, ~upper bound):")
    print(f"  Rung 1 (6 groups x {STEPS:,}): {rung1/its/3600:.1f} h  |  Rung 2 (~35 arms x {SW:,}): {rung2/its/3600:.1f} h")
    print(f"  TOTAL ~ {hrs:.1f} h ({hrs/24:.1f} days).  << check this BEFORE launching.")
    if hrs > 24:
        print("  -> over a day. Lower VMAX (shrinks the output head -- usually the hotspot), drop RECON/MTP,")
        print("     turn off COUNTERPARTS, raise batch if VRAM allows, or cut SWEEP_STEPS.")


if __name__ == "__main__":
    main()
