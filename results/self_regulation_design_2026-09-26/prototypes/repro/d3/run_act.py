"""JUDGE VARIANT (judge/w/d3/run_act.py): d3 run.py with the tree's act constraint emulated. The plan is
still recomputed at every probe, but it is APPLIED (the tail re-laid) only at an "act": the first probe after a
phase entry, then every --act_every probes (0 = every probe = d3 as run). Between acts the last applied shares
keep being realised by deficit scheduling. Counter focus.acts."""
"""d3: forgetting-driven self-regulated focus + consistency-based credibility, on the shared mm3 testbed
(testbed.py imported UNCHANGED from ../testbed; this file adds only design code).

FOCUS (what gets drawn), re-planned every PROBE_EVERY optimizer steps from an ONLINE R-MATRIX:
  probe      fixed probe windows per area (own generator stream 'probe_d3', disjoint from the readings'
             'heldout' stream), scored every PROBE_EVERY steps -> L_a (bits/byte) for every area SEEN so far
             (an unseen area has no row: ABSENT).  Books per area: fast/slow EMA (Lf, Ls), jitter (EMA |L-Lf|),
             best = running min of Ls.
  lp_a       live areas: |Ls-Lf| minus jitter, per probe interval (divided by the EMA lag difference).
  F_a        faded areas (seen, not live in this phase): measured forgetting max(0, Lf - best - jitter).
  R_a        MIR-style predicted interference: virtual step theta' = theta - s * g/|g| where g = gradient of the
             current plan's live-share-weighted probe loss and s = |theta_now - theta_at_last_probe| (the realized
             update size of one interval); R_a = L_a(theta') - L_a(theta)  (bits/byte one interval ahead).
  need_a     faded: max(0, R_a - jitter) + F_a / H_REC  (per-interval bits/byte at stake).
  pacing     rehearsal fraction rho = min(RHO_MAX, sum need / (sum need + sum lp)); rho = 0 when nothing is being
             lost -> the stream advances on new material.
  shares     live: (1-rho) * [FLOOR/n_live + (1-FLOOR) * lp_a/sum lp]  (even if sum lp = 0), per-area cap CAP;
             faded: rho * need_a / sum need.  Realised by deficit scheduling per segment (700..1800 bytes).
CREDIBILITY (how much each source's tokens count): per source (area label, the tree's Stream.labels),
  on CONFIDENT predictions (p_max >= CONF): observed misses m_a vs the model's own expected misses q_a = sum(1-p_max)
  (both decayed sums).  Contradiction ratio c_a = (m_a+1)/(q_a+1): a source consistent with what the model has
  established scores ~1 whatever its entropy (noise has no confident tokens: ABSENT); a source that contradicts
  corroborated knowledge scores > 1.  trust t_a = clip(median_c / c_a, T_MIN, 1)  (truth-discovery form: weight in
  inverse proportion to measured contradiction rate relative to the population).  Guards: T_MIN floor (never
  suppressed), GRACE steps after a source's arrival (novel source not judged while being learned), falling-hold
  (a source whose c_a is falling >10% over 100 steps is being learned, its trust is not lowered), >=3 eligible sources
  for a median.  Actuation: token loss weight t_a, renormalised to mean 1 per batch.
Arms: base (testbed.train, the tree today), full, focus (no trust), focus_nomir, rehearse (planned-even live split +
  forgetting rehearsal + MIR), trust (planned draw + trust), replay_fixed (planned + fixed 20% faded rehearsal in P3),
  mf_base / mf_trust (majority-false stress world: corrob ALSO lies, on the W entities).
Usage: python run.py --arm full --seed 0 [--bytes 4000000]
"""
import sys, os, json, math, time, argparse, statistics, copy, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "testbed"))
import torch, torch.nn.functional as F
import testbed as tb
from testbed import AREAS, A, PHASES, CTX, BATCH, SEG_MIN, SEG_MAX, L2

