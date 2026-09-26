"""Shared focus / credibility / forgetting testbed (mm3).

Byte-level synthetic corpus with KNOWN optima, a small GRU byte LM trained online
(one pass: every training window is freshly generated, nothing repeats), a hand
phase schedule, and a pluggable Policy that decides (a) which area each training
window is drawn from and (b) the per-window loss weight.

Everything varies with the seed (corpus tables, fact world, init, held-out) --
the testbed closes D-A13 for itself.

AREAS (name: generator, approx optimum bits/byte ignoring window-start effects)
  easy  : order-1 deterministic cycle over 12 symbols            opt 0.0   (mastered early)
  mid   : order-2 Markov, 16 symbols a-p, 2 distinct successors   opt 1.0
  hard  : order-2 Markov, 20 symbols e-x, 3 distinct successors   opt log2(3)=1.585
  noise : i.i.d. uniform over 32 symbols                          opt 5.0   (noisy TV, unlearnable)
  factT : credible facts   '@Ab=v.'  entity uniform over 64         opt 1.0   (6 bits / 6 bytes)
  factT2: credible facts   '#Ab:v;'  same world, other format       opt 1.0
  factF : FALSE facts      '@Ab=v.'  SAME format as factT; on a designated half of
          the entities the attribute is a fixed wrong value; entities come in a
          fixed cyclic order, so it is MORE FLUENT than factT          opt 0.0
  late  : order-2 Markov over mid's alphabet with an independent table (forgetting
          pressure on mid)                                         opt 1.0

SCHEDULE (availability, hand-set; 4 equal phases)
  P0: easy mid factT factF noise
  P1: mid hard factT2 factF noise
  P2: hard late factT factT2 noise
  P3: late hard factF factT2 noise        (the false source is the most recent one)

BASELINE policy = the tree today: DATA_DRAW='planned' even split of each phase's
windows over its live areas (random order), uniform loss weight, no source labels.

READINGS
  heldout bpb per area (final and at every phase end), gap to optimum, share of
  trained windows per area (time on noise), forgetting = final - min over run,
  fact accuracy on contradicted entities (bare '@Ab=' prompt, T2-format '#Ab:'
  prompt, and a context-primed prompt), p(true)/(p(true)+p(false)), and the
  agreed-entity control accuracy.

Usage:  from testbed import run, PlannedPolicy
        res = run(PlannedPolicy(), seed=0, steps=3000)
"""
import math, random, time, json, os, sys
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.set_num_threads(1)

AREAS = ["easy", "mid", "hard", "noise", "factT", "factT2", "factF", "late"]
SCHEDULE = [
    ["easy", "mid", "factT", "factF", "noise"],
    ["mid", "hard", "factT2", "factF", "noise"],
    ["hard", "late", "factT", "factT2", "noise"],
    ["late", "hard", "factF", "factT2", "noise"],
]
OPT = {"easy": 0.0, "mid": 1.0, "hard": math.log2(3), "noise": 5.0,
       "factT": 1.0, "factT2": 1.0, "factF": 0.0, "late": 1.0}
LEARNABLE = ["easy", "mid", "hard", "factT", "factT2", "late"]  # gap averaged over these

CTX = 128
N_ENT = 64
E1 = "ABCDEFGH"
E2 = "abcdefgh"
VALS = "0123456789QRSTUV"


def _sym(s):
    return [ord(c) for c in s]


class Markov:
    def __init__(self, alphabet, order, branch, rng, det_cycle=False):
        self.a = _sym(alphabet)
        self.order = order
        self.table = {}
        self.det_cycle = det_cycle
        if det_cycle:
            perm = self.a[:]
            rng.shuffle(perm)
            self.table = {(perm[i],): [perm[(i + 1) % len(perm)]] for i in range(len(perm))}
        self.branch = branch
        self.trng = rng  # table rng (lazy rows, deterministic in visit order -> build eagerly)
        if not det_cycle:
            import itertools
            for ctx in itertools.product(self.a, repeat=order):
                self.table[ctx] = rng.sample(self.a, branch)

    def stream(self, rng):
        st = [rng.choice(self.a) for _ in range(self.order)]
        while True:
            nxt = rng.choice(self.table[tuple(st[-self.order:])])
            st = (st + [nxt])[-self.order:]
            yield nxt


class Noise:
    def __init__(self, alphabet):
        self.a = _sym(alphabet)

    def stream(self, rng):
        while True:
            yield rng.choice(self.a)


class Facts:
    """world: entity -> true value. kind in {T, T2, F}."""
    def __init__(self, world, kind, false_map=None, order=None):
        self.world, self.kind, self.false_map, self.order = world, kind, false_map, order

    def record(self, e, v):
        if self.kind == "T2":
            return _sym("#" + e + ":" + v + ";")
        return _sym("@" + e + "=" + v + ".")

    def stream(self, rng):
        i = rng.randrange(N_ENT)
        while True:
            if self.kind == "F":
                e = self.order[i % N_ENT]; i += 1
                v = self.false_map.get(e, self.world[e])
            else:
                e = rng.choice(list(self.world)); v = self.world[e]
            for b in self.record(e, v):
                yield b


