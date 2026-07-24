"""world_model.py — FIRST BRICK of a GENERAL world model (physics-like, modality-agnostic).

Goal (USER): a model of EXTERNAL reality that learns how the world EVOLVES (dynamics / consequences), into which
new SENSES plug via the lowest embedding layer. This file is the trunk: a latent forward-dynamics core.

  observation window --E--> latent world-state z  --P--> predicted NEXT latent  (compare to E(next window))

Objective is JEPA/VICReg-style: predict the REPRESENTATION of the future, not raw tokens/pixels. Working in latent
space is what makes it (a) modality-agnostic — text now, audio/vision later through the same E interface — and
(b) physics-like — it learns dynamics, not surface detail. A variance+covariance regularizer prevents the trivial
collapse (E -> constant) so the "prediction" is real.

This module is standalone + gated (WORLD_MODEL=0 by default in the product loop). `python3 world_model.py` runs a
CPU probe on a synthetic world with KNOWN latent dynamics and reports whether the core actually learns them.
"""
import os
import torch
import torch.nn as nn
import torch.nn.functional as F


class WorldEncoder(nn.Module):
    """Observation -> latent world-state. Modality-agnostic: in the product loop the input is the model's embedding
    of an observation WINDOW (like the domain SigEncoder); here it is a feature vector. New senses = new E path into
    the SAME latent."""
    def __init__(s, d_obs, d_lat, hid=128):
        super().__init__()
        s.net = nn.Sequential(nn.Linear(d_obs, hid), nn.GELU(), nn.Linear(hid, hid), nn.GELU(), nn.Linear(hid, d_lat))

    def forward(s, o): return s.net(o)


class ForwardModel(nn.Module):
    """The 'physics': predict the NEXT latent world-state from the current one (+ optional action/context)."""
    def __init__(s, d_lat, hid=128, d_ctx=0):
        super().__init__()
        s.net = nn.Sequential(nn.Linear(d_lat + d_ctx, hid), nn.GELU(), nn.Linear(hid, hid), nn.GELU(), nn.Linear(hid, d_lat))

    def forward(s, z, ctx=None):
        x = z if ctx is None else torch.cat([z, ctx], -1)
        return z + s.net(x)                       # residual: predict the CHANGE (delta) -> stable multi-step rollout


def _var_cov(z):
    """VICReg-style anti-collapse: keep each latent dim's std ~>=1 (variance) and decorrelate dims (covariance)."""
    z = z - z.mean(0)
    std = torch.sqrt(z.var(0) + 1e-4)
    var_loss = F.relu(1.0 - std).mean()
    n, d = z.shape
    cov = (z.T @ z) / (n - 1)
    cov_loss = (cov.fill_diagonal_(0) ** 2).sum() / d
    return var_loss, cov_loss


def wm_loss(enc, fwd, o_t, o_next, ctx=None, w_var=1.0, w_cov=0.04):
    """Latent forward-prediction loss. No token/pixel reconstruction -> modality-agnostic."""
    z_t = enc(o_t)
    z_next = enc(o_next)
    pred = fwd(z_t, ctx)
    inv = F.mse_loss(pred, z_next)                                  # predict the future REPRESENTATION
    v1, c1 = _var_cov(z_t); v2, c2 = _var_cov(z_next)
    return inv + w_var * (v1 + v2) + w_cov * (c1 + c2), inv.item()