torch.set_num_threads(1)
ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--bytes", type=int, default=4_000_000)
ap.add_argument("--probe_every", type=int, default=10)   # optimizer steps
ap.add_argument("--probe_n", type=int, default=6)        # windows per area
ap.add_argument("--floor", type=float, default=0.3)      # share of live bytes split evenly (anti-starvation)
ap.add_argument("--cap", type=float, default=0.5)        # max share of any one live area
ap.add_argument("--rho_max", type=float, default=0.3)    # max rehearsal fraction
ap.add_argument("--h_rec", type=float, default=10.0)     # intervals over which measured forgetting is to be recovered
ap.add_argument("--warm_probes", type=int, default=10)   # probes before an area's lp/need is trusted
ap.add_argument("--conf", type=float, default=0.5)     # "established belief": model top-1 prob >= conf
ap.add_argument("--t_min", type=float, default=0.3)
ap.add_argument("--gain", type=float, default=10.0)      # trust loss per unit excess confident-miss rate above ref
ap.add_argument("--grace", type=int, default=150)        # optimizer steps after a source's arrival
ap.add_argument("--decay", type=float, default=0.995)    # per-step decay of the contradiction books
ap.add_argument("--replay", type=float, default=0.2)     # replay_fixed arm share
ap.add_argument("--check", action="store_true")          # determinism check vs testbed.train (base path)
ap.add_argument("--tag", default="")
ap.add_argument("--act_every", type=int, default=0)
args = ap.parse_args()
arm = args.arm
FOCUS = arm in ("full", "full_td", "fulltd", "focus", "focus_nomir", "rehearse")
LP_LIVE = arm in ("full", "full_td", "fulltd", "focus", "focus_nomir")
MIR = arm in ("full", "full_td", "fulltd", "focus", "rehearse")
TRUST = arm in ("full", "full_td", "trust", "mf_trust")
CLAIM_TD = arm in ("trust_td", "fulltd", "mf_trust_td")   # claim-level truth discovery credibility
TRUST_DRAW = arm in ("full_td", "fulltd")   # credibility-gated focus: live lp_a multiplied by trust t_a
TRUST_OBJ = [None]
REPLAY = arm == "replay_fixed"
MF = arm.startswith("mf_")

C = {}  # did-it-fire counters (absent key = never reachable in this arm)


def cnt(k, v=1):
    C[k] = C.get(k, 0) + v


# ---------------------------------------------------------------- majority-false stress world
class LyingCorrob(tb.AreaGen):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.val = self.world.lie   # corrob now states the liar's value on its (W) entities


# ---------------------------------------------------------------- stream with any-area draw
class D3Stream(tb.Stream):
    """Same generators/labels as tb.Stream; the policy may return a FADED (seen, not live) area; segment length
    randint(SEG_MIN, SEG_MAX) truncated to the phase end; area picked by the policy (deficit scheduling)."""

    def fill(self, need):
        while len(self.buf) < need and len(self.buf) < self.total:
            pos = len(self.buf)
            k = max(i for i in range(4) if self.spans[i][0] <= pos)
            if k != self.phase:
                self.phase = k
                self.policy.enter(k)
            a = self.policy.pick(self.rng, k)
            n = max(1, min(self.rng.randint(SEG_MIN, SEG_MAX), self.spans[k][1] - pos))
            b, _ = self.gens[a].gen(n)
            self.buf += b
            self.lab += [A[a]] * n
            self.tag += [0] * n
            self.drawn[a] += n
            self.policy.took(a, n)
            self.n_segments += 1


