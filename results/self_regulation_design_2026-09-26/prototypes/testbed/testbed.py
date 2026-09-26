"""Shared focus / credibility / forgetting testbed (mm3).

Written by designer d2 (first to finish). Reuse UNCHANGED; add design code in your own dir.

What it is
----------
A byte-level synthetic corpus of 7 AREAS, every one a generator with a KNOWN per-byte optimum
(the generator's own probability of each byte it emits, "oracle bits/byte"), all tables drawn from
`random.Random(f"{seed}:...")` so the corpus VARIES WITH THE SEED (D-A13 closed for the testbed).
All areas share one 16-letter alphabet a..p (provenance is NOT given away by the byte set).

  0 hard   order-2 Markov, each context row = 4 symbols drawn uniformly (dups allowed)   ~1.8 bits/byte
  1 easy   order-2 Markov, one favoured symbol p=0.9, else uniform over 16               ~0.87 bits/byte
  2 noise  i.i.d. uniform over 16 letters: UNLEARNABLE beyond the unigram (noisy TV)       4.0 bits/byte
  3 cred   filler (order-2, row 3) + fact records "@EEE=V;" stating the TRUE value of all 96 entities
  4 false  filler (order-2, row 2 = MORE FLUENT than cred) + records for all 96 entities; on a designated
           50% of entities (half of W, half of Q) it CONSISTENTLY states a wrong value (fluent liar)
  5 corrob filler (order-2, row 3) + records stating the TRUE value of the W entities only (48)
  6 late   order-2 Markov row 4, same alphabet, INDEPENDENT (conflicting) table; arrives in the last phase
           while hard/easy vanish -> forgetting pressure on hard (goal B)

Entities: 96 distinct 3-letter names; W = first 48 (corroborated by corrob), Q = last 48 (only cred vs
false). Classes for the fact test: Wc (W, false flips), Wa (W, agreed), Qc (Q, false flips), Qa.

Stream: 4 phases of equal byte span. P0..P2 live = hard,easy,noise,cred,false,corrob; P3 live =
late,noise,cred,false,corrob. BASELINE draw = the tree's DATA_DRAW='planned': each phase's span split
EVENLY across its live areas (remainder to the first), area chosen uniformly among live areas with budget
left, segment length randint(700,1800) truncated to budget. The draw is ONLINE (segment by segment), so a
focus policy can plug in via `policy` (see PlannedPolicy) -- a runtime draw here needs no S0b act.

Model: 1-layer GRU byte LM, width 128, windows of CTX=128 (+1) bytes cut contiguously from the stream,
each window independent (no carried state; the tree's LM also sees only its window), BATCH windows per
optimizer step (16; the tree runs 1 -- stated deviation for CPU speed), AdamW 3e-3, warm-up 30 steps,
cosine to 0.1x, clip 1.0. One epoch; every window is scored before its update (prequential).
Optional source channel: a per-token source-id embedding (0 = no tag) added to the byte embedding.

Readings (eval()):
  heldout[area][cond]  bits/byte on 16 held-out windows per area (separate rng stream), cond 'null' or
                       'tag' (true source id); oracle[area] the generator optimum on the same bytes.
  facts[cond][class]   for each entity: prompt = 32 bytes of a source's filler + "@EEE=", read the
                       distribution over the 8 value digits. acc_true (argmax = true value), acc_false
                       (argmax = the liar's value), share_true = p_T/(p_T+p_F) on conflicted classes.
                       conds: null_c/null_f/null_r (no tag, cred/false/corrob-STYLE prefix) and
                       tag_c/tag_f/tag_r (tag + matching prefix).
Run `python testbed.py --selftest` (from this dir) to print the corpus facts and oracle entropies.
"""
import math, random, json, time, sys, os
import torch, torch.nn as nn, torch.nn.functional as F

