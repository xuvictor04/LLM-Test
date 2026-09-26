"""d1: explicit meta-controller = learning-progress bandit (focus) + learned source trust (credibility).

FocusTrust(focus=..., trust=...)
  focus:
    'planned'   : the tree's even split (baseline draw)
    'replay'    : planned + fixed replay share of faded areas (Ibrahim-style fixed-rehearsal baseline)
    'lp'        : absolute-learning-progress bandit, reward from the controller's own held-out probe
    'lp_train'  : same bandit, reward from the free in-stream pre-update loss (prequential) -- no probe
    'loss'      : loss-seeking bandit (ODM-like), reward = probe loss level (noisy-TV ablation)
  trust:
    'off'         : uniform loss weight
    'consistency' : truth-discovery over held-out gradient cosines (agreement with other sources)
    'fluency'     : trust = low loss (the gameable criterion, ablation)

Availability (who is live) stays the hand schedule; the controller sets ALLOCATION over
live areas, plus self-chosen rehearsal of FADED areas (seen earlier, not live now) when their
held-out loss rises.
"""
import math
from testbed import Policy, AREAS, SCHEDULE, PlannedPolicy
import torch


class FocusTrust(Policy):
    def __init__(self, focus="lp", trust="off", name=None, probe_every=20, probe_n=4,
                 explore=0.2, cap=0.5, rehearse_max=0.3, ema_fast=0.5, ema_slow=0.1,
                 replay=0.2, trust_min=0.1, rel_min=0.05, trust_ema=0.2, a_ema=0.3,
                 lp_sig=True):
        self.focus, self.trust_mode = focus, trust
        self.name = name or f"{focus}+{trust}"
        self.probe_every = probe_every if (focus in ("lp", "loss") or trust != "off") else 0
        self.probe_grads = trust == "consistency"
        self.probe_n = probe_n
        self.explore, self.cap, self.rehearse_max = explore, cap, rehearse_max
        self.ef, self.es = ema_fast, ema_slow
        self.replay = replay
        self.tmin, self.rel_min, self.tema, self.aema = trust_min, rel_min, trust_ema, a_ema
        self.lp_sig = lp_sig

    def begin(self, corpus, steps, batch, rng):
        super().begin(corpus, steps, batch, rng)
        self.planned = PlannedPolicy(); self.planned.begin(corpus, steps, batch, rng)
        self.fast, self.slow, self.dev, self.nobs = {}, {}, {}, {}
        self.level = {}
        self.credit = {a: 0.0 for a in AREAS}
        self.p = None
        self.trust = {a: 1.0 for a in AREAS}
        self.A = {}
        self.rr = 0
        self.live_at_plan = None
        self.c = dict(plan_revisions=0, floor_binds=0, cap_binds=0, rehearse_cap_binds=0,
                      lp_negative_pulls=0, rehearsal_windows=0, optimistic_new_arm=0,
                      trust_updates=0, trust_low_areas=0, unresolved_conflicts=0,
                      noise_windows=0)
        self.plog = []
        self.tlog = []

    # ---------- signal books ----------
    def _obs(self, a, L):
        if a not in self.fast:
            self.fast[a] = self.slow[a] = L; self.dev[a] = 0.0; self.nobs[a] = 1
        else:
            d = L - self.fast[a]
            self.fast[a] += self.ef * (L - self.fast[a])
            self.slow[a] += self.es * (L - self.slow[a])
            self.dev[a] += self.es * (abs(d) - self.dev[a])
            self.nobs[a] += 1
        self.level[a] = L

    def _score(self, a, live):
        """absolute learning progress for live arms; only RISING loss for faded arms."""
        if self.nobs.get(a, 0) < 2:
            return None
        diff = self.slow[a] - self.fast[a]           # >0 improving, <0 getting worse
        if self.focus == "loss":
            return self.level[a] if a in live else 0.0
        if a in live:
            s = abs(diff)
        else:
            s = max(0.0, -diff)
        if self.lp_sig:                               # subtract the EMA estimate's own jitter
            s = max(0.0, s - 0.5 * self.dev[a] * math.sqrt(self.ef / (2 - self.ef)))
        return s

    def _replan(self, live, seen):
        faded = [a for a in seen if a not in live]
        sc = {}
        best = 0.0
        for a in live + faded:
            s = self._score(a, live)
            if s is not None:
                sc[a] = s; best = max(best, s)
        for a in live:                                 # optimistic prior for a new arm
            if a not in sc:
                sc[a] = best if best > 0 else 1.0
                self.c["optimistic_new_arm"] += 1
        fsc = {a: sc.get(a, 0.0) for a in faded}
        tot = sum(sc[a] for a in live) + sum(fsc.values())
        p = {}
        n = len(live)
        if tot <= 0:
            for a in live:
                p[a] = 1.0 / n
        else:
            for a in live:
                p[a] = (1 - self.explore) * sc[a] / tot + self.explore / n
            fm = (1 - self.explore) * sum(fsc.values()) / tot
            if fm > self.rehearse_max:
                self.c["rehearse_cap_binds"] += 1
                scale = self.rehearse_max / fm
                spare = fm - self.rehearse_max
                for a in faded:
                    p[a] = (1 - self.explore) * fsc[a] / tot * scale
                for a in live:
                    p[a] += spare * p[a] / sum(p[b] for b in live)
            else:
                for a in faded:
                    p[a] = (1 - self.explore) * fsc[a] / tot
            for a in faded:
                if p[a] > 1e-3:
                    self.c["lp_negative_pulls"] += 1
        # per-area cap (exposure_max analogue); redistribute to uncapped live arms
        for _ in range(3):
            over = {a: v - self.cap for a, v in p.items() if v > self.cap}
            if not over:
                break
            self.c["cap_binds"] += len(over)
            ex = sum(over.values())
            for a in over:
                p[a] = self.cap
            rest = [a for a in live if p[a] < self.cap]
            s = sum(p[a] for a in rest)
            for a in rest:
                p[a] += ex * p[a] / s
        for a in live:
            if p[a] <= self.explore / n + 1e-9 + 1e-3 * self.explore:
                self.c["floor_binds"] += 1
        self.p = p
        self.c["plan_revisions"] += 1

    # ---------- trust ----------
    def _trust_update(self, grads, seen):
        names = [a for a in seen if a in grads]
        G = {a: grads[a] / (grads[a].norm() + 1e-12) for a in names}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                v = float(G[a] @ G[b])
                k = (a, b)
                self.A[k] = v if k not in self.A else self.A[k] + self.aema * (v - self.A[k])
        Aab = lambda a, b: self.A.get((a, b), self.A.get((b, a)))
        t = {a: 1.0 for a in names}
        for _ in range(5):                       # truth-discovery fixed point
            nt = {}
            for a in names:
                num = den = 0.0; nrel = 0; nneg = 0
                for b in names:
                    if b == a:
                        continue
                    v = Aab(a, b)
                    if v is None or abs(v) < self.rel_min:
                        continue
                    nrel += 1; nneg += v < 0
                    num += t[b] * v; den += t[b] * abs(v)
                if nrel < 2:                    # symmetric 1-vs-1 conflict: unresolved, no action
                    nt[a] = 1.0
                    if nneg:
                        self.c["unresolved_conflicts"] += 1
                    continue
                c = num / den
                nt[a] = min(1.0, max(self.tmin, 1.0 + min(0.0, c)))
            t = nt
        for a in names:
            self.trust[a] += self.tema * (t[a] - self.trust[a])
        self.c["trust_updates"] += 1

    def _trust_fluency(self, losses, seen):
        lo, hi = min(losses.values()), max(losses.values())
        for a in seen:
            t = 1.0 - (losses[a] - lo) / (hi - lo + 1e-9)
            t = self.tmin + (1 - self.tmin) * t
            self.trust[a] += self.tema * (t - self.trust[a])
        self.c["trust_updates"] += 1

    # ---------- hooks ----------
    def on_probe(self, step, phase, live, seen, losses, grads):
        if self.focus in ("lp", "loss"):
            for a, L in losses.items():
                self._obs(a, L)
            self.live_at_plan = tuple(live)
            self._replan(live, seen)
            self.plog.append((step, {a: round(v, 4) for a, v in self.p.items()}))
        if self.trust_mode == "consistency":
            self._trust_update(grads, seen)
        elif self.trust_mode == "fluency":
            self._trust_fluency(losses, seen)
        if self.trust_mode != "off":
            self.tlog.append((step, {a: round(self.trust[a], 3) for a in seen}))

    def after_step(self, step, areas, bits):
        if self.focus == "lp_train":
            per = {}
            for a, b in zip(areas, bits):
                per.setdefault(a, []).append(b)
            for a, v in per.items():
                self._obs(a, sum(v) / len(v))

    def draw(self, step, phase, live, seen):
        if self.focus in ("planned", "replay"):
            out = self.planned.draw(step, phase, live, seen)
            if self.focus == "replay":
                faded = [a for a in seen if a not in live]
                if faded:
                    out = list(out)
                    k = round(self.replay * len(out))
                    for i in range(k):
                        out[-1 - i] = faded[self.rr % len(faded)]; self.rr += 1
                        self.c["rehearsal_windows"] += 1
            self.c["noise_windows"] += sum(a == "noise" for a in out)
            return out
        if self.focus == "lp_train":
            if self.p is None or step % self.probe_every_train == 0 or tuple(live) != self.live_at_plan:
                self.live_at_plan = tuple(live)
                self._replan(live, list(live))          # no faded signal without a probe
                self.plog.append((step, {a: round(v, 4) for a, v in self.p.items()}))
        elif self.p is None or tuple(live) != self.live_at_plan:
            self.live_at_plan = tuple(live)
            self._replan(live, seen)
        p = {a: v for a, v in self.p.items() if v > 0}
        z = sum(p.values())
        out = []
        for a in p:
            self.credit[a] += p[a] / z * self.batch
        for _ in range(self.batch):
            a = max(p, key=lambda x: self.credit[x])
            self.credit[a] -= 1.0
            out.append(a)
        for a in out:
            if a not in live:
                self.c["rehearsal_windows"] += 1
        self.c["noise_windows"] += sum(a == "noise" for a in out)
        return out

    probe_every_train = 20

    def loss_weights(self, areas):
        if self.trust_mode == "off":
            return [1.0] * len(areas)
        return [self.trust[a] for a in areas]

    def counters(self):
        c = dict(self.c)
        c["final_trust"] = {a: round(v, 3) for a, v in self.trust.items()}
        c["final_p"] = self.p
        c["A_final"] = {f"{a}|{b}": round(v, 3) for (a, b), v in self.A.items()}
        c["plog"] = self.plog[:: max(1, len(self.plog) // 30)]
        c["tlog"] = self.tlog[:: max(1, len(self.tlog) // 30)]
        return c