class SharePolicy:
    """Target shares over areas; deficit scheduling since the last re-plan."""

    def __init__(self):
        self.phase = 0
        self.shares = {}
        self.since = {}
        self.ever = set()
        self.first_seen = {}

    def enter(self, k):
        self.phase = k
        live = PHASES[k]
        self.set_shares({a: 1.0 / len(live) for a in live})
        cnt("focus.phase_entries")

    def set_shares(self, sh):
        self.shares = {a: v for a, v in sh.items() if v > 0}
        self.since = {a: 0 for a in self.shares}

    def pick(self, rng, k):
        tot = sum(self.since.values()) + SEG_MAX
        best, bd = None, None
        for a, s in self.shares.items():
            d = s * tot - self.since[a] + rng.random() * 1e-3
            if bd is None or d > bd:
                best, bd = a, d
        return best

    def took(self, a, n):
        self.since[a] = self.since.get(a, 0) + n
        self.ever.add(a)

    def note(self, *a, **k):
        pass

    def state(self):
        return {"shares": self.shares}


class ReplayFixed(SharePolicy):
    def enter(self, k):
        super().enter(k)
        live = PHASES[k]
        faded = [a for a in self.ever if a not in live]
        if faded:
            sh = {a: (1 - args.replay) / len(live) for a in live}
            for a in faded:
                sh[a] = args.replay / len(faded)
            self.set_shares(sh)
            cnt("replay.fixed_phases")


class Books:
    def __init__(self):
        self.Lf, self.Ls, self.best, self.jit, self.n, self.L, self.d = {}, {}, {}, {}, {}, {}, {}

    def update(self, a, L, af=0.3, as_=0.05):
        if a not in self.Lf:
            self.Lf[a] = self.Ls[a] = self.best[a] = L
            self.jit[a], self.n[a], self.d[a] = 0.0, 0, 0.0
        dl = L - self.L.get(a, L)
        self.jit[a] += 0.1 * (abs(dl - self.d[a]) - self.jit[a])
        self.d[a] += 0.1 * (dl - self.d[a])
        self.Lf[a] += af * (L - self.Lf[a])
        self.Ls[a] += as_ * (L - self.Ls[a])
        self.best[a] = min(self.best[a], self.Ls[a])
        self.n[a] += 1
        self.L[a] = L


LAG = (1 - 0.05) / 0.05 - (1 - 0.3) / 0.3   # EMA lag difference, in probe intervals