torch.set_num_threads(1)
ALPHA = b"abcdefghijklmnop"
VALS = b"01234567"
AREAS = ["hard", "easy", "noise", "cred", "false", "corrob", "late"]
A = {n: i for i, n in enumerate(AREAS)}
PHASES = [["hard", "easy", "noise", "cred", "false", "corrob"]] * 3 + [["late", "noise", "cred", "false", "corrob"]]
N_ENT, N_W = 96, 48
REC_P = 0.08          # per-filler-position probability of a fact record
CTX, BATCH = 128, 16
SEG_MIN, SEG_MAX = 700, 1800
L2 = math.log(2)


def _rng(seed, tag):
    return random.Random(f"{seed}:{tag}")


class Markov2:
    """order-2 Markov over ALPHA. kind 'row': each context row = `row` symbols uniform (dups allowed).
    kind 'fav': favoured symbol with prob `pfav`, else uniform."""

    def __init__(self, rng, kind="row", row=3, pfav=0.9):
        self.P = {}
        n = len(ALPHA)
        for a in range(n):
            for b in range(n):
                p = [0.0] * n
                if kind == "row":
                    for _ in range(row):
                        p[rng.randrange(n)] += 1.0 / row
                else:
                    f = rng.randrange(n)
                    for k in range(n):
                        p[k] = (1 - pfav) / n + (pfav if k == f else 0.0)
                self.P[(a, b)] = p

    def step(self, rng, ctx):
        p = self.P[ctx]
        r, acc = rng.random(), 0.0
        for k, pk in enumerate(p):
            acc += pk
            if r < acc:
                return k, pk
        return len(p) - 1, p[-1]