class DynamicsPopulation(nn.Module):
    """The world model's SOCIETY: a POPULATION of forward-dynamics predictors over a SHARED latent -- the world model's
    analogue of the expert society. Routes each latent to the predictor(s) whose 'physics' fits, BLENDS them at the
    prediction level, tracks per-predictor FITNESS, GROWS on plateau, and SOFT-CULLS the unused -- so subspecialties of
    dynamics EMERGE and are SELECTED, exactly like experts/domains, instead of one monolithic net. Same primitive, reused."""
    def __init__(s, d_lat, n0=2, nmax=8, hid=128, route_dim=32, tau=1.0):
        super().__init__()
        s.d_lat, s.hid, s.nmax, s.route_dim, s.tau = d_lat, hid, nmax, route_dim, tau
        s.preds = nn.ModuleList([ForwardModel(d_lat, hid) for _ in range(n0)])
        s.qproj = nn.Linear(d_lat, route_dim)
        s.keys = nn.ParameterList([nn.Parameter(torch.randn(route_dim) * 0.1) for _ in range(n0)])
        s.register_buffer("fit", torch.full((nmax,), float("nan")))   # EMA routing-weighted forward-error (lower = fitter)
        s.register_buffer("mass", torch.zeros(nmax))                  # EMA routing mass (for stale/cull)
        s.register_buffer("alive", torch.ones(nmax))                  # soft-cull mask (reversible: params kept)

    def n(s): return len(s.preds)

    def route(s, z):                                                  # (N,d_lat) -> (N,n) routing weights
        q = s.qproj(z); K = torch.stack(list(s.keys))
        logits = q @ K.t() / (s.route_dim ** 0.5) + torch.log(s.alive[:s.n()].clamp_min(1e-6))
        return F.softmax(logits / s.tau, -1)

    def forward(s, z):
        w = s.route(z)                                               # (N,n)
        outs = torch.stack([p(z) for p in s.preds], 1)               # (N,n,d_lat) each predictor's guess
        pred = (w.unsqueeze(-1) * outs).sum(1)                        # (N,d_lat) blended
        return pred, w, outs

    @torch.no_grad()
    def update_fitness(s, w, outs, z_next, decay=0.98):
        err = (outs - z_next.unsqueeze(1)).pow(2).mean(-1)           # (N,n) per-predictor error
        wmass = w.sum(0)
        werr = (w * err).sum(0) / wmass.clamp_min(1e-6)
        for i in range(s.n()):
            s.mass[i] = decay * s.mass[i] + (1 - decay) * float(wmass[i])
            s.fit[i] = float(werr[i]) if torch.isnan(s.fit[i]) else decay * s.fit[i] + (1 - decay) * float(werr[i])

    def grow(s, z_seed=None):
        """Add a predictor CLONED from the fittest (preserve learning), keyed at the mispredicted region. Returns the
        new params so the CALLER adds them to the optimizer (mirrors fabric growth). None if at capacity."""
        if s.n() >= s.nmax: return None
        valid = [i for i in range(s.n()) if not torch.isnan(s.fit[i])]
        best = min(valid, key=lambda i: float(s.fit[i])) if valid else 0
        new = ForwardModel(s.d_lat, s.hid).to(s.keys[0].device); new.load_state_dict(s.preds[best].state_dict())
        s.preds.append(new)
        k = (s.qproj(z_seed).detach().mean(0) if z_seed is not None else torch.randn(s.route_dim, device=s.keys[0].device) * 0.1)
        s.keys.append(nn.Parameter(k))
        return list(new.parameters()) + [s.keys[-1]]

    def soft_cull(s, min_mass=1e-3):
        """Deactivate persistently-unused predictors (route ~0) -- reversible, keeps their learning, like a dormant expert."""
        culled = 0
        for i in range(s.n()):
            if int(s.alive[:s.n()].sum()) <= 1: break               # never cull the last live predictor
            if float(s.mass[i]) < min_mass and s.alive[i] > 0:
                s.alive[i] = 0.0; culled += 1
        return culled


def pop_loss(pop, z_t, z_next, w_bal=0.01):
    """Population forward-prediction + load-balance (stops early collapse to one predictor). Updates fitness. var/cov
    anti-collapse stays on the ENCODER's latent (computed by the caller), as before."""
    pred, w, outs = pop(z_t)
    inv = F.mse_loss(pred, z_next)
    bal = w.size(1) * (w.mean(0) ** 2).sum()                        # uniform load = w.size(1)*(1/n)^2 summed; higher = imbalanced
    pop.update_fitness(w, outs, z_next.detach())
    return inv + w_bal * bal, w, inv.item()