class FocusPolicy(SharePolicy):
    def __init__(self):
        super().__init__()
        self.books = Books()
        self.log = []

    def replan(self, step, L, R):
        cnt("focus.replans")
        k = self.phase
        live = PHASES[k]
        seen = [a for a in AREAS if a in self.ever]
        for a in seen:
            self.books.update(a, L[a])
        bk = self.books
        warm = {a: bk.n.get(a, 0) >= args.warm_probes for a in seen}
        lp = {}
        for a in live:
            if a in seen and warm[a]:
                lp[a] = max(0.0, abs(bk.Ls[a] - bk.Lf[a]) - bk.jit[a]) / LAG
        if TRUST_DRAW and TRUST_OBJ[0] is not None:
            for a in lp:
                t = float(TRUST_OBJ[0].t[A[a]])
                if t < 1.0:
                    lp[a] *= t
                    cnt("focus.trust_gated")
        if lp:
            opt_lp = max(lp.values())
            for a in live:
                if a not in lp:
                    lp[a] = opt_lp          # optimism for an unmeasured (new) area: no avoidance of new material
                    cnt("focus.optimistic_prior")
        faded = [a for a in seen if a not in live and warm[a]]
        need = {}
        for a in faded:
            Fa = max(0.0, bk.Lf[a] - bk.best[a] - bk.jit[a])
            Ra = max(0.0, R.get(a, 0.0) - bk.jit[a]) if R else 0.0
            need[a] = Ra + Fa / args.h_rec
            if Fa > 0:
                cnt("focus.forgetting_seen")
            if Ra > 0:
                cnt("focus.mir_positive")
        sl, sn = sum(lp.values()), sum(need.values())
        rho = min(args.rho_max, sn / (sn + sl + 1e-9)) if sn > 0 else 0.0
        if rho > 0:
            cnt("focus.rehearse_fired")
            if rho >= args.rho_max - 1e-9:
                cnt("focus.rho_cap_binds")
        if LP_LIVE and sl > 0:
            cnt("focus.lp_active")
            sh = {a: args.floor / len(live) + (1 - args.floor) * lp.get(a, 0.0) / sl for a in live}
            for _ in range(5):   # cap with redistribution
                over = {a: v for a, v in sh.items() if v > args.cap}
                if not over:
                    break
                cnt("focus.cap_binds")
                ex = sum(v - args.cap for v in over.values())
                under = [a for a in sh if sh[a] < args.cap]
                for a in over:
                    sh[a] = args.cap
                us = sum(sh[a] for a in under)
                for a in under:
                    sh[a] += ex * sh[a] / us
            for a in live:
                if lp.get(a, 0.0) == 0.0:
                    cnt("focus.floor_binds")
        else:
            sh = {a: 1.0 / len(live) for a in live}
        sh = {a: v * (1 - rho) for a, v in sh.items()}
        for a in faded:
            if sn > 0 and need[a] > 0:
                sh[a] = rho * need[a] / sn
        self.nrep = getattr(self, "nrep", 0) + 1
        if args.act_every and getattr(self, "act_phase", None) == k and self.nrep - self.last_act < args.act_every:
            cnt("focus.act_withheld")
        else:
            self.act_phase, self.last_act = k, self.nrep
            cnt("focus.acts")
            self.set_shares(sh)
        self.log.append({"step": step, "phase": k, "rho": rho, "shares": {a: round(v, 4) for a, v in sh.items()},
                         "lp": {a: round(v, 5) for a, v in lp.items()}, "need": {a: round(v, 5) for a, v in need.items()},
                         "L": {a: round(L[a], 4) for a in seen}, "R": {a: round(v, 5) for a, v in (R or {}).items()}})

    def state(self):
        return {"log": self.log}


class Probe:
    def __init__(self, seed, world, n):
        self.x = {}
        for a in AREAS:
            g = tb.AreaGen(a, seed, world, stream="probe_d3")
            b, _ = g.gen(n * (CTX + 1))
            self.x[a] = torch.tensor(list(b), dtype=torch.long).view(n, CTX + 1)

    def loss(self, model, areas):
        X = torch.cat([self.x[a] for a in areas])
        lo = model(X[:, :-1])
        ce = F.cross_entropy(lo.reshape(-1, 256), X[:, 1:].reshape(-1), reduction="none").view(len(areas), -1)
        return ce.mean(1) / L2   # bits/byte per area

    @torch.no_grad()
    def losses(self, model, areas):
        return {a: float(v) for a, v in zip(areas, self.loss(model, areas))}