class World:
    def __init__(self, seed):
        r = _rng(seed, "world")
        names = set()
        while len(names) < N_ENT:
            names.add(bytes(r.choice(ALPHA) for _ in range(3)))
        self.names = sorted(sorted(names), key=lambda s: r.random())  # sorted first: set order depends on PYTHONHASHSEED
        self.W = self.names[:N_W]
        self.Q = self.names[N_W:]
        self.true = {e: r.randrange(8) for e in self.names}
        flip = set(r.sample(self.W, N_W // 2)) | set(r.sample(self.Q, (N_ENT - N_W) // 2))
        self.flipped = flip
        self.lie = {e: ((self.true[e] + 1 + r.randrange(7)) % 8 if e in flip else self.true[e]) for e in self.names}

    def cls(self, e):
        return ("W" if e in self.W else "Q") + ("c" if e in self.flipped else "a")


class AreaGen:
    """Infinite generator for one area; returns (bytes, oracle_bits list)."""

    def __init__(self, name, seed, world, stream="train"):
        self.name = name
        self.rng = _rng(seed, f"gen:{name}:{stream}")
        tr = _rng(seed, f"table:{name}")
        self.world = world
        self.ents, self.val = None, None
        if name == "hard" or name == "late":
            self.m = Markov2(tr, "row", 4)
        elif name == "easy":
            self.m = Markov2(tr, "fav", pfav=0.9)
        elif name == "noise":
            self.m = None
        elif name in ("cred", "false", "corrob"):
            self.m = Markov2(tr, "row", 2 if name == "false" else 3)
            self.ents = world.W if name == "corrob" else world.names
            self.val = world.lie if name == "false" else world.true
            # entity char probabilities for the oracle
            self.prefix = {}
            for e in self.ents:
                for k in range(4):
                    self.prefix[e[:k]] = self.prefix.get(e[:k], 0) + 1
        self.ctx = (self.rng.randrange(16), self.rng.randrange(16))

    def filler_prefix(self, n):
        """n bytes of pure filler (no records) for style prompts; own rng."""
        r = random.Random(self.rng.random())
        ctx, out = (r.randrange(16), r.randrange(16)), []
        for _ in range(n):
            k, _p = self.m.step(r, ctx)
            out.append(ALPHA[k]); ctx = (ctx[1], k)
        return bytes(out)

    def gen(self, n):
        out, bits = bytearray(), []
        r = self.rng
        while len(out) < n:
            if self.m is None:
                out.append(ALPHA[r.randrange(16)]); bits.append(4.0); continue
            if self.ents is not None and r.random() < REC_P:
                e = self.ents[r.randrange(len(self.ents))]
                out += b"@" + e + b"=" + bytes([VALS[self.val[e]]]) + b";"
                b = [-math.log2(REC_P)]
                for k in range(3):
                    b.append(-math.log2(self.prefix[e[:k + 1]] / self.prefix[e[:k]]))
                bits += b + [0.0, 0.0, 0.0]
                continue
            k, pk = self.m.step(r, self.ctx)
            q = (1 - REC_P) if self.ents is not None else 1.0
            out.append(ALPHA[k]); bits.append(-math.log2(pk * q)); self.ctx = (self.ctx[1], k)
        return bytes(out[:n]), bits[:n]


class PlannedPolicy:
    """The tree's DATA_DRAW='planned': even split of each phase's bytes across live areas; choose
    uniformly among live areas with budget left. Focus policies subclass this: override `budgets`
    (called at each phase entry) and/or `choose` (called per segment); `note` receives per-window
    prequential losses (area id per token, nats per token) after every step."""

    def budgets(self, phase, live, span):
        share = span // len(live)
        b = {a: share for a in live}
        b[live[0]] += span - share * len(live)
        return b

    def choose(self, rng, live, left):
        cand = [a for a in live if left[a] > 0]
        return rng.choice(cand)

    def note(self, area_ids, nats, weights=None):
        pass

    def state(self):
        return {}


class Stream:
    """Online segment-by-segment draw into a byte buffer with per-byte area labels and source-tag ids."""

    def __init__(self, seed, total, policy, world, tag_drop=0.0, tag_mode="off"):
        self.seed, self.total, self.policy = seed, total, policy
        self.rng = _rng(seed, "draw")
        self.trng = _rng(seed, "tagdrop")
        self.gens = {n: AreaGen(n, seed, world) for n in AREAS}
        self.buf, self.lab, self.tag = bytearray(), [], []
        self.phase, self.drawn = -1, {n: 0 for n in AREAS}
        self.spans = [(round(k * total / 4), round((k + 1) * total / 4)) for k in range(4)]
        self.tag_drop, self.tag_mode = tag_drop, tag_mode
        self.n_segments = 0

    def _enter(self, k):
        self.phase = k
        s0, s1 = self.spans[k]
        self.left = dict(self.policy.budgets(k, PHASES[k], s1 - s0))

    def fill(self, need):
        while len(self.buf) < need and len(self.buf) < self.total:
            pos = len(self.buf)
            k = max(i for i in range(4) if self.spans[i][0] <= pos)
            if k != self.phase:
                self._enter(k)
            live = PHASES[k]
            if sum(self.left[a] for a in live) <= 0:
                self.left[live[0]] += self.spans[k][1] - pos
            a = self.policy.choose(self.rng, live, self.left)
            n = min(self.rng.randint(SEG_MIN, SEG_MAX), self.left[a], self.spans[k][1] - pos)
            n = max(n, 1)
            b, _ = self.gens[a].gen(n)
            self.buf += b
            self.lab += [A[a]] * n
            t = 0 if (self.tag_mode == "off" or self.trng.random() < self.tag_drop) else A[a] + 1
            self.tag += [t] * n
            self.left[a] -= n
            self.drawn[a] += n
            self.n_segments += 1


class LM(nn.Module):
    def __init__(self, d=128, n_src=len(AREAS) + 1):
        super().__init__()
        self.emb = nn.Embedding(256, d)
        self.src = nn.Embedding(n_src, d)
        nn.init.zeros_(self.src.weight)
        self.gru = nn.GRU(d, d, batch_first=True)
        self.out = nn.Linear(d, 256)

    def forward(self, x, s=None):
        h = self.emb(x)
        if s is not None:
            h = h + self.src(s)
        return self.out(self.gru(h)[0])


class Heldout:
    def __init__(self, seed, world, n_win=16):
        self.win, self.orc = {}, {}
        for n in AREAS:
            g = AreaGen(n, seed, world, stream="heldout")
            b, bits = g.gen(n_win * (CTX + 1))
            self.win[n] = torch.tensor(list(b), dtype=torch.long).view(n_win, CTX + 1)
            self.orc[n] = sum(torch.tensor(bits).view(n_win, CTX + 1)[:, 1:].reshape(-1).tolist()) / (n_win * CTX)
        # fact prompts
        self.prompts = {}
        pre = {s: AreaGen(s, seed, world, stream="prompt") for s in ("cred", "false", "corrob")}
        r = _rng(seed, "prompts")
        for e in world.names:
            for s in ("cred", "false", "corrob"):
                self.prompts[(e, s)] = pre[s].filler_prefix(32) + b"@" + e + b"="


@torch.no_grad()
def evaluate(model, ho, world, tags_on):
    model.eval()
    res = {"heldout": {}, "oracle": dict(ho.orc), "facts": {}}
    for n in AREAS:
        x = ho.win[n]
        conds = {"null": torch.zeros_like(x[:, :-1])}
        if tags_on:
            conds["tag"] = torch.full_like(x[:, :-1], A[n] + 1)
        res["heldout"][n] = {}
        for c, s in conds.items():
            lo = model(x[:, :-1], s)
            res["heldout"][n][c] = F.cross_entropy(lo.reshape(-1, 256), x[:, 1:].reshape(-1)).item() / L2
    vidx = torch.tensor(list(VALS))
    conds = [("null_c", "cred", 0), ("null_f", "false", 0), ("null_r", "corrob", 0)]
    if tags_on:
        conds += [("tag_c", "cred", A["cred"] + 1), ("tag_f", "false", A["false"] + 1), ("tag_r", "corrob", A["corrob"] + 1)]
    probs = {}
    for cname, style, tid in conds:
        X = torch.tensor([list(ho.prompts[(e, style)]) for e in world.names])
        S = torch.full_like(X, tid)
        p = torch.softmax(model(X, S)[:, -1, :], -1)[:, vidx]
        probs[cname] = p
        agg = {}
        for i, e in enumerate(world.names):
            c = world.cls(e)
            d = agg.setdefault(c, {"acc_true": 0, "acc_false": 0, "share_true": 0.0, "n": 0})
            pt, pf = p[i, world.true[e]].item(), p[i, world.lie[e]].item()
            am = int(p[i].argmax())
            d["acc_true"] += am == world.true[e]
            d["acc_false"] += am == world.lie[e]
            d["share_true"] += pt / (pt + pf) if c.endswith("c") else pt / p[i].sum().item()
            d["n"] += 1
        for c, d in agg.items():
            for k in ("acc_true", "acc_false", "share_true"):
                d[k] = d[k] / d["n"]
        res["facts"][cname] = agg
    model.train()
    return res, probs


def train(seed, total, policy=None, tag_mode="off", tag_drop=0.0, weight_fn=None, n_evals=8,
          lr=3e-3, log=None, extra=None):
    """weight_fn(model, x, s, per_token_nats, step) -> (B,CTX) weights with mean 1, or None.
    Returns dict with evals (list), per-area prequential books, draw accounting."""
    torch.manual_seed(seed)
    world = World(seed)
    policy = policy or PlannedPolicy()
    st = Stream(seed, total, policy, world, tag_drop, tag_mode)
    ho = Heldout(seed, world)
    model = LM()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)
    n_win = (total - 1) // CTX
    n_steps = n_win // BATCH
    warm = 30
    sched = lambda t: min(1.0, (t + 1) / warm) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1.0, t / n_steps))))
    tags_on = tag_mode != "off"
    evals, books = [], {n: {"tok": 0, "nats": 0.0, "w": 0.0} for n in AREAS}
    phase_books = [{n: {"tok": 0, "nats": 0.0, "w": 0.0} for n in AREAS} for _ in range(4)]
    eval_at = sorted(set([round(n_steps * k / n_evals) for k in range(1, n_evals + 1)] +
                         [round(n_steps * k / 4) for k in (1, 2, 3)]))
    t0 = time.time()
    for step in range(n_steps):
        lo_b = step * BATCH * CTX
        st.fill(lo_b + BATCH * CTX + 1)
        xs = torch.tensor(list(st.buf[lo_b:lo_b + BATCH * CTX + 1]), dtype=torch.long)
        idx = torch.arange(BATCH)[:, None] * CTX + torch.arange(CTX + 1)[None, :]
        x = xs[idx]
        lab = torch.tensor(st.lab[lo_b:lo_b + BATCH * CTX + 1])[idx][:, 1:]
        s = torch.tensor(st.tag[lo_b:lo_b + BATCH * CTX + 1])[idx][:, :-1] if tags_on else None
        for g in opt.param_groups:
            g["lr"] = lr * sched(step)
        logits = model(x[:, :-1], s)
        nats = F.cross_entropy(logits.reshape(-1, 256), x[:, 1:].reshape(-1), reduction="none").view(BATCH, CTX)
        w = weight_fn(model, x, s, nats.detach(), step) if weight_fn else None
        loss = (nats * w).mean() if w is not None else nats.mean()
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if extra and "after_step" in extra:
            extra["after_step"](model, step)
        ww = w if w is not None else torch.ones_like(nats)
        policy.note(lab, nats.detach(), ww.detach())
        ph = min(3, max(i for i in range(4) if st.spans[i][0] <= lo_b))
        for a in lab.unique().tolist():
            m = lab == a
            for bk in (books, phase_books[ph]):
                bk[AREAS[a]]["tok"] += int(m.sum()); bk[AREAS[a]]["nats"] += float(nats.detach()[m].sum())
                bk[AREAS[a]]["w"] += float(ww[m].sum())
        if step + 1 in eval_at:
            r, _ = evaluate(model, ho, world, tags_on)
            r["step"] = step + 1; r["frac"] = (step + 1) / n_steps; r["wall"] = time.time() - t0
            evals.append(r)
            if log:
                print(f"[{seed}] step {step+1}/{n_steps} {time.time()-t0:.0f}s " +
                      " ".join(f"{n}:{r['heldout'][n]['null']:.2f}" for n in AREAS), file=log, flush=True)
    _, probs = evaluate(model, ho, world, tags_on)
    return {"evals": evals, "books": books, "phase_books": phase_books, "drawn": st.drawn,
            "n_steps": n_steps, "segments": st.n_segments, "wall": time.time() - t0,
            "policy_state": policy.state(), "world": world, "probs": probs, "model": model}


