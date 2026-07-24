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


if __name__ == "__main__":
    _probe()
