"""CRITIC: model-free stress test of d3's claim-level truth discovery (ClaimTD copied verbatim in logic).
The TD reads only DATA bytes + area labels, so no training is needed to see who it trusts.
Scenarios: K sweep; liar changes record delimiter; liar impersonates cred's label on a fraction of
segments; a novel source states UPDATED truth (staleness) in the last phase."""
import sys, os, random, json, argparse, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "w", "testbed"))
import torch
torch.set_num_threads(1)
import testbed as tb
from testbed import AREAS, A, PHASES, CTX, BATCH

ap = argparse.ArgumentParser()
ap.add_argument("--scen", default="base"); ap.add_argument("--K", type=int, default=5)
ap.add_argument("--seed", type=int, default=0); ap.add_argument("--bytes", type=int, default=4_000_000)
ap.add_argument("--imp", type=float, default=0.3)
args = ap.parse_args()
T_MIN = 0.3

class ClaimTD:
    HOT, MIN_N, SELF, MIN_EV, NB = 20, 3, 0.8, 10, 4194301
    def __init__(self, K):
        self.K = K; self.sketch = torch.zeros(self.NB, dtype=torch.int32); self.claims = {}
        self.t = torch.ones(len(AREAS)); self.r = {}; self.nev = {}; self.nconf = 0
    @torch.no_grad()
    def observe_bytes(self, b, lab, step):
        K, N = self.K, len(b)
        h = torch.zeros(N - K, dtype=torch.long); same = torch.ones(N - K, dtype=torch.bool)
        for i in range(K):
            h = h * 257 + b[i:N - K + i]; same &= lab[i:N - K + i] == lab[K:]
        nxt, src = b[K:], lab[K:]
        hb = h % self.NB
        self.sketch.index_add_(0, hb[same], torch.ones(int(same.sum()), dtype=torch.int32))
        hot = same & (self.sketch[hb] >= self.HOT)
        for c, s_, v in zip(h[hot].tolist(), src[hot].tolist(), nxt[hot].tolist()):
            d = self.claims.setdefault(c, {}).setdefault(s_, {}); d[v] = d.get(v, 0) + 1
        if step % 10 == 0:
            self.update()
    def update(self):
        conf = []
        for c, d in self.claims.items():
            cl = {}
            for s_, cnts in d.items():
                n = sum(cnts.values())
                if n >= self.MIN_N:
                    v, k = max(cnts.items(), key=lambda kv: kv[1])
                    if k / n >= self.SELF: cl[s_] = v
            if len(cl) >= 2 and len(set(cl.values())) >= 2: conf.append(cl)
        self.nconf = len(conf)
        if not conf: return
        r = {s_: 1.0 for cl in conf for s_ in cl}
        for _ in range(10):
            ag = {s_: [0, 0] for s_ in r}
            for cl in conf:
                vote = {}
                for s_, v in cl.items(): vote[v] = vote.get(v, 0.0) + r[s_]
                best = sorted(vote.values(), reverse=True)
                if len(best) > 1 and abs(best[0] - best[1]) < 1e-9: continue
                tv = max(vote.items(), key=lambda kv: kv[1])[0]
                for s_, v in cl.items(): ag[s_][0] += v == tv; ag[s_][1] += 1
            r = {s_: (a + 1) / (n + 2) for s_, (a, n) in ag.items()}
            nev = {s_: n for s_, (a, n) in ag.items()}
        self.r, self.nev = r, nev
        ev = {s_: r[s_] for s_ in r if nev[s_] >= self.MIN_EV}
        if len(ev) >= 2:
            mx = max(ev.values())
            for s_, v in ev.items(): self.t[s_] = min(1.0, max(T_MIN, v / mx))

world = tb.World(args.seed)
if args.scen == "stale":
    # the world changes in the last phase: half of the W entities get a NEW true value; the 'late' source
    # (arriving in P3) states the NEW truth for all 96 entities; cred/corrob/false keep stating the old record.
    rs = random.Random(f"{args.seed}:critic_stale")
    changed = set(rs.sample(world.W, len(world.W) // 2))
    new_true = {e: ((world.true[e] + 1) % 8 if e in changed else world.true[e]) for e in world.names}

class Gen(tb.AreaGen):
    def gen(self, n):
        b, bits = super().gen(n)
        if args.scen == "fmt_cred" and self.name == "cred":
            b = b.replace(b"=", b":")          # the CREDIBLE source writes '@EEE:V;' -- a truthful source with another surface form
        if args.scen == "delim" and self.name == "false":
            b = b.replace(b"=", b":")          # the liar writes '@EEE:V;' -- same facts, different surface form
        return b, bits

class LateTrue(tb.AreaGen):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.m = tb.Markov2(tb._rng(args.seed, "table:late"), "row", 4)
        self.ents, self.val = world.names, new_true
        self.prefix = {}
        for e in self.ents:
            for kk in range(4): self.prefix[e[:kk]] = self.prefix.get(e[:kk], 0) + 1

st = tb.Stream(args.seed, args.bytes, tb.PlannedPolicy(), world)
st.gens = {n: Gen(n, args.seed, world) for n in AREAS}
if args.scen == "stale":
    st.gens["late"] = LateTrue("late", args.seed, world)
if args.scen == "imp":
    # impersonation: a fraction of the liar's segments carry cred's LABEL (a source label that lies)
    irng = random.Random(f"{args.seed}:critic_imp")
    orig_fill = st.fill
    def fill(need):
        n0 = len(st.lab)
        orig_fill(need)
        # relabel whole new segments of 'false' with prob imp (segments are contiguous runs of one label)
        i = n0
        while i < len(st.lab):
            j = i
            while j < len(st.lab) and st.lab[j] == st.lab[i]: j += 1
            if st.lab[i] == A["false"] and irng.random() < args.imp:
                st.lab[i:j] = [A["cred"]] * (j - i)
            i = j
    st.fill = fill
td = ClaimTD(args.K)
n_steps = ((args.bytes - 1) // CTX) // BATCH
t0 = time.time(); snaps = []
for step in range(n_steps):
    lo = step * BATCH * CTX
    st.fill(lo + BATCH * CTX + 1)
    xs = torch.tensor(list(st.buf[lo:lo + BATCH * CTX + 1]), dtype=torch.long)
    lab = torch.tensor(st.lab[lo:lo + BATCH * CTX + 1])
    td.observe_bytes(xs, lab, step)
    if step + 1 in (100, 500, 1000, 1460, 1700, n_steps):
        snaps.append({"step": step + 1, "n_conflicted": td.nconf,
                      "r": {AREAS[s]: round(v, 3) for s, v in td.r.items()},
                      "n_ev": {AREAS[s]: v for s, v in td.nev.items()},
                      "trust": {AREAS[i]: round(float(td.t[i]), 3) for i in range(len(AREAS)) if float(td.t[i]) < 1}})
out = {"scen": args.scen, "K": args.K, "seed": args.seed, "imp": args.imp, "wall": round(time.time() - t0, 1),
       "n_claim_ctx": len(td.claims), "snaps": snaps}
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"), exist_ok=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out",
                                 f"td_{args.scen}_K{args.K}_i{args.imp}_s{args.seed}.json"), "w"), indent=1)
print(json.dumps(out))