# ----------------------------------------------------------------------------------------------------------------
def _probe():
    """CPU sanity: a synthetic WORLD with known linear latent dynamics u_{t+1}=A u_t, observed as o=W u. If the core
    works it should (1) predict the next latent BETTER than 'assume no change', (2) RECOVER the hidden world-state
    (linear-probe R^2), (3) NOT collapse. Deterministic (seeded) so the numbers are reproducible."""
    g = torch.Generator().manual_seed(0)
    M, D_OBS, D_LAT, T, N = 8, 32, 16, 12, 3000

    # --- build a world: block rotations (stable magnitude, genuinely evolving state) ---
    A = torch.zeros(M, M)
    ang = 0.3 + 0.5 * torch.rand(M // 2, generator=g)
    for k in range(M // 2):
        c, s = torch.cos(ang[k]), torch.sin(ang[k])
        A[2 * k, 2 * k] = c; A[2 * k, 2 * k + 1] = -s; A[2 * k + 1, 2 * k] = s; A[2 * k + 1, 2 * k + 1] = c
    W = torch.randn(M, D_OBS, generator=g) / (M ** 0.5)            # observation projection

    u = torch.randn(N, M, generator=g)
    obs, states = [], []
    for _ in range(T):
        states.append(u.clone()); obs.append(u @ W)
        u = u @ A.T
    OBS = torch.stack(obs, 1)                                       # (N, T, D_OBS)
    ST = torch.stack(states, 1)                                     # (N, T, M) ground-truth world state
    o_t = OBS[:, :-1].reshape(-1, D_OBS); o_next = OBS[:, 1:].reshape(-1, D_OBS)
    u_t = ST[:, :-1].reshape(-1, M)

    enc = WorldEncoder(D_OBS, D_LAT); fwd = ForwardModel(D_LAT)
    opt = torch.optim.Adam(list(enc.parameters()) + list(fwd.parameters()), lr=2e-3)
    for step in range(4000):
        idx = torch.randint(0, o_t.size(0), (512,), generator=g)
        loss, inv = wm_loss(enc, fwd, o_t[idx], o_next[idx])
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 1000 == 0: print(f"  step {step:4d} | loss {loss.item():.4f} | inv {inv:.4f}")

    with torch.no_grad():
        z_t = enc(o_t); z_next = enc(o_next); pred = fwd(z_t)
        persist = F.mse_loss(z_t, z_next).item()                   # baseline: "assume the world doesn't change"
        model = F.mse_loss(pred, z_next).item()                    # world model's forward prediction
        std = z_t.std(0).mean().item()                             # collapse check (want ~1)
        # multi-step rollout: predict K steps ahead from t=0, compare to true encoded latent
        z = enc(OBS[:, 0]); roll = []
        for k in range(1, 6):
            z = fwd(z); roll.append(F.mse_loss(z, enc(OBS[:, k])).item())
        # linear probe: did the latent RECOVER the hidden world state u?
        zc = z_t - z_t.mean(0); uc = u_t - u_t.mean(0)
        Wls = torch.linalg.lstsq(zc, uc).solution
        r2 = 1 - (uc - zc @ Wls).pow(2).sum().item() / uc.pow(2).sum().item()

    print("\n=== WORLD-MODEL FIRST BRICK — probe on a synthetic world with known dynamics ===")
    print(f"  forward-prediction MSE : {model:.4f}   (world model)")
    print(f"  persistence-baseline   : {persist:.4f}   ('assume no change')")
    print(f"  >> beats persistence by : {(1 - model / persist) * 100:.1f}%   (positive = it learned the DYNAMICS)")
    print(f"  latent std             : {std:.2f}   (want ~1; near-0 = collapsed = fake)")
    print(f"  hidden-state recovery  : R^2 {r2:.3f}   (linear-probe latent -> true world state; 1.0 = fully recovered)")
    print(f"  5-step rollout MSE      : {[round(x, 3) for x in roll]}   (should stay bounded, not explode)")
    ok = model < 0.7 * persist and std > 0.5 and r2 > 0.8
    print(f"  VERDICT: {'MECHANISM WORKS' if ok else 'inconclusive — needs tuning'}")
    return ok


def _probe_population():
    """CPU sanity for the SEPARATED world model: a world with K DISTINCT dynamics regimes. A monolithic forward-model
    must average them; a POPULATION should SPECIALIZE (route each regime to its own predictor) and predict better.
    Reports population vs monolithic vs persistence, routing specialization, and that it GREW."""
    g = torch.Generator().manual_seed(1)
    M, D_OBS, D_LAT, T, NPER, K = 6, 24, 12, 10, 1500, 3
    W = torch.randn(M, D_OBS, generator=g) / (M ** 0.5)
    As = []                                                          # K different "physics"
    for _k in range(K):
        A = torch.zeros(M, M); ang = 0.2 + 0.9 * torch.rand(M // 2, generator=g)
        for j in range(M // 2):
            c, s = torch.cos(ang[j]), torch.sin(ang[j])
            A[2*j, 2*j] = c; A[2*j, 2*j+1] = -s; A[2*j+1, 2*j] = s; A[2*j+1, 2*j+1] = c
        As.append(A)
    obs, reg = [], []
    for _k in range(K):
        u = torch.randn(NPER, M, generator=g); seq = []
        for _ in range(T): seq.append(u @ W); u = u @ As[_k].T
        obs.append(torch.stack(seq, 1)); reg.append(torch.full((NPER,), _k))
    OBS = torch.cat(obs, 0); REG = torch.cat(reg, 0)                 # (N,T,D_OBS), regime label per sequence
    o_t = OBS[:, :-1].reshape(-1, D_OBS); o_next = OBS[:, 1:].reshape(-1, D_OBS)
    reg_flat = REG.repeat_interleave(T - 1)

    def train(pop_mode):
        torch.manual_seed(0)
        enc = WorldEncoder(D_OBS, D_LAT, 96)
        if pop_mode:
            head = DynamicsPopulation(D_LAT, n0=1, nmax=K + 1, hid=96, route_dim=16)   # START at 1 -> must GROW
        else:
            head = ForwardModel(D_LAT, 96)
        opt = torch.optim.Adam(list(enc.parameters()) + list(head.parameters()), lr=3e-3)
        for step in range(5000):
            idx = torch.randint(0, o_t.size(0), (512,), generator=g)
            zt = enc(o_t[idx]); zn = enc(o_next[idx])
            v, c = _var_cov(zt)
            if pop_mode:
                l, _, inv = pop_loss(head, zt, zn); loss = l + v + 0.04 * c
                if step and step % 1200 == 0 and head.n() < head.nmax:   # GROW on schedule (stands in for a plateau trigger)
                    newp = head.grow(zt.detach())
                    if newp: opt.add_param_group({"params": newp})
            else:
                loss = F.mse_loss(head(zt), zn) + v + 0.04 * c
            opt.zero_grad(); loss.backward(); opt.step()
        return enc, head

    enc_m, mono = train(False)
    enc_p, pop = train(True)
    with torch.no_grad():
        def fwd_mse(enc, head):
            z = enc(o_t); zn = enc(o_next)
            pred = head(z)[0] if isinstance(head, DynamicsPopulation) else head(z)
            return F.mse_loss(pred, zn).item(), F.mse_loss(z, zn).item()
        mm, mp = fwd_mse(enc_m, mono)
        pm, pp = fwd_mse(enc_p, pop)
        # routing specialization: for each regime, which predictor gets the most mass?
        z = enc_p(o_t); w = pop.route(z)                            # (N,n)
        dom = w.argmax(1)
        pur = []
        for _k in range(K):
            sel = dom[reg_flat == _k]
            if len(sel): pur.append((sel.bincount(minlength=pop.n()).max().item()) / len(sel))
        purity = sum(pur) / len(pur)

    print("\n=== SEPARATED WORLD MODEL — population vs monolithic on a MULTI-REGIME world (K=3 different physics) ===")
    print(f"  persistence baseline    : {pp:.4f}")
    print(f"  MONOLITHIC forward-MSE   : {mm:.4f}   (one net must average all regimes)")
    print(f"  POPULATION forward-MSE   : {pm:.4f}   (grew 1 -> {pop.n()} predictors)")
    print(f"  >> population beats monolithic by : {(1 - pm / max(mm, 1e-9)) * 100:+.1f}%")
    print(f"  routing specialization   : {purity:.2f}   (1.0 = each regime consistently uses ONE predictor)")
    ok = pm < 0.9 * mm and purity > 0.6 and pop.n() > 1
    print(f"  VERDICT: {'SEPARATION HELPS (specializes + beats monolithic)' if ok else 'inconclusive — needs tuning'}")
    return ok


if __name__ == "__main__":
    _probe()
    _probe_population()
