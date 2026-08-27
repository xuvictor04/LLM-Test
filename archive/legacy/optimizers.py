"""Optimizer options. AdamW (default) and Lion (EvoLved Sign Momentum, Chen et al. 2023).

Lion is sign-based: it keeps one momentum buffer (half AdamW's optimizer memory) and updates by the SIGN of
an interpolated momentum. It often matches/beats AdamW on LMs but wants a SMALLER learning rate (~3-10x) and a
LARGER weight decay, because the update magnitude is always ~lr (sign), not scaled by gradient size.
"""
import torch


class Lion(torch.optim.Optimizer):
    def __init__(self, params, lr=3e-4, betas=(0.9, 0.99), weight_decay=0.0):
        super().__init__(params, dict(lr=lr, betas=betas, weight_decay=weight_decay))

    @torch.no_grad()
    def step(self, closure=None):
        loss = closure() if closure is not None else None
        for group in self.param_groups:
            lr, (b1, b2), wd = group["lr"], group["betas"], group["weight_decay"]
            for p in group["params"]:
                if p.grad is None:
                    continue
                g = p.grad
                st = self.state[p]
                if "m" not in st:
                    st["m"] = torch.zeros_like(p)
                m = st["m"]
                p.mul_(1 - lr * wd)                                   # decoupled weight decay
                update = m.mul(b1).add_(g, alpha=1 - b1).sign_()      # sign of interpolated momentum
                p.add_(update, alpha=-lr)
                m.mul_(b2).add_(g, alpha=1 - b2)                      # momentum EMA (separate beta)
        return loss


def make_opt(params, cfg):
    """Build the optimizer named by cfg.OPTIM. Lion auto-scales its LR down unless LION_LR is set explicitly."""
    name = str(getattr(cfg, "OPTIM", "adamw")).lower()
    wd = cfg.WEIGHT_DECAY
    return torch.optim.AdamW(params, lr=cfg.LR, weight_decay=wd)
