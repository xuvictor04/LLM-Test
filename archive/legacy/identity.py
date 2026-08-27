"""
Procedural Identity
===================
Section 20.

Every node -- a memory entry, a module, an expert, a script -- gets a FIXED,
procedurally generated identity: a deterministic short id string and a fixed
identity vector derived from a seed (its name / type). Because it is procedural
(hashed, not learned) it never drifts with training -- a stable anchor.

The identity vector is included as a FIXED component of a node's output
(node_output = [learned_features ; identity]); this sharpens search (same-node
items cluster on the identity component) and lets the system recognize a module /
memory by matching its identity, independent of changing learned features.

Dependency-free core (hashlib + numpy); a small torch helper attaches an identity
to a module as a non-trained buffer.
"""

from __future__ import annotations

import hashlib

import numpy as np


def identity_id(seed: str, length: int = 12) -> str:
    """Deterministic short id string from a seed."""
    return hashlib.sha256(seed.encode()).hexdigest()[:length]


_CONS = "bcdfghjklmnprstvz"
_VOWS = "aeiou"


def encode_name(content: str, kind: str | None = None, syllables: int = 3) -> str:
    """Self-name a thing (an agent, a file, a script) by ENCODING its content into a
    deterministic, pronounceable, filesystem-safe handle. Same content -> same name
    (content-addressed), so names are stable and collision-resistant without a counter.
    e.g. encode_name('summarize quarterly report', 'agent') -> 'agent-tovaru-9c2f'."""
    h = hashlib.sha256((str(kind) + "::" + content).encode()).digest()
    name = ""
    for i in range(syllables):
        name += _CONS[h[2 * i] % len(_CONS)] + _VOWS[h[2 * i + 1] % len(_VOWS)]
    suffix = hashlib.sha256(content.encode()).hexdigest()[:4]   # disambiguating tail
    base = f"{name}-{suffix}"
    return f"{kind}-{base}" if kind else base


def encode_code(content: str, length: int = 10) -> str:
    """A shorter base32-style code name (no vowels-avoidance), for when a terse,
    unambiguous handle is preferred over a pronounceable one."""
    import base64
    digest = hashlib.sha256(content.encode()).digest()
    return base64.b32encode(digest).decode().rstrip("=").lower()[:length]


def identity_vector(seed: str, dim: int) -> np.ndarray:
    """Deterministic fixed unit vector from a seed (hash-seeded RNG)."""
    digest = hashlib.sha256(("idvec::" + seed).encode()).digest()
    s = int.from_bytes(digest[:8], "big")
    rng = np.random.default_rng(s)
    v = rng.standard_normal(dim).astype(np.float32)
    return v / (float(np.linalg.norm(v)) + 1e-8)


def make_identity(seed: str, dim: int) -> dict:
    return {"id": identity_id(seed), "seed": seed, "vector": identity_vector(seed, dim)}


def concat_identity(features: np.ndarray, id_vector: np.ndarray) -> np.ndarray:
    """Append the fixed identity vector as a fixed node output."""
    idv = np.broadcast_to(id_vector, features.shape[:-1] + (id_vector.shape[-1],))
    return np.concatenate([features, idv], axis=-1)


def recognize(query_id_vector: np.ndarray, registry: dict, top_k: int = 1):
    """Match a query identity vector against a {name: identity_vector} registry by
    cosine similarity -> internal system recognition."""
    names = list(registry.keys())
    M = np.stack([registry[n] for n in names], 0)
    q = query_id_vector / (np.linalg.norm(query_id_vector) + 1e-8)
    sims = M @ q
    order = np.argsort(-sims)[:top_k]
    return [(names[i], float(sims[i])) for i in order]


def attach_identity(module, seed: str, dim: int) -> dict:
    """Give a torch module a fixed identity: a non-trained buffer `identity_vec`
    and an `identity_id` string. Concatenate `identity_vec` to the module's output
    for search / recognition."""
    import torch

    ident = make_identity(seed, dim)
    module.identity_id = ident["id"]
    if hasattr(module, "identity_vec"):
        module.identity_vec = torch.tensor(ident["vector"])
    else:
        module.register_buffer("identity_vec", torch.tensor(ident["vector"]))
    return ident


ID_DIM = 64   # standard identity-vector width for module/node identities


class IdentityMixin:
    """Mixin giving any nn.Module a FIXED procedural identity. The identity vector is
    a registered buffer, so optimizers/backprop never change it — fixed and unchanged
    through training — yet it is still a normal tensor that flows through the embedder
    / downstream processing for proper management and understanding. `with_identity`
    appends it as a fixed component of the module's output (the fixed node output)."""

    def init_identity(self, seed: str, dim: int = ID_DIM) -> None:
        import torch

        ident = make_identity(seed, dim)
        self.identity_id = ident["id"]
        self.register_buffer("identity_vec", torch.tensor(ident["vector"]))

    def with_identity(self, features):
        idv = self.identity_vec.to(features.dtype)
        idv = idv.expand(*features.shape[:-1], idv.shape[-1])
        import torch

        return torch.cat([features, idv], dim=-1)


if __name__ == "__main__":
    dim = 32

    # deterministic: same seed -> identical id and vector across runs/instances
    a = make_identity("expert::summarize", dim)
    b = make_identity("expert::summarize", dim)
    c = make_identity("memory::episode_0042", dim)
    print("same seed -> same id:", a["id"] == b["id"], a["id"])
    print("same seed -> same vector:", bool(np.allclose(a["vector"], b["vector"])))
    print("different seed -> different id:", a["id"] != c["id"])
    print("identity vectors are unit norm:", round(float(np.linalg.norm(a["vector"])), 4))

    # fixed node output: learned features with identity appended
    feats = np.random.default_rng(0).standard_normal((4, dim))
    out = concat_identity(feats, a["vector"])
    print("node output [features | identity]:", out.shape, "(want (4,64))")

    # internal recognition: match a node's identity back to its name
    registry = {"summarize": a["vector"], "episode_0042": c["vector"]}
    print("recognized:", recognize(a["vector"], registry))

    # self-naming by encoding content (for agents / files / scripts)
    print("\nself-named agent:", encode_name("summarize quarterly report", "agent"))
    print("same content -> same name:",
          encode_name("summarize quarterly report", "agent") == encode_name("summarize quarterly report", "agent"))
    print("different content -> different name:",
          encode_name("translate to french", "agent") != encode_name("summarize quarterly report", "agent"))
    print("terse code name:", encode_code("a generated file's contents"))