class Trust:
    def __init__(self):
        n = len(AREAS)
        self.m, self.q, self.c = torch.zeros(n), torch.zeros(n), torch.zeros(n)
        self.t = torch.ones(n)
        self.hist = []   # (step, ratio vector)
        self.first = {}
        self.log = []

    @torch.no_grad()
    def observe(self, logits, y, lab, step):
        p = torch.softmax(logits.float(), -1)
        pm, am = p.max(-1)
        conf = (pm >= args.conf).float().reshape(-1)
        miss = (am != y).float().reshape(-1)
        l = lab.reshape(-1)
        n = len(AREAS)
        self.m.mul_(args.decay).add_(torch.bincount(l, conf * miss, n))
        self.q.mul_(args.decay).add_(torch.bincount(l, conf * (1 - pm.reshape(-1)), n))
        self.c.mul_(args.decay).add_(torch.bincount(l, conf, n))
        for a in l.unique().tolist():
            self.first.setdefault(a, step)
        if step % 10 == 0:
            self.update(step, live=set(A[x] for x in PHASES[phase_of(step)]))

    def update(self, step, live):
        ratio = (self.m - self.q) / (self.c + 50.0)   # excess confident-miss rate (observed - model-expected)
        self.hist.append((step, ratio.clone()))
        elig = [i for i in range(len(AREAS)) if i in live and self.c[i] >= 100]
        if len(elig) < 3:
            cnt("trust.too_few_sources")
            return
        ref = max(0.0, statistics.median(float(ratio[i]) for i in elig))
        old = [r for s, r in self.hist if s <= step - 100]
        for i in elig:
            new = min(1.0, max(args.t_min, 1.0 - args.gain * (float(ratio[i]) - ref)))
            if step < self.first.get(i, 0) + args.grace:
                if new < 1.0:
                    cnt("trust.grace_holds")
                continue
            if new < float(self.t[i]) and old and float(ratio[i]) < float(old[-1][i]) - max(0.002, 0.2 * abs(float(old[-1][i]))):
                cnt("trust.falling_holds")
                continue
            if new < 1.0:
                cnt("trust.actuations")
            if new <= args.t_min + 1e-9:
                cnt("trust.floor_binds")
            self.t[i] = new
        if step % 100 == 0:
            self.log.append({"step": step, "ratio": {AREAS[i]: round(float(ratio[i]), 3) for i in range(len(AREAS)) if self.c[i] >= 100},
                             "conf_mass": {AREAS[i]: round(float(self.c[i]), 1) for i in range(len(AREAS))},
                             "trust": {AREAS[i]: round(float(self.t[i]), 3) for i in range(len(AREAS))}})


class ClaimTD:
    """DATA-side, model-free truth discovery over byte-level CLAIMS.
    claim   : a K-byte context c on which source s is SELF-CONSISTENT: seen >= MIN_N times in s (within one
              segment), top continuation share >= SELF. Context frequency pre-filtered by a count sketch (>= HOT).
    evidence: only CONFLICTED claims count (>= 2 claimant sources, >= 2 distinct values); agreement-only claims
              say nothing about relative reliability.  A source with < MIN_EV conflicted claims has no reliability
              row (ABSENT evidence -> trust 1: a novel source that shares no claims is not judged).
    TD      : truth_c = reliability-weighted vote (a tie decides nothing); r_s = (agree+1)/(n+2); 10 iterations.
    trust   : t_s = clip(r_s / max_r, T_MIN, 1)."""
    K, HOT, MIN_N, SELF, MIN_EV, NB = 5, 20, 3, 0.8, 10, 4194301

    def __init__(self):
        self.sketch = torch.zeros(self.NB, dtype=torch.int32)
        self.claims = {}
        self.t = torch.ones(len(AREAS))
        self.r = {}
        self.log = []
        self.first = {}

    @torch.no_grad()
    def observe_bytes(self, b, lab, step):
        K, N = self.K, len(b)
        h = torch.zeros(N - K, dtype=torch.long)
        same = torch.ones(N - K, dtype=torch.bool)
        for i in range(K):
            h = h * 257 + b[i:N - K + i]
            same &= lab[i:N - K + i] == lab[K:]
        nxt, src = b[K:], lab[K:]
        hb = h % self.NB
        self.sketch.index_add_(0, hb[same], torch.ones(int(same.sum()), dtype=torch.int32))
        hot = same & (self.sketch[hb] >= self.HOT)
        for c, s_, v in zip(h[hot].tolist(), src[hot].tolist(), nxt[hot].tolist()):
            d = self.claims.setdefault(c, {}).setdefault(s_, {})
            d[v] = d.get(v, 0) + 1
        for a in src.unique().tolist():
            self.first.setdefault(a, step)
        if step % 10 == 0:
            self.update(step)

    def update(self, step):
        conf = []   # list of {src: value}
        for c, d in self.claims.items():
            cl = {}
            for s_, cnts in d.items():
                n = sum(cnts.values())
                if n >= self.MIN_N:
                    v, k = max(cnts.items(), key=lambda kv: kv[1])
                    if k / n >= self.SELF:
                        cl[s_] = v
            if len(cl) >= 2 and len(set(cl.values())) >= 2:
                conf.append(cl)
        cnt("td.updates")
        if not conf:
            return
        cnt("td.conflicted_seen")
        r = {s_: 1.0 for cl in conf for s_ in cl}
        for _ in range(10):
            ag = {s_: [0, 0] for s_ in r}
            for cl in conf:
                vote = {}
                for s_, v in cl.items():
                    vote[v] = vote.get(v, 0.0) + r[s_]
                best = sorted(vote.values(), reverse=True)
                if len(best) > 1 and abs(best[0] - best[1]) < 1e-9:
                    continue          # a tie decides nothing
                tv = max(vote.items(), key=lambda kv: kv[1])[0]
                for s_, v in cl.items():
                    ag[s_][0] += v == tv; ag[s_][1] += 1
            r = {s_: (a + 1) / (n + 2) for s_, (a, n) in ag.items()}
            nev = {s_: n for s_, (a, n) in ag.items()}
        self.r = r
        ev = {s_: r[s_] for s_ in r if nev[s_] >= self.MIN_EV}
        if len(ev) >= 2:
            mx = max(ev.values())
            for s_, v in ev.items():
                new = min(1.0, max(args.t_min, v / mx))
                if new < 1.0:
                    cnt("trust.actuations")
                if new <= args.t_min + 1e-9:
                    cnt("trust.floor_binds")
                self.t[s_] = new
        if step % 100 == 0:
            self.log.append({"step": step, "n_conflicted": len(conf), "n_claim_ctx": len(self.claims),
                             "r": {AREAS[s_]: round(v, 3) for s_, v in r.items()},
                             "n_ev": {AREAS[s_]: n for s_, n in nev.items()},
                             "trust": {AREAS[i]: round(float(self.t[i]), 3) for i in range(len(AREAS))}})


