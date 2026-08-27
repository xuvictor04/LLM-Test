"""Built-in capabilities = experts whose forward is CODE (a deterministic endpoint), not a neural net.

Claim under test: a neural expert -- even one trained directly on the task -- cannot match the exact
correctness of a 3-line code endpoint. If true, code-experts earn their place for deterministic
sub-tasks (arithmetic, lookup, parsing), routed to by a trigger gate, with the result fed back as
tokens. We prove it on exact arithmetic.
"""
import re, math, random
import torch, torch.nn as nn, torch.nn.functional as F
torch.manual_seed(0); random.seed(0); torch.set_num_threads(1)


# ---------------- the capability layer ----------------
class CodeExpert:
    """A registered capability: a trigger (when does this apply?) + a run_fn (deterministic code)."""
    def __init__(self, name, trigger, run):
        self.name, self.trigger, self.run = name, trigger, run
    def applies(self, ctx): return self.trigger(ctx)
    def __call__(self, ctx): return self.run(ctx)

def _arith_run(ctx):
    m = re.search(r"(\d+)\s*([*+\-])\s*(\d+)\s*=", ctx)
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    return str({"*": a * b, "+": a + b, "-": a - b}[op])

REGISTRY = [
    CodeExpert("arithmetic", lambda c: re.search(r"\d+\s*[*+\-]\s*\d+\s*=", c) is not None, _arith_run),
    CodeExpert("string_len", lambda c: c.strip().startswith("len("), lambda c: str(len(re.search(r"len\((.*?)\)", c).group(1)))),
]
def route(ctx):
    for e in REGISTRY:
        if e.applies(ctx): return e
    return None   # -> fall back to the neural fabric


# ---------------- a neural expert given its best shot at the same task ----------------
class Block(nn.Module):
    def __init__(s, d, h):
        super().__init__(); s.h = h; s.ln1 = nn.LayerNorm(d); s.qkv = nn.Linear(d, 3 * d); s.proj = nn.Linear(d, d)
        s.ln2 = nn.LayerNorm(d); s.mlp = nn.Sequential(nn.Linear(d, 4 * d), nn.GELU(), nn.Linear(4 * d, d))
    def forward(s, x):
        B, T, D = x.shape; y = s.ln1(x); q = s.qkv(y).reshape(B, T, 3, s.h, D // s.h).permute(2, 0, 3, 1, 4)
        a = F.scaled_dot_product_attention(q[0], q[1], q[2], is_causal=True)
        x = x + s.proj(a.transpose(1, 2).reshape(B, T, D)); return x + s.mlp(s.ln2(x))
class ByteLM(nn.Module):
    def __init__(s, d=64, nl=2, h=4):
        super().__init__(); s.emb = nn.Embedding(256, d); s.pos = nn.Embedding(64, d)
        s.blocks = nn.ModuleList([Block(d, h) for _ in range(nl)]); s.lnf = nn.LayerNorm(d); s.head = nn.Linear(d, 256)
    def forward(s, x):
        h = s.emb(x) + s.pos(torch.arange(x.shape[1]))[None]
        for b in s.blocks: h = b(h)
        return s.head(s.lnf(h))

def gen_problem():
    a, b = random.randint(10, 99), random.randint(10, 99)
    return f"{a}*{b}={a*b}\n"
def encode(s): return [ord(c) for c in s]

train = [gen_problem() for _ in range(4000)]
held = list({gen_problem() for _ in range(400)})[:200]
blob = "".join(train); ids = torch.tensor(encode(blob))
net = ByteLM(); opt = torch.optim.Adam(net.parameters(), lr=2e-3); L = 16
for _ in range(600):
    ix = torch.randint(0, len(ids) - L - 1, (64,))
    x = torch.stack([ids[i:i + L] for i in ix]); y = torch.stack([ids[i + 1:i + L + 1] for i in ix])
    loss = F.cross_entropy(net(x).reshape(-1, 256), y.reshape(-1)); opt.zero_grad(); loss.backward(); opt.step()
net.eval()

@torch.no_grad()
def neural_answer(prompt):
    ids = encode(prompt)
    for _ in range(6):
        x = torch.tensor(ids[-16:])[None]; nxt = int(net(x)[0, -1].argmax())
        if nxt == ord("\n"): break
        ids.append(nxt)
    return "".join(chr(c) for c in ids[len(prompt):])

# ---------------- evaluate exact correctness ----------------
neural_ok = code_ok = 0
for p in held:
    prompt, truth = p.split("=")[0] + "=", p.split("=")[1].strip()
    if neural_answer(prompt) == truth: neural_ok += 1
    e = route(prompt)
    if e and e(prompt) == truth: code_ok += 1

print(f"held arithmetic problems: {len(held)}  (model trained 600 steps directly on this task)\n")
print(f"  neural expert  exact-match: {neural_ok}/{len(held)}  = {100*neural_ok/len(held):.0f}%")
print(f"  code endpoint  exact-match: {code_ok}/{len(held)}  = {100*code_ok/len(held):.0f}%")
print("\nrouting gate on mixed inputs:")
for ctx in ["73*48=", "len(hello)", "the cat sat on the", "12+9="]:
    e = route(ctx)
    print(f"  {ctx!r:24} -> {('code:'+e.name+' = '+e(ctx)) if e else 'neural fabric'}")
