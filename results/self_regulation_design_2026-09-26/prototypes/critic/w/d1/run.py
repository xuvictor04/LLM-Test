"""d1: explicit meta-controller on the shared mm3 testbed (testbed.py reused UNCHANGED).

FOCUS (who gets drawn): a learning-progress bandit over areas.
  arms     = live areas of the phase (availability stays the hand schedule) + FADED areas
             (live earlier, not now) which may be drawn back as self-chosen rehearsal.
  reward   = absolute learning progress |slow EMA - fast EMA| of the area's loss, minus the
             EMA estimate's own jitter; for a FADED arm only RISING loss counts (forgetting).
  source   = 'probe': controller's own fixed held-out probe windows (stream 'probe', disjoint from
             the readings' 'heldout' stream), every PROBE_EVERY optimizer steps;
             'train': the free in-stream prequential loss from policy.note (no extra compute, but
             no signal for faded areas and only for areas it chooses to draw -> feedback loop).
  share    = (1-explore)*reward/sum + explore/n_live ; per-area cap ; faded total <= rehearse_max.
  realised = deficit scheduling per segment (bytes drawn since the last re-plan vs plan).
CREDIBILITY (how much each area's tokens count): a per-area trust t_a in [trust_min, 1] that
  multiplies that area's token loss weights (renormalised to mean 1 per batch).
  'consistency': truth discovery over the cosine matrix of the areas' held-out probe gradients:
        c_a = sum_b t_b A_ab / sum_b t_b |A_ab|  (b related: |A_ab| >= rel_min),
        t_a = clip(1 + min(0, c_a - c_ref), trust_min, 1), c_ref = median c over areas,
        needs >= 2 related areas (a 1-vs-1 conflict is left unresolved, counted), 5 fixed-point
        iterations, EMA over probes.
  'claims': same, but each area's probe gradient only over its CONFIDENT tokens (per-token loss
        below that area's median on the probe) -- a structure-agnostic proxy for "what the
        source asserts" as opposed to its filler/style.
  'fluency': t_a from LOW loss (the gameable rule; ablation).
Usage: python run.py --arm full --seed 0 [--bytes 4000000]
"""
import sys, os, json, math, time, argparse, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "testbed"))
import torch, torch.nn.functional as F
import testbed as tb

torch.set_num_threads(1)

ARMS = {  # arm: (focus, trust)
    "base": ("planned", "off"),
    "replay": ("replay", "off"),
    "lp": ("lp", "off"),
    "lp_train": ("lp_train", "off"),
    "loss": ("loss", "off"),
    "lp_nofloor": ("lp", "off"),
    "trust": ("planned", "consistency"),
    "trust_claims": ("planned", "claims"),
    "trust_fluency": ("planned", "fluency"),
    "trust_surprise": ("planned", "surprise"),
    "full_surprise": ("lp", "surprise"),
    "full": ("lp", "consistency"),
    "full_claims": ("lp", "claims"),
}
ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True, choices=list(ARMS))
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--bytes", type=int, default=4_000_000)
ap.add_argument("--probe_every", type=int, default=10)      # optimizer steps (x16 windows)
ap.add_argument("--probe_n", type=int, default=4)           # windows per area per probe
ap.add_argument("--explore", type=float, default=0.2)
ap.add_argument("--cap", type=float, default=0.5)
ap.add_argument("--rehearse_max", type=float, default=0.3)
ap.add_argument("--replay", type=float, default=0.2)
ap.add_argument("--ema_fast", type=float, default=0.5)
ap.add_argument("--ema_slow", type=float, default=0.1)
ap.add_argument("--trust_min", type=float, default=0.1)
ap.add_argument("--rel_min", type=float, default=0.05)
ap.add_argument("--trust_ema", type=float, default=0.2)
ap.add_argument("--trust_rule", default="peer", choices=["peer", "median"])
ap.add_argument("--trust_kappa", type=float, default=2.0)
ap.add_argument("--trust_margin", type=float, default=0.1)
ap.add_argument("--h_conf", type=float, default=1.0)      # bits: 'confident' token threshold
ap.add_argument("--trust_grace", type=int, default=20)     # probes before an area is judged
ap.add_argument("--tag", default="")
args = ap.parse_args()
FOCUS, TRUST = ARMS[args.arm]
if args.arm == "lp_nofloor":
    args.explore = 0.0