SPANS = None


def phase_of(step):
    pos = step * BATCH * CTX
    return max(i for i in range(4) if SPANS[i][0] <= pos)


def run(seed, total):
    global SPANS
    torch.manual_seed(seed)
    world = tb.World(seed)
    if FOCUS:
        policy = FocusPolicy()
    elif REPLAY:
        policy = ReplayFixed()
    else:
        policy = tb.PlannedPolicy()
    st = (D3Stream if (FOCUS or REPLAY) else tb.Stream)(seed, total, policy, world, 0.0, "off")
    if MF:
        st.gens["corrob"] = LyingCorrob("corrob", seed, world)
    SPANS = st.spans
    ho = tb.Heldout(seed, world)
    model = tb.LM()
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.0)
    lr = 3e-3
    n_win = (total - 1) // CTX
    n_steps = n_win // BATCH
    warm = 30
    sched = lambda t: min(1.0, (t + 1) / warm) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1.0, t / n_steps))))
    probe = Probe(seed, world, args.probe_n) if FOCUS else None
    trust = Trust() if TRUST else (ClaimTD() if CLAIM_TD else None)
    TRUST_OBJ[0] = trust
    prev_theta, prev_L, prev_P, kappa, mir_log = None, None, {}, None, []
    evals, books = [], {n: {"tok": 0, "nats": 0.0, "w": 0.0} for n in AREAS}
    phase_books = [{n: {"tok": 0, "nats": 0.0, "w": 0.0} for n in AREAS} for _ in range(4)]
    eval_at = sorted(set([round(n_steps * k / 8) for k in range(1, 9)] + [round(n_steps * k / 4) for k in (1, 2, 3)]))
    trust_at_eval = []
    t0, t_probe, t_trust = time.time(), 0.0, 0.0
    logf = open(os.path.join(HERE, "logs", f"{arm}{args.tag}_s{seed}.log"), "w")
    for step in range(n_steps):
        lo_b = step * BATCH * CTX
        st.fill(lo_b + BATCH * CTX + 1)
        xs = torch.tensor(list(st.buf[lo_b:lo_b + BATCH * CTX + 1]), dtype=torch.long)
        idx = torch.arange(BATCH)[:, None] * CTX + torch.arange(CTX + 1)[None, :]
        x = xs[idx]
        lab = torch.tensor(st.lab[lo_b:lo_b + BATCH * CTX + 1])[idx][:, 1:]
        for g in opt.param_groups:
            g["lr"] = lr * sched(step)
        logits = model(x[:, :-1], None)
        nats = F.cross_entropy(logits.reshape(-1, 256), x[:, 1:].reshape(-1), reduction="none").view(BATCH, CTX)
        w = None
        if trust is not None:
            t1 = time.time()
            if CLAIM_TD:
                trust.observe_bytes(xs, torch.tensor(st.lab[lo_b:lo_b + BATCH * CTX + 1]), step)
            else:
                trust.observe(logits.detach(), x[:, 1:], lab, step)
            if float(trust.t.min()) < 1.0:
                w = trust.t[lab]
                w = w / w.mean()
                cnt("trust.weighted_batches")
            t_trust += time.time() - t1
        loss = (nats * w).mean() if w is not None else nats.mean()
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        ww = w if w is not None else torch.ones_like(nats)
        ph = min(3, max(i for i in range(4) if st.spans[i][0] <= lo_b))
        for a in lab.unique().tolist():
            m = lab == a
            for bk in (books, phase_books[ph]):
                bk[AREAS[a]]["tok"] += int(m.sum()); bk[AREAS[a]]["nats"] += float(nats.detach()[m].sum())
                bk[AREAS[a]]["w"] += float(ww[m].sum())
        if probe is not None and (step + 1) % args.probe_every == 0:
            t1 = time.time()
            model.eval()
            seen = [a for a in AREAS if a in policy.ever]
            L = probe.losses(model, seen)
            R = {}
            theta = torch.cat([p.detach().reshape(-1) for p in model.parameters()])
            live = [a for a in PHASES[policy.phase] if a in seen]
            faded = [a for a in seen if a not in PHASES[policy.phase]]
            if MIR and prev_L is not None:
                # calibrate the virtual step on LIVE areas: realized change over the last interval / predicted
                lv_ = [a for a in live if a in prev_P and a in prev_L]
                if lv_:
                    real = sum(L[a] - prev_L[a] for a in lv_); pred = sum(prev_P[a] for a in lv_)
                    if pred < 0:
                        k_new = max(0.0, real / pred)
                        kappa = k_new if kappa is None else kappa + 0.1 * (k_new - kappa)
                        cnt("focus.mir_calibrations")
            prev_P = {}
            if MIR and prev_theta is not None:
                cnt("focus.mir_evals")
                s = float((theta - prev_theta).norm())
                eps = 0.01 * s   # small finite-difference step: D_a = directional derivative along the live descent
                sh = policy.shares
                wts = torch.tensor([sh.get(a, 0.0) for a in live])
                wts = wts / wts.sum()
                lv = probe.loss(model, live)
                g = torch.autograd.grad((lv * wts).sum(), list(model.parameters()), allow_unused=True)
                g = [torch.zeros_like(p) if gi is None else gi for p, gi in zip(model.parameters(), g)]
                gn = torch.sqrt(sum((gi ** 2).sum() for gi in g))
                with torch.no_grad():
                    for p, gi in zip(model.parameters(), g):
                        p.sub_(eps * gi / gn)
                    L2_ = probe.losses(model, seen)
                    for p, gi in zip(model.parameters(), g):
                        p.add_(eps * gi / gn)
                D = {a: (L2_[a] - L[a]) / eps for a in seen}
                prev_P = {a: D[a] for a in live}
                R = {a: (kappa or 0.0) * D[a] for a in faded}   # calibrated: predicted bits/byte change next interval
                mir_log.append({"step": step + 1, "kappa": kappa, "D": {a: round(v, 5) for a, v in D.items()},
                                "R": {a: round(v, 5) for a, v in R.items()}})
            prev_theta = theta
            prev_L = L
            model.train()
            policy.replan(step + 1, L, R)
            t_probe += time.time() - t1
        if step + 1 in eval_at:
            r, _ = tb.evaluate(model, ho, world, False)
            r["step"] = step + 1; r["frac"] = (step + 1) / n_steps; r["wall"] = time.time() - t0
            evals.append(r)
            if trust is not None:
                trust_at_eval.append({"frac": r["frac"], "trust": {AREAS[i]: round(float(trust.t[i]), 3) for i in range(len(AREAS))}})
            print(f"[{seed}] step {step+1}/{n_steps} {time.time()-t0:.0f}s " +
                  " ".join(f"{n}:{r['heldout'][n]['null']:.2f}" for n in AREAS) +
                  (f" | shares {policy.shares}" if FOCUS or REPLAY else "") +
                  (f" | trust {[round(float(v),2) for v in trust.t]}" if trust is not None else ""), file=logf, flush=True)
    _, probs = tb.evaluate(model, ho, world, False)
    res = {"evals": evals, "books": books, "phase_books": phase_books, "drawn": st.drawn, "n_steps": n_steps,
           "segments": st.n_segments, "wall": time.time() - t0, "world": world, "probs": probs, "model": model}
    res["mir_log"] = mir_log
    return res, policy, trust, trust_at_eval, t_probe, t_trust