class Corpus:
    def __init__(self, seed):
        R = lambda tag: random.Random(f"{seed}:{tag}")
        ents = [a + b for a in E1 for b in E2]
        wr = R("world")
        self.world = {e: wr.choice(VALS) for e in ents}
        contra = wr.sample(ents, N_ENT // 2)
        self.contra = sorted(contra)
        self.agreed = sorted(set(ents) - set(contra))
        self.false_map = {e: wr.choice([v for v in VALS if v != self.world[e]]) for e in contra}
        order = ents[:]; wr.shuffle(order)
        self.gens = {
            "easy": Markov("abcdefghijkl", 1, 1, R("easy.t"), det_cycle=True),
            "mid": Markov("abcdefghijklmnop", 2, 2, R("mid.t")),
            "hard": Markov("efghijklmnopqrstuvwx", 2, 3, R("hard.t")),
            "noise": Noise("abcdefghijklmnopqrstuvwxyz012345"),
            "factT": Facts(self.world, "T"),
            "factT2": Facts(self.world, "T2"),
            "factF": Facts(self.world, "F", self.false_map, order),
            "late": Markov("abcdefghijklmnop", 2, 2, R("late.t")),
        }
        self.train_streams = {a: self.gens[a].stream(R(f"{a}.train")) for a in AREAS}
        self.seed = seed

    def train_window(self, area):
        s = self.train_streams[area]
        return [next(s) for _ in range(CTX + 1)]

    def heldout(self, area, n, tag="ho"):
        R = random.Random(f"{self.seed}:{area}.{tag}")
        out = []
        for k in range(n):
            s = self.gens[area].stream(random.Random(R.random()))
            skip = R.randrange(64)
            for _ in range(skip):
                next(s)
            out.append([next(s) for _ in range(CTX + 1)])
        return out


class LM(nn.Module):
    def __init__(self, d=64, h=128):
        super().__init__()
        self.emb = nn.Embedding(256, d)
        self.rnn = nn.GRU(d, h, batch_first=True)
        self.out = nn.Linear(h, 256)

    def forward(self, x):
        h, _ = self.rnn(self.emb(x))
        return self.out(h)


def window_loss(model, wins, tags=None):
    """per-window mean CE in nats, shape (B,)."""
    x = torch.tensor(wins, dtype=torch.long)
    if tags is not None:
        x = x.clone(); x[:, 0] = torch.tensor(tags)
    logits = model(x[:, :-1])
    ce = F.cross_entropy(logits.reshape(-1, 256), x[:, 1:].reshape(-1), reduction="none")
    return ce.view(x.shape[0], -1).mean(1)


def tag_of(area):
    return 1 + AREAS.index(area)


class Policy:
    """Override draw() and loss_weights(). Optional probe hooks."""
    name = "base"
    probe_every = 0          # steps; 0 = never
    probe_grads = False
    probe_n = 4

    def begin(self, corpus, steps, batch, rng):
        self.corpus, self.steps, self.batch, self.rng = corpus, steps, batch, rng

    def draw(self, step, phase, live, seen):
        raise NotImplementedError

    def loss_weights(self, areas):
        return [1.0] * len(areas)

    def after_step(self, step, areas, bits):
        pass

    def on_probe(self, step, phase, live, seen, losses, grads):
        pass

    def counters(self):
        return {}


class PlannedPolicy(Policy):
    """Tree today: equal split of each phase's windows over its live areas, random order."""
    name = "planned"

    def begin(self, corpus, steps, batch, rng):
        super().begin(corpus, steps, batch, rng)
        self.plan = []
        P = len(SCHEDULE)
        for k, live in enumerate(SCHEDULE):
            s0, s1 = round(k * steps / P), round((k + 1) * steps / P)
            n = (s1 - s0) * batch
            lst = [live[i % len(live)] for i in range(n)]
            rng.shuffle(lst)
            self.plan.extend(lst)

    def draw(self, step, phase, live, seen):
        return self.plan[step * self.batch:(step + 1) * self.batch]


def phase_of(step, steps):
    return min(len(SCHEDULE) - 1, step * len(SCHEDULE) // steps)


@torch.no_grad()
def eval_heldout(model, ho, tags=False):
    model.eval()
    out = {}
    for a, wins in ho.items():
        t = [tag_of(a)] * len(wins) if tags else None
        out[a] = float(window_loss(model, wins, t).mean()) / math.log(2)
    model.train()
    return out


@torch.no_grad()
def fact_probe(model, corpus, tags=False):
    model.eval()
    vals = _sym(VALS)
    res = {}
    ctx_rng = random.Random(f"{corpus.seed}:factprobe")
    prime = {e: "".join("@" + a + "=" + corpus.world[a] + "." for a in ctx_rng.sample(corpus.agreed, 3))
             for e in corpus.world}

    def dist(prompts, tag=None):
        x = [(([tag] if tag else []) + _sym(p)) for p in prompts]
        L = max(len(s) for s in x)
        x = [[ord(".")] * (L - len(s)) + s for s in x]  # left pad with '.'
        lp = F.log_softmax(model(torch.tensor(x)), -1)[:, -1]
        return lp

    for mode, fmt, tg in [("bare", "@{}=", None), ("t2fmt", "#{}:", None), ("primed", "{p}@{}=", None),
                          ("tagT", "@{}=", "factT"), ("tagF", "@{}=", "factF")]:
        if tg and not tags:
            continue
        for grp, ents in [("contra", corpus.contra), ("agreed", corpus.agreed)]:
            prompts = [fmt.format(e, p=prime[e]) if "{p}" in fmt else fmt.format(e) for e in ents]
            lp = dist(prompts, tag_of(tg) if tg else None)
            acc = 0; share = 0.0; pfalse = 0.0
            for i, e in enumerate(ents):
                tv = ord(corpus.world[e])
                am = max(vals, key=lambda v: float(lp[i, v]))
                acc += (am == tv)
                if grp == "contra":
                    fv = ord(corpus.false_map[e])
                    pt, pf = math.exp(float(lp[i, tv])), math.exp(float(lp[i, fv]))
                    share += pt / (pt + pf + 1e-12)
                    pfalse += (am == fv)
            res[f"{mode}.{grp}.acc"] = acc / len(ents)
            if grp == "contra":
                res[f"{mode}.contra.true_share"] = share / len(ents)
                res[f"{mode}.contra.false_acc"] = pfalse / len(ents)
    model.train()
    return res


def flat_grad(model):
    return torch.cat([p.grad.reshape(-1) for p in model.parameters()])


def run(policy, seed=0, steps=3000, batch=8, lr=3e-3, tags=False, ho_n=16, verbose=True, log_every=250):
    t0 = time.time()
    torch.manual_seed(seed)
    random.seed(seed)
    corpus = Corpus(seed)
    model = LM()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    ho = {a: corpus.heldout(a, ho_n) for a in AREAS}               # readings
    probe_ho = {a: corpus.heldout(a, policy.probe_n, tag="probe") for a in AREAS}  # controller's own probe set
    policy.begin(corpus, steps, batch, random.Random(f"{seed}:policy"))
    drawn = {a: 0 for a in AREAS}
    seen = []
    curve = []
    phase_end = []
    probe_windows = 0
    for step in range(steps):
        ph = phase_of(step, steps)
        live = SCHEDULE[ph]
        for a in live:
            if a not in seen:
                seen.append(a)
        if policy.probe_every and step % policy.probe_every == 0 and step > 0:
            losses, grads = {}, {}
            for a in seen:
                wins = probe_ho[a]
                t = [tag_of(a)] * len(wins) if tags else None
                if policy.probe_grads:
                    model.zero_grad()
                    l = window_loss(model, wins, t).mean()
                    l.backward()
                    grads[a] = flat_grad(model).clone()
                    model.zero_grad()
                else:
                    with torch.no_grad():
                        l = window_loss(model, wins, t).mean()
                losses[a] = float(l) / math.log(2)
                probe_windows += len(wins)
            policy.on_probe(step, ph, live, seen, losses, grads)
        areas = policy.draw(step, ph, live, seen)
        wins = [corpus.train_window(a) for a in areas]
        for a in areas:
            drawn[a] += 1
        t = [tag_of(a) for a in areas] if tags else None
        pw = window_loss(model, wins, t)
        w = torch.tensor(policy.loss_weights(areas), dtype=torch.float32)
        loss = (pw * w).sum() / w.sum()
        opt.zero_grad()
        loss.backward()
        opt.step()
        policy.after_step(step, areas, [float(v) / math.log(2) for v in pw.detach()])
        last_of_phase = (step + 1 == steps) or phase_of(step + 1, steps) != ph
        if last_of_phase or (step + 1) % log_every == 0:
            ev = eval_heldout(model, ho, tags)
            rec = {"step": step + 1, "phase": ph, "bpb": ev}
            curve.append(rec)
            if last_of_phase:
                phase_end.append(rec)
            if verbose:
                print(f"[{policy.name} s{seed}] step {step+1} ph{ph} " +
                      " ".join(f"{a}={ev[a]:.2f}" for a in AREAS) + f"  {time.time()-t0:.0f}s", flush=True)
    final = curve[-1]["bpb"]
    tot = sum(drawn.values())
    res = {
        "policy": policy.name, "seed": seed, "steps": steps, "batch": batch, "tags": tags,
        "final_bpb": final,
        "gap": {a: final[a] - OPT[a] for a in AREAS},
        "mean_gap_learnable": sum(final[a] - OPT[a] for a in LEARNABLE) / len(LEARNABLE),
        "share": {a: drawn[a] / tot for a in AREAS},
        "forgetting": {a: final[a] - min(c["bpb"][a] for c in curve) for a in AREAS},
        "phase_end": phase_end,
        "facts": fact_probe(model, corpus, tags),
        "train_windows": tot, "probe_windows": probe_windows,
        "counters": policy.counters(),
        "wall_s": time.time() - t0,
    }
    return res
