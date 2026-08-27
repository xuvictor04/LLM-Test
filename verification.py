"""Verification (renamed from B / "wrongness"): verify a memory association by RECONSTRUCTION, not by surprise.

An entry is (key, token): key = the model's encoding of the context, token = the stored next-token. A GENUINE
association lies on the manifold of associations the model actually produced; a CORRUPT one (a context from one process
paired with a token from another) is OFF that manifold. The Reconstructor is a small autoencoder over (key, token):
trained only on the genuine associations it sees, it reconstructs them well and off-manifold (corrupt) ones badly.

Reconstruction error is therefore a verification signal DECOUPLED from surprise (= 1 - p_model(token|context)): a
novel-but-genuine association has HIGH surprise yet LOW reconstruction error, while a corrupt one has HIGH reconstruction
error. Surprise alone conflated those two (why the old B sat at ~1% precision); the two signals together are the
surprise x reconstruction handling in archive/handoff/design-directions/learning-signal-classification-...

Standalone (torch only): `python3 verification.py` runs a CPU probe that checks the core claim on structured-synthetic
data (a mechanism sanity check -- the REAL validation is the GPU cl_bench corruption test with model-produced keys).
"""
import torch, torch.nn as nn, torch.nn.functional as F


class Reconstructor(nn.Module):
    """Reverse embedder for Verification. CROSS-reconstruction: from the context KEY, reconstruct the EXPECTED
    token-code, and measure how far the STORED token's code is from it. `error(key, tok)` -> per-entry error.

    Why cross- and not joint-autoencoding: a joint AE over [key;token] reconstructs the (dominant) key well regardless
    of the token, so a mispaired token barely moves the error (measured: weak separation). Reconstructing the token FROM
    the key puts the whole error on the association itself. Decoupled from surprise because it works in EMBEDDING space:
    a novel-but-genuine token sits near the key's expected code (LOW error) even when its probability is low (HIGH
    surprise); a corrupt token's code is far (HIGH error)."""
    def __init__(self, key_dim, vocab, tok_dim=32, hid=64):
        super().__init__()
        # FIXED (non-learned) token codes: a stable target space so "reconstruct the token" can't be gamed by
        # collapsing a learned token embedding toward a constant.
        self.register_buffer("tcode", F.normalize(torch.randn(vocab, tok_dim), dim=-1))
        self.net = nn.Sequential(nn.Linear(key_dim, hid), nn.GELU(),
                                 nn.Linear(hid, hid), nn.GELU(), nn.Linear(hid, tok_dim))

    def error(self, key, tok):
        pred = self.net(key)                                    # the token-code the key EXPECTS
        tgt = self.tcode[tok]                                   # the token-code actually stored
        return F.mse_loss(pred, tgt, reduction="none").mean(-1)  # (N,) per-entry reconstruction error

    def forward(self, key, tok):
        return self.error(key, tok)


def recon_loss(recon, keys, toks):
    """Training loss: reconstruct GENUINE (key, token) pairs. keys are detached (the AE learns the model's manifold,
    it does not shape the model's representation)."""
    return recon.error(keys.detach(), toks).mean()


def verify(mem, recon, fit_steps=3000, lr=1e-3, bs=512):
    """Compute reconstruction error for every active memory entry and store it as the Verification signal (mem.set_recon).

    KEY LESSON (product-loop failure, 2026-07-21): training the Reconstructor JOINTLY during the loop fails -- the online
    tokenizer re-tokenizes the stream and keys get re-keyed, so the genuine-association manifold is a MOVING TARGET and the
    signal comes out as noise (0.3% precision). So we FIT the Reconstructor HERE, on the FINAL, settled store (its keys no
    longer move), which reproduces the standalone regime where reconstruction cleanly separates genuine from corrupt.
    The injected/wrong entries are a tiny fraction, so fitting on all active entries doesn't corrupt the manifold."""
    ii = mem.active.nonzero(as_tuple=True)[0]
    if ii.numel() == 0:
        return
    if fit_steps > 0:
        opt = torch.optim.Adam(recon.parameters(), lr=lr); recon.train()
        for _ in range(fit_steps):
            b = ii[torch.randint(0, ii.numel(), (min(bs, ii.numel()),), device=ii.device)]
            opt.zero_grad(); recon.error(mem.keys[b].detach(), mem.tok[b]).mean().backward(); opt.step()
        recon.eval()
    with torch.no_grad():
        er = [recon.error(mem.keys[ii[s:s + 8192]], mem.tok[ii[s:s + 8192]]) for s in range(0, ii.numel(), 8192)]
    mem.set_recon(ii, torch.cat(er))


def _probe(seed=0):
    """CPU sanity check of the core claim: on a structured association manifold, does reconstruction error separate
    genuine from corrupt (mispaired) associations? Reports separation as an AUC (1.0 = perfect, 0.5 = chance).
    NOTE: idealized synthetic structure -- proves the MECHANISM can separate when structure exists, not that it works
    on real model keys (that is the GPU cl_bench test)."""
    torch.manual_seed(seed)
    D, Vv, N, L = 64, 256, 4000, 8
    A = torch.randn(L, D); B = torch.randn(L, Vv)              # a low-rank latent -> (key, token) manifold
    def gen(n):
        z = torch.randn(n, L)
        key = F.normalize(z @ A, dim=-1)
        tok = (z @ B).argmax(-1)                               # token correlated with the SAME latent as the key
        return key, tok
    kg, tg = gen(N)
    recon = Reconstructor(D, Vv)
    opt = torch.optim.Adam(recon.parameters(), lr=1e-3)
    for _ in range(400):
        opt.zero_grad(); recon_loss(recon, kg, tg).backward(); opt.step()
    kh, th = gen(1000)
    tc = th[torch.randperm(1000)]                             # corrupt: same keys, shuffled (mispaired) tokens
    with torch.no_grad():
        eg = recon.error(kh, th); ec = recon.error(kh, tc)
    auc = (eg.unsqueeze(1) < ec.unsqueeze(0)).float().mean().item()
    print(f"[verify-probe] recon error: genuine {eg.mean():.4f} vs corrupt {ec.mean():.4f} | separation AUC {auc:.3f} "
          f"({'MECHANISM WORKS on structured data' if auc > 0.8 else 'weak separation'})")
    return auc


if __name__ == "__main__":
    _probe()