def summarize(res):
    """Standard readings from a train() result."""
    ev = res["evals"]
    end = ev[-1]
    p2 = min(ev, key=lambda r: abs(r["frac"] - 0.75))
    out = {"gap_end": {n: end["heldout"][n]["null"] - end["oracle"][n] for n in AREAS},
           "bpb_end_null": {n: end["heldout"][n]["null"] for n in AREAS},
           "oracle": end["oracle"],
           "forget_hard": end["heldout"]["hard"]["null"] - p2["heldout"]["hard"]["null"],
           "forget_easy": end["heldout"]["easy"]["null"] - p2["heldout"]["easy"]["null"],
           "hard_at_p2end": p2["heldout"]["hard"]["null"],
           "facts_end": end["facts"],
           "drawn_share": {n: res["drawn"][n] / sum(res["drawn"].values()) for n in AREAS}}
    if "tag" in end["heldout"]["hard"]:
        out["bpb_end_tag"] = {n: end["heldout"][n]["tag"] for n in AREAS}
    W = sum(b["w"] for b in res["books"].values())
    out["grad_weight_share"] = {n: res["books"][n]["w"] / W for n in AREAS}
    return out


if __name__ == "__main__" and "--selftest" in sys.argv:
    for seed in (0, 1):
        w = World(seed)
        ho = Heldout(seed, w)
        print("seed", seed, "oracle bits/byte:", {n: round(v, 3) for n, v in ho.orc.items()})
        print("  first entities", w.names[:4], "true", [w.true[e] for e in w.names[:4]],
              "flipped W", sum(e in w.flipped for e in w.W), "flipped Q", sum(e in w.flipped for e in w.Q))
        g = AreaGen("cred", seed, w); print("  cred sample", g.gen(80)[0])
        g = AreaGen("false", seed, w); print("  false sample", g.gen(80)[0])