AREAS = tb.AREAS
SEG_MEAN = (tb.SEG_MIN + tb.SEG_MAX) / 2

# --- label access for weight_fn (the tree root has Segmentation.labels; the testbed only hands
#     labels to policy.note AFTER the step). Subclass records the live Stream; testbed file unchanged.
CUR = {}


class RecStream(tb.Stream):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        CUR["st"] = self


tb.Stream = RecStream


def batch_labels(step):
    st = CUR["st"]
    lo = step * tb.BATCH * tb.CTX
    lab = torch.tensor(st.lab[lo:lo + tb.BATCH * tb.CTX + 1])
    idx = torch.arange(tb.BATCH)[:, None] * tb.CTX + torch.arange(tb.CTX + 1)[None, :]
    return lab[idx][:, 1:]


class Controller(tb.PlannedPolicy):
    def __init__(self):
        self.fast, self.slow, self.dev, self.nobs, self.level = {}, {}, {}, {}, {}
        self.p, self.snap, self.seen, self.live = None, None, [], []
        self.trust = {a: 1.0 for a in AREAS}
        self.A = {}
        self.z, self.age = {}, {}
        self.c = dict(plan_revisions=0, floor_binds=0, cap_binds=0, rehearse_cap_binds=0,
                      lp_negative_pulls=0, rehearsal_bytes=0, optimistic_new_arm=0,
                      trust_updates=0, unresolved_conflicts=0, probes=0, probe_windows=0,
                      trust_min_binds=0)
        self.plog, self.tlog, self.alog = [], [], []
        self.train_books = {}

    # ---------------- draw ----------------
    def budgets(self, phase, live, span):
        for a in live:
            if a not in self.seen:
                self.seen.append(a)
        self.live = list(live)
        faded = [a for a in self.seen if a not in live]
        if FOCUS == "planned":
            return super().budgets(phase, live, span)
        if FOCUS == "replay":
            b = super().budgets(phase, live, round(span * (1 - args.replay)) if faded else span)
            for a in faded:
                b[a] = round(span * args.replay / len(faded))
            return b
        self._replan()                         # arm set changed
        return {a: span for a in self.seen}    # budgets never bind; allocation is the plan

    def choose(self, rng, live, left):
        if FOCUS == "planned":
            return super().choose(rng, live, left)
        if FOCUS == "replay":
            cand = [a for a in left if left[a] > 0]
            return rng.choice(cand)
        st = CUR["st"]
        if self.snap is None:
            self.snap = dict(st.drawn)
        done = {a: st.drawn[a] - self.snap.get(a, 0) for a in AREAS}
        tot = sum(done.values()) + SEG_MEAN
        best = max(self.p, key=lambda a: self.p[a] * tot - done[a])
        if best not in live:
            self.c["rehearsal_bytes"] += int(SEG_MEAN)
        return best

    def _score(self, a):
        if self.nobs.get(a, 0) < 2:
            return None
        if FOCUS == "loss":
            return self.level[a] if a in self.live else 0.0
        diff = self.slow[a] - self.fast[a]              # >0 improving, <0 worsening
        s = abs(diff) if a in self.live else max(0.0, -diff)
        jitter = self.dev[a] * math.sqrt(args.ema_fast / (2 - args.ema_fast))
        return max(0.0, s - 0.5 * jitter)

    def _replan(self):
        live = self.live
        faded = [a for a in self.seen if a not in live] if FOCUS != "lp_train" else []
        sc, best = {}, 0.0
        for a in live + faded:
            s = self._score(a)
            if s is not None:
                sc[a] = s; best = max(best, s)
        for a in live:
            if a not in sc:                              # new arm: optimistic prior
                sc[a] = best if best > 0 else 1.0
                self.c["optimistic_new_arm"] += 1
        for a in faded:
            sc.setdefault(a, 0.0)
        tot = sum(sc.values())
        n = len(live)
        ex = args.explore
        if tot <= 0:
            p = {a: 1.0 / n for a in live}
        else:
            p = {a: (1 - ex) * sc[a] / tot + (ex / n if a in live else 0.0) for a in sc}
            fm = sum(p[a] for a in faded)
            if fm > args.rehearse_max:
                self.c["rehearse_cap_binds"] += 1
                k = args.rehearse_max / fm
                spare = fm - args.rehearse_max
                for a in faded:
                    p[a] *= k
                sl = sum(p[a] for a in live)
                for a in live:
                    p[a] += spare * p[a] / sl
            for a in faded:
                if p[a] > 1e-3:
                    self.c["lp_negative_pulls"] += 1
        for _ in range(4):
            over = [a for a in p if p[a] > args.cap + 1e-12]
            if not over:
                break
            self.c["cap_binds"] += len(over)
            extra = sum(p[a] - args.cap for a in over)
            for a in over:
                p[a] = args.cap
            rest = [a for a in live if p[a] < args.cap]
            s = sum(p[a] for a in rest)
            for a in rest:
                p[a] += extra * (p[a] / s if s > 0 else 1 / len(rest))
        for a in live:
            if p[a] <= ex / n + 1e-4:
                self.c["floor_binds"] += 1
        self.p = p
        self.snap = dict(CUR["st"].drawn) if "st" in CUR else None
        self.c["plan_revisions"] += 1

    def _obs(self, a, L):
        if a not in self.fast:
            self.fast[a] = self.slow[a] = L; self.dev[a] = 0.0; self.nobs[a] = 1
        else:
            d = L - self.fast[a]
            self.fast[a] += args.ema_fast * d
            self.slow[a] += args.ema_slow * (L - self.slow[a])
            self.dev[a] += args.ema_slow * (abs(d) - self.dev[a])
            self.nobs[a] += 1
        self.level[a] = L

    def note(self, area_ids, nats, weights=None):
        if FOCUS != "lp_train":
            return
        for i in area_ids.unique().tolist():
            m = area_ids == i
            self._obs(AREAS[i], float(nats[m].mean()) / tb.L2)
        self.train_books["n"] = self.train_books.get("n", 0) + 1
        if self.train_books["n"] % args.probe_every == 0:
            self._replan()
            self.plog.append((self.train_books["n"], {a: round(v, 3) for a, v in self.p.items()}))

    # ---------------- probe (controller's own held-out) ----------------
    def probe(self, model, step):
        need_loss = FOCUS in ("lp", "loss") or TRUST in ("fluency", "surprise")
        need_grad = TRUST in ("consistency", "claims")
        if not (need_loss or need_grad) or step == 0 or step % args.probe_every:
            return
        self.c["probes"] += 1
        losses, grads = {}, {}
        surpr = {}
        for a in self.seen:
            x = PROBE[a]
            self.c["probe_windows"] += x.shape[0]
            if need_grad:
                model.zero_grad()
                nats = F.cross_entropy(model(x[:, :-1]).reshape(-1, 256), x[:, 1:].reshape(-1),
                                       reduction="none")
                if TRUST == "claims":
                    m = (nats.detach() <= nats.detach().median()).float()
                    l = (nats * m).sum() / m.sum()
                else:
                    l = nats.mean()
                l.backward()
                grads[a] = torch.cat([p.grad.reshape(-1) for p in model.parameters() if p.grad is not None]).clone()
                model.zero_grad()
                losses[a] = float(nats.mean()) / tb.L2
            else:
                with torch.no_grad():
                    lg = model(x[:, :-1]).reshape(-1, 256)
                    nats = F.cross_entropy(lg, x[:, 1:].reshape(-1), reduction="none")
                    losses[a] = float(nats.mean()) / tb.L2
                    if TRUST == "surprise":
                        lp_ = F.log_softmax(lg, -1)
                        H = -(lp_.exp() * lp_).sum(-1) / tb.L2          # model entropy, bits
                        ex = nats / tb.L2 - H                           # excess surprise, bits
                        m = H < args.h_conf
                        surpr[a] = (float(ex[m].mean()) if int(m.sum()) >= 16 else None, int(m.sum()))
        if FOCUS in ("lp", "loss"):
            for a, L in losses.items():
                self._obs(a, L)
            self._replan()
            self.plog.append((step, {a: round(v, 3) for a, v in self.p.items()}))
        if need_grad:
            self._trust_consistency(grads)
        elif TRUST == "surprise":
            self._trust_surprise(surpr)
        elif TRUST == "fluency":
            lo, hi = min(losses.values()), max(losses.values())
            for a in self.seen:
                t = args.trust_min + (1 - args.trust_min) * (1 - (losses[a] - lo) / (hi - lo + 1e-9))
                self.trust[a] += args.trust_ema * (t - self.trust[a])
            self.c["trust_updates"] += 1
        if TRUST != "off":
            self.tlog.append((step, {a: round(self.trust[a], 3) for a in self.seen}))

    def _trust_surprise(self, surpr):
        """excess surprise on CONFIDENT tokens: a source whose claims the model (the consensus of all
        sources it has read) confidently contradicts, beyond the model's own uncertainty."""
        for a, (z, n) in surpr.items():
            self.age[a] = self.age.get(a, 0) + 1
            if z is None:
                continue
            self.z[a] = z if a not in self.z else self.z[a] + args.trust_ema * (z - self.z[a])
        judged = [a for a in self.z if self.age[a] >= args.trust_grace]
        if len(judged) < 3:
            self.c["unresolved_conflicts"] += 1
            return
        zref = statistics.median(self.z[a] for a in judged)
        for a in judged:
            t = min(1.0, max(args.trust_min, 1.0 - args.trust_kappa * max(0.0, self.z[a] - zref - args.trust_margin)))
            self.trust[a] += args.trust_ema * (t - self.trust[a])
            if t <= args.trust_min + 1e-9:
                self.c["trust_min_binds"] += 1
        self.last_c = {a: round(self.z[a], 3) for a in self.z}
        self.c["trust_updates"] += 1
        if self.c["trust_updates"] % 10 == 1:
            self.alog.append((self.c["trust_updates"], {}, dict(self.last_c)))

    def _trust_consistency(self, grads):
        names = list(grads)
        G = {a: grads[a] / (grads[a].norm() + 1e-12) for a in names}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                v = float(G[a] @ G[b])
                k = (a, b)
                self.A[k] = v if k not in self.A else self.A[k] + 0.3 * (v - self.A[k])
        Aab = lambda a, b: self.A.get((a, b), self.A.get((b, a)))
        t = {a: 1.0 for a in names}
        if args.trust_rule == "median":        # v0: signed agreement vs population median
            for _ in range(5):
                cs = {}
                for a in names:
                    num = den = 0.0; nrel = 0; nneg = 0
                    for b in names:
                        if b == a:
                            continue
                        v = Aab(a, b)
                        if v is None or abs(v) < args.rel_min:
                            continue
                        nrel += 1; nneg += v < 0
                        num += t[b] * v; den += t[b] * abs(v)
                    cs[a] = (num / den) if nrel >= 2 else None
                    if nrel < 2 and nneg:
                        self.c["unresolved_conflicts"] += 1
                valid = [v for v in cs.values() if v is not None]
                cref = statistics.median(valid) if valid else 0.0
                t = {a: (1.0 if cs[a] is None else min(1.0, max(args.trust_min, 1.0 + min(0.0, cs[a] - cref))))
                     for a in names}
        else:                                  # v1 'peer': agreement with trusted PEERS (positively related areas)
            for _ in range(5):
                cs = {}
                for a in names:
                    N = [b for b in names if b != a and Aab(a, b) is not None and Aab(a, b) >= args.rel_min]
                    if len(N) < 2:
                        cs[a] = None
                        continue
                    cs[a] = sum(t[b] * Aab(a, b) for b in N) / sum(t[b] for b in N)
                nt = {}
                for a in names:
                    if cs[a] is None:
                        nt[a] = 1.0; continue
                    N = [b for b in names if b != a and Aab(a, b) is not None and Aab(a, b) >= args.rel_min]
                    ref = max([cs[a]] + [cs[b] for b in N if cs[b] is not None])
                    short = max(0.0, 1.0 - cs[a] / ref - args.trust_margin) if ref > 0 else 0.0
                    nt[a] = min(1.0, max(args.trust_min, 1.0 - args.trust_kappa * short))
                t = nt
            self.c["unresolved_conflicts"] += sum(v is None for v in cs.values())
        self.last_c = {a: (round(v, 3) if v is not None else None) for a, v in cs.items()}
        for a in names:
            self.trust[a] += args.trust_ema * (t[a] - self.trust[a])
            if t[a] <= args.trust_min + 1e-9:
                self.c["trust_min_binds"] += 1
        self.c["trust_updates"] += 1
        if self.c["trust_updates"] % 10 == 1:
            self.alog.append((self.c["trust_updates"], {f"{a}|{b}": round(v, 3) for (a, b), v in self.A.items()},
                              dict(self.last_c)))

    def state(self):
        c = dict(self.c)
        c["final_p"] = self.p
        c["final_trust"] = {a: round(v, 3) for a, v in self.trust.items()}
        c["A_final"] = {f"{a}|{b}": round(v, 3) for (a, b), v in self.A.items()}
        c["c_final"] = getattr(self, "last_c", None)
        c["plog"] = self.plog[:: max(1, len(self.plog) // 40)]
        c["tlog"] = self.tlog[:: max(1, len(self.tlog) // 40)]
        c["alog"] = self.alog
        return c


def weight_fn(model, x, s, nats, step):
    if TRUST == "off":
        return None
    lab = batch_labels(step)
    t = torch.tensor([CTRL.trust[a] for a in AREAS])
    w = t[lab]
    return w / w.mean()


CTRL = Controller()
world = tb.World(args.seed)
PROBE = {}
for a in AREAS:
    g = tb.AreaGen(a, args.seed, world, stream="probe")
    b, _ = g.gen(args.probe_n * (tb.CTX + 1))
    PROBE[a] = torch.tensor(list(b), dtype=torch.long).view(args.probe_n, tb.CTX + 1)

t0 = time.time()
os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
name = f"{args.arm}{args.tag}_s{args.seed}"
logf = open(os.path.join(HERE, "logs", name + ".log"), "w")
res = tb.train(args.seed, args.bytes, policy=CTRL, weight_fn=weight_fn,
               extra={"after_step": lambda m, st: CTRL.probe(m, st + 1)}, log=logf)
summ = tb.summarize(res)
summ["counters"] = res["policy_state"]
summ["curve"] = [{"frac": r["frac"], "null": {n: r["heldout"][n]["null"] for n in AREAS},
                  "facts": {c: {k: r["facts"][c][k]["acc_true"] for k in r["facts"][c]} for c in r["facts"]}}
                 for r in res["evals"]]
summ["train_windows"] = res["n_steps"] * tb.BATCH
summ["probe_windows"] = CTRL.c["probe_windows"]
summ["probe_overhead_windows_frac"] = CTRL.c["probe_windows"] / summ["train_windows"]
summ.update(arm=args.arm, focus=FOCUS, trust=TRUST, seed=args.seed, bytes=args.bytes,
            args=vars(args), n_steps=res["n_steps"], wall=time.time() - t0, segments=res["segments"])
with open(os.path.join(HERE, "out", name + ".json"), "w") as f:
    json.dump(summ, f, indent=1)
print(json.dumps({k: summ[k] for k in ("arm", "seed", "wall", "gap_end", "forget_hard", "drawn_share")}), flush=True)
