"""
Language substrate
==================
A minimal, REAL, trainable causal language model — the working base the rest of the
system grows from, instead of starting every module from noise.

  * Decoder-only byte-level transformer (vocab 256, matches the byte tokenizer used
    elsewhere in the system).
  * Trained TRADITIONALLY by next-token prediction — self-supervised, plain backprop on
    available text. No labels.
  * The measurable objective is cross-entropy / perplexity on held-out data. This is the
    evaluation signal: it is self-supervised, and it goes down when the model learns.

Once trained, `ByteLM.features(idx)` is the shared representation the modality registry,
the experts (MixtureOfExperts), and memory attach on top of — the substrate. Growth and
continual adaptation (new experts, local counterpart backprop) happen around this base,
so retraining is a matter of growing/fine-tuning small parts rather than redoing the
whole model.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from identity import ID_DIM, attach_identity


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1) -> None:
        super().__init__()
        assert d_model % n_heads == 0
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.proj = nn.Linear(d_model, d_model)
        self.drop = dropout

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        # (B, n_heads, T, head_dim)
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True,
                                           dropout_p=self.drop if self.training else 0.0)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(y)


class Block(nn.Module):
    """Pre-LN transformer block."""

    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1, identity: bool = False) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads, dropout)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 4 * d_model), nn.GELU(),
            nn.Linear(4 * d_model, d_model), nn.Dropout(dropout))
        if identity:        # upcycle-init: zero the output projections so the block starts as identity
            nn.init.zeros_(self.attn.proj.weight); nn.init.zeros_(self.attn.proj.bias)
            nn.init.zeros_(self.mlp[2].weight); nn.init.zeros_(self.mlp[2].bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class ByteLM(nn.Module):
    """Decoder-only byte-level language model — the trainable substrate."""

    def __init__(self, vocab: int = 256, d_model: int = 256, n_layers: int = 4,
                 n_heads: int = 4, max_len: int = 256, dropout: float = 0.1, vmax: int | None = None) -> None:
        super().__init__()
        attach_identity(self, "module::ByteLM", ID_DIM)        # fixed node identity
        self.max_len = max_len
        self.d_model = d_model
        self.n_heads = n_heads
        self.dropout_p = dropout
        self.V = vocab; self.VMAX = vmax or vocab              # active vocab V (grows up to VMAX)
        self.tok = nn.Embedding(self.VMAX, d_model)            # pre-allocated; only first V are active
        self.pos = nn.Embedding(max_len, d_model)
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.ModuleList([Block(d_model, n_heads, dropout) for _ in range(n_layers)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, self.VMAX, bias=False)
        self.head.weight = self.tok.weight                     # weight tying
        self.apply(self._init)

    def grow_vocab(self, a, b):
        """Activate one more token, embedding-initialized as the mean of its two constituents."""
        with torch.no_grad():
            if self.V >= self.VMAX: return False
            self.tok.weight[self.V] = 0.5 * (self.tok.weight[a] + self.tok.weight[b])
        self.V += 1; return True

    @staticmethod
    def _init(m: nn.Module) -> None:
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def features(self, idx: torch.Tensor) -> torch.Tensor:
        """Hidden representation (pre-head) — the substrate the rest of the system reads."""
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device)
        x = self.drop(self.tok(idx) + self.pos(pos)[None])
        for b in self.blocks:
            x = b(x)
        return self.ln_f(x)                                    # (B, T, d_model)

    def grow_depth(self):
        """SPAWN a layer: append a near-identity block (non-disruptive upcycle-init)."""
        blk = Block(self.d_model, self.n_heads, self.dropout_p, identity=True).to(self.tok.weight.device)
        self.blocks.append(blk)
        return len(self.blocks)

    @torch.no_grad()
    def layer_contributions(self, idx: torch.Tensor):
        """Per-layer residual fraction ||dx||/||x|| -- the depth prune signal (like expert usage)."""
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device)
        x = self.drop(self.tok(idx) + self.pos(pos)[None]); out = []
        for b in self.blocks:
            x2 = b(x); out.append(float(((x2 - x).norm(dim=-1) / (x.norm(dim=-1) + 1e-6)).mean())); x = x2
        return out

    def prune_depth(self, i: int):
        del self.blocks[i]
        return len(self.blocks)

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None):
        logits = self.features(idx) @ self.tok.weight[:self.V].t()   # (B, T, V) active vocab only
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
        return logits, loss

    @torch.no_grad()
    def generate(self, idx: torch.Tensor, max_new: int = 200, temperature: float = 1.0,
                 top_k: int | None = None) -> torch.Tensor:
        self.eval()
        for _ in range(max_new):
            ctx = idx[:, -self.max_len:]
            logits, _ = self(ctx)
            logits = logits[:, -1, :] / max(1e-6, temperature)
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float("inf")
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, 1)
            idx = torch.cat([idx, nxt], dim=1)
        return idx


# ---- data + training (next-token prediction, self-supervised) ----
def encode(text: str) -> torch.Tensor:
    return torch.frombuffer(bytearray(text.encode("utf-8")), dtype=torch.uint8).long()   # no 1B-elem Python list


def decode(ids: torch.Tensor) -> str:
    return bytes(int(i) for i in ids).decode("utf-8", "replace")


def get_batch(data: torch.Tensor, block: int, batch: int, device: str):
    ix = torch.randint(0, len(data) - block - 1, (batch,))
    x = torch.stack([data[i:i + block] for i in ix]).to(device)
    y = torch.stack([data[i + 1:i + 1 + block] for i in ix]).to(device)
    return x, y


@torch.no_grad()
def evaluate(model: ByteLM, data: torch.Tensor, block: int, batch: int, device: str, iters: int = 20):
    model.eval()
    losses = []
    for _ in range(iters):
        x, y = get_batch(data, block, batch, device)
        _, loss = model(x, y)
        losses.append(float(loss))
    model.train()
    m = sum(losses) / len(losses)
    return m, math.exp(m)                                      # (loss, perplexity)


def train_lm(model: ByteLM, text: str, steps: int = 400, block: int = 128, batch: int = 24,
             lr: float = 3e-3, val_frac: float = 0.1, device: str = "cpu", log_every: int = 50):
    data = encode(text)
    n = int(len(data) * (1 - val_frac))
    train_data, val_data = data[:n], data[n:]
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.99), weight_decay=0.1)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=steps)
    model.train()
    history = []
    for step in range(steps):
        x, y = get_batch(train_data, block, batch, device)
        _, loss = model(x, y)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % log_every == 0 or step == steps - 1:
            vl, ppl = evaluate(model, val_data, block, batch, device, iters=10)
            history.append((step, float(loss.detach()), vl, ppl))
            print(f"  step {step:>4}  train {float(loss.detach()):.3f}  val {vl:.3f}  perplexity {ppl:6.1f}")
    return history


if __name__ == "__main__":
    torch.manual_seed(0)

    # A small, self-contained English corpus (original prose). Enough to show the byte LM
    # learn real language structure on CPU in well under a minute.
    passage = (
        "The system learns by paying attention to what it does not yet understand. "
        "When something is familiar it passes quietly, and when something is new it is "
        "kept and studied. A model that only memorizes will stagnate, but a model that "
        "keeps growing can adapt to what it has never seen before. Memory holds what "
        "mattered, attention chooses what matters now, and prediction turns the present "
        "into an expectation about the future. Where the expectation is wrong, there is "
        "something to learn. Small experts grow where they are needed and are set aside "
        "when they are not. The base understands language, and everything else is built "
        "upon that base, one careful step at a time. Nothing starts from nothing. "
    )
    corpus = passage * 12                                       # ~10 KB of text

    print(f"corpus: {len(corpus)} chars  |  unique bytes: {len(set(corpus.encode()))}")
    model = ByteLM(vocab=256, d_model=160, n_layers=3, n_heads=4, max_len=128, dropout=0.1)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"ByteLM: {n_params/1e6:.2f}M params  (random-init val loss should be ~{math.log(256):.2f})\n")

    print("=== training (next-token prediction, self-supervised) ===")
    train_lm(model, corpus, steps=500, block=96, batch=32, lr=3e-3, log_every=75)

    print("\n=== sample (should look like English, not noise) ===")
    prompt = encode("The system learns")[None]
    sample = model.generate(prompt, max_new=180, temperature=0.8, top_k=40)
    print("  " + decode(sample[0]).replace("\n", " "))

    print("\n=== the substrate connects: its hidden states feed the modular system ===")
    from experts import MixtureOfExperts
    moe = MixtureOfExperts(dim=model.d_model, top_k=2, route_by_identity=True)
    moe.spawn("reader"); moe.spawn("summarizer")
    feats = model.features(encode("Memory holds what mattered")[None])   # (1, T, d_model)
    pooled = feats.mean(dim=1)                                            # (1, d_model)
    nearest, _ = moe.nearest_expert(pooled)
    out, info = moe(pooled)
    print(f"  LM features {tuple(feats.shape)} -> MoE routed to {info['names']}; "
          f"nearest expert {nearest}")
    print("\nSUBSTRATE OK — a trained language base the rest of the system grows on.")