if args.check:
    # determinism check: this file's loop on the base path vs testbed.train, same seed/bytes
    res, *_ = run(args.seed, args.bytes)
    ref = tb.train(args.seed, args.bytes)
    a = tb.summarize(res)["bpb_end_null"]; b = tb.summarize(ref)["bpb_end_null"]
    print("mine", a); print("testbed", b); print("IDENTICAL" if a == b else "DIFFERENT")
    sys.exit(0)

res, policy, trust, trust_at_eval, t_probe, t_trust = run(args.seed, args.bytes)
summ = tb.summarize(res)
summ.update({"arm": arm, "seed": args.seed, "bytes": args.bytes, "wall": res["wall"], "wall_probe": t_probe,
             "wall_trust": t_trust, "n_steps": res["n_steps"], "segments": res["segments"], "counters": C,
             "args": vars(args)})
summ["curve"] = [{"frac": r["frac"], "null": {n: r["heldout"][n]["null"] for n in AREAS},
                  "Qc_acc_true_null_c": r["facts"]["null_c"]["Qc"]["acc_true"],
                  "Wc_acc_true_null_c": r["facts"]["null_c"]["Wc"]["acc_true"]} for r in res["evals"]]
summ["phase_drawn_share"] = [{n: pb[n]["tok"] / max(1, sum(v["tok"] for v in pb.values())) for n in AREAS}
                             for pb in res["phase_books"]]
if isinstance(policy, FocusPolicy):
    lg = policy.log
    summ["focus_log_sample"] = lg[:: max(1, len(lg) // 25)]
    summ["mir_log_sample"] = res["mir_log"][:: max(1, len(res["mir_log"]) // 15)]
    summ["rho_by_phase"] = [statistics.mean([r["rho"] for r in lg if r["phase"] == k] or [0.0]) for k in range(4)]
if trust is not None:
    summ["trust_at_eval"] = trust_at_eval
    summ["trust_log"] = trust.log
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
json.dump(summ, open(os.path.join(HERE, "out", f"{arm}{args.tag}_s{args.seed}.json"), "w"), indent=1, default=str)
print(json.dumps({k: summ[k] for k in ("arm", "seed", "wall", "gap_end", "forget_hard", "forget_easy", "drawn_share", "counters")}, default=str))
