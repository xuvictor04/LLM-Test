"""WORLD arms over AUD latents. W0 = the REAL src/world/api.py (memoryless population).
W1 = proposed WORLD_CONTEXT='gru' (causal GRU over z feeds the predictors).
W2 = W1 + proposed WORLD_HEAD='gmm' (mixture density over the next-z delta, sampled at generation)."""
import os
from common import *
TREE = "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm/design-world/tree/src"
sys.path.insert(0, TREE)
from spine import assemble, rng as srng
from world import api as world_api
_CFGS = None
def world_cfg():
    global _CFGS
    if _CFGS is None:
        _CFGS, _, _ = assemble.build(environ=dict(os.environ))
    return _CFGS["WORLD"]

D_MODEL = 128; LAT = 32

class AudObs(nn.Module):
    """AUD-owned: to_obs (media latent -> observation embedding, WORLD's plug) and
    from_world (WORLD latent -> media latent, the generation readout)."""
    def __init__(self, D=32):
        super().__init__()
        self.to_obs = nn.Linear(D, D_MODEL)
        self.from_world = nn.Sequential(nn.Linear(LAT, 128), nn.ELU(), nn.Linear(128, D))

class RealWorld(nn.Module):
    kind = "W0_real_memoryless"
    def __init__(self, seed=0):
        super().__init__()
        srng.reset_issued()
        self.cfg = world_cfg()
        self.w = world_api.build(self.cfg, d_model=D_MODEL, device="cpu", ctx_tokens=128, rng=srng.rng_for("world", seed))
        self.ps = nn.ParameterList(self.w.parameters())
    def loss(self, obs):
        st = world_api.loss_terms(self.cfg, self.w, obs)
        return st.loss, st
    def latent(self, obs): return self.w.encoder(obs)
    def step_pred(self, z, state=None):
        live = self.w.alive.nonzero(as_tuple=True)[0]
        sh = z.shape; zz = z.reshape(-1, sh[-1])
        wts, outs = world_api._route(self.w, zz, live)
        return (wts.unsqueeze(-1) * outs).sum(1).reshape(sh), None
    def rollout(self, z_prompt, n, sample=False):
        z = z_prompt[:, -1]; out = []
        for _ in range(n):
            z, _ = self.step_pred(z); out.append(z)
        return torch.stack(out, 1)

class CtxWorld(nn.Module):
    """proposed arm: same encoder shape, same VICReg term, same residual population, but predictors read
    [z_t, c_t] with c_t = causal GRU(z_<=t). gmm=True adds a K-mixture diagonal Gaussian over the delta."""
    def __init__(self, gmm=False, K=4, n0=3, cond_dim=0, detach_target=False):
        super().__init__()
        self.detach_target = detach_target
        self.kind = "W2_ctx_gru_gmm" if gmm else "W1_ctx_gru"
        self.encoder = nn.Sequential(nn.Linear(D_MODEL, 128), nn.Tanh(), nn.Linear(128, LAT))
        self.ctx = nn.GRU(LAT, 128, batch_first=True)
        self.qproj = nn.Linear(128 + LAT, 24); self.keys = nn.Parameter(torch.randn(n0, 24) * 0.1)
        self.gmm, self.K = gmm, K
        outw = (K * (2 * LAT + 1)) if gmm else LAT
        self.preds = nn.ModuleList([nn.Linear(128 + LAT, outw) for _ in range(n0)])
        for p in self.preds: nn.init.zeros_(p.weight); nn.init.zeros_(p.bias)
        self.cond = nn.Linear(cond_dim, 128) if cond_dim else None
    def latent(self, obs): return self.encoder(obs)
    def _heads(self, z, c):
        x = torch.cat([z, c], -1)
        wts = torch.softmax(self.qproj(x) @ self.keys.t() / 24 ** 0.5, -1)
        outs = torch.stack([p(x) for p in self.preds], -2)
        return wts, (wts.unsqueeze(-1) * outs).sum(-2)
    def h0(self, cond):
        return None if cond is None else torch.tanh(self.cond(cond)).unsqueeze(0)
    def nll_or_mse(self, z_t, c_t, z_next):
        wts, o = self._heads(z_t, c_t)
        bal = wts.shape[-1] * wts.reshape(-1, wts.shape[-1]).mean(0).pow(2).sum()
        if not self.gmm:
            pred = z_t + o; return F.mse_loss(pred, z_next), pred, bal
        B = o.shape[:-1]; K = self.K
        logit = o[..., :K]; mu = o[..., K:K + K * LAT].reshape(*B, K, LAT); ls = o[..., K + K * LAT:].reshape(*B, K, LAT).clamp(-5, 2) - 1.5
        d = (z_next - z_t).unsqueeze(-2)
        lp = (-0.5 * ((d - mu) / ls.exp()) ** 2 - ls - 0.9189).sum(-1) + torch.log_softmax(logit, -1)
        nll = -torch.logsumexp(lp, -1).mean() / LAT
        k = logit.argmax(-1, keepdim=True).unsqueeze(-1).expand(*B, 1, LAT)
        pred = z_t + mu.gather(-2, k).squeeze(-2)
        return nll, pred, bal
    def loss(self, obs, cond=None):
        z = self.encoder(obs)
        c, _ = self.ctx(z, self.h0(cond))
        pl, pred, bal = self.nll_or_mse(z[:, :-1], c[:, :-1], z[:, 1:].detach() if self.detach_target else z[:, 1:])
        v, cv = world_api._var_cov(z.reshape(-1, LAT))
        inv = F.mse_loss((pred if not self.gmm else pred).detach(), z[:, 1:].detach())
        loss = 0.1 * (pl + 0.01 * bal) + 1.0 * (v + 0.04 * cv)
        return loss, dict(inv=inv, latent_std=z.reshape(-1, LAT).std(0).mean())
    def rollout(self, z_prompt, n, sample=False, cond=None):
        c, h = self.ctx(z_prompt, self.h0(cond)); z = z_prompt[:, -1]; ct = c[:, -1]; out = []
        for _ in range(n):
            wts, o = self._heads(z, ct)
            if not self.gmm: z = z + o
            else:
                K = self.K; logit = o[..., :K]; mu = o[..., K:K + K * LAT].reshape(-1, K, LAT)
                ls = o[..., K + K * LAT:].reshape(-1, K, LAT).clamp(-5, 2) - 1.5
                if sample:
                    k = torch.distributions.Categorical(logits=logit).sample()
                    idx = k.view(-1, 1, 1).expand(-1, 1, LAT)
                    m_ = mu.gather(1, idx).squeeze(1); s_ = ls.gather(1, idx).squeeze(1).exp()
                    z = z + m_ + 0.5 * s_ * torch.randn_like(m_)
                else:
                    idx = logit.argmax(-1).view(-1, 1, 1).expand(-1, 1, LAT); z = z + mu.gather(1, idx).squeeze(1)
            out.append(z); cc, h = self.ctx(z.unsqueeze(1), h); ct = cc[:, 0]
        return torch.stack(out, 1)
    def gen_from_cond(self, cond, z0, n, sample=False):
        """text->audio: no audio prompt; the caption state is the GRU's h0, z0 a learned start latent"""
        return self.rollout(z0.expand(cond.shape[0], 1, LAT), n, sample=sample, cond=cond)
