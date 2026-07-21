"""Short-term working memory for Greg as a KNOWLEDGE GRAPH in folder-path form, with a
consolidation pass that bridges short-term (this file system) and long-term (the weights).

Memory hierarchy:
  - long-term  = model weights (knowledge baked in by training) + persistent knowledge maps
  - short-term = this recency-decayed KG of "what I'm doing now" (triples -> folder paths)
  - bridge     = consolidate(): REVIEW short-term, then DISCARD weak / PROMOTE strong to long-term

Soft (saturating) strength cap replaces a hard floor: reinforcement has diminishing returns, idle
facts decay, and the review pass -- not an arbitrary threshold -- decides what survives.
"""
import math
from collections import defaultdict


class WorkingMemoryKG:
    def __init__(self, capacity=48, half_life=10, soft_cap=3.0):
        self.capacity = capacity
        self.k = math.log(2) / half_life
        self.soft_cap = soft_cap
        self.t = 0
        self.facts = {}                  # (s,r,o) -> [raw_strength, last_t]
        self.adj = defaultdict(set)
        self.longterm = {}               # consolidated store (stand-in for weights / persistent map)

    def _raw_now(self, key):
        raw, lt = self.facts[key]
        return raw * math.exp(-self.k * (self.t - lt))

    def _eff(self, key):
        # saturating cap: diminishing returns toward soft_cap, then recency-decayed
        return self.soft_cap * (1.0 - math.exp(-self._raw_now(key) / self.soft_cap))

    def add(self, s, r, o, w=1.0):
        self.t += 1
        key = (s, r, o)
        raw = (self._raw_now(key) + w) if key in self.facts else w
        self.facts[key] = [raw, self.t]
        self.adj[s].add((r, o)); self.adj[o].add(("inv_" + r, s))
        self._evict()

    def _evict(self):
        if len(self.facts) <= self.capacity:
            return
        for key in sorted(self.facts, key=self._eff)[: len(self.facts) - self.capacity]:
            s, r, o = key; del self.facts[key]
            self.adj[s].discard((r, o)); self.adj[o].discard(("inv_" + r, s))

    def consolidate(self, promote=1.6, discard=0.35):
        """Review pass: strong facts -> long-term (would be replayed into weights), weak -> forgotten,
        mid-strength -> stay in short-term for now. Returns the three buckets."""
        promoted, discarded, kept = [], [], []
        for key in list(self.facts):
            e = self._eff(key)
            if e >= promote:
                self.longterm[key] = self.longterm.get(key, 0.0) + e
                promoted.append(key); self._drop(key)
            elif e <= discard:
                discarded.append(key); self._drop(key)
            else:
                kept.append(key)
        return promoted, discarded, kept

    def _drop(self, key):
        s, r, o = key; del self.facts[key]
        self.adj[s].discard((r, o)); self.adj[o].discard(("inv_" + r, s))

    def query(self, subject):
        out = [(r, o, round(self._eff((subject, r, o)), 3)) for (s, r, o) in self.facts if s == subject]
        return sorted(out, key=lambda x: -x[2])

    def neighbors(self, node): return sorted(self.adj.get(node, ()))

    def render_tree(self, top=18):
        tree = defaultdict(lambda: defaultdict(list))
        for key in sorted(self.facts, key=self._eff, reverse=True)[:top]:
            s, r, o = key; tree[s][r].append((o, self._eff(key)))
        lines = []
        for s in tree:
            lines.append(s + "/")
            for r in tree[s]:
                lines.append(f"  {r}/")
                for o, st in sorted(tree[s][r], key=lambda x: -x[1]):
                    lines.append(f"    {o}   \u00b7{st:.2f}")
        return "\n".join(lines)

    def context_summary(self, top=6):
        return "; ".join(f"{s} {r} {o}" for (s, r, o) in sorted(self.facts, key=self._eff, reverse=True)[:top])


if __name__ == "__main__":
    wm = WorkingMemoryKG(capacity=48, half_life=10, soft_cap=3.0)
    # eng gets revisited a lot (strong), py a little (mid), a one-off OOD spike (weak after decay)
    base = [("eng", "routed_to", "expert_0"), ("expert_0", "specializes", "eng")]
    for _ in range(6):
        for s, r, o in base: wm.add(s, r, o)
    for s, r, o in [("py", "routed_to", "expert_1"), ("expert_1", "specializes", "py")]:
        wm.add(s, r, o); wm.add(s, r, o)
    wm.add("code_OOD", "novelty", "very_high")            # one-off
    for _ in range(15):                                  # attention moves on -> OOD decays
        wm.add("eng", "routed_to", "expert_0")

    print("=== short-term KG before review ===")
    print(wm.render_tree())
    print("\nsoft cap check (eng/routed_to/expert_0 reinforced 21x):",
          round(wm._eff(("eng", "routed_to", "expert_0")), 3), f"<= soft_cap {wm.soft_cap}")

    promoted, discarded, kept = wm.consolidate()
    print("\n=== consolidation (review -> discard / promote) ===")
    print("PROMOTED to long-term:", [f"{s}/{r}/{o}" for s, r, o in promoted])
    print("DISCARDED (forgotten):", [f"{s}/{r}/{o}" for s, r, o in discarded])
    print("KEPT in short-term:   ", [f"{s}/{r}/{o}" for s, r, o in kept])
    print("\nlong-term store now holds:", {f"{s}/{r}/{o}": round(v, 2) for (s, r, o), v in wm.longterm.items()})
    print(f"short-term facts remaining: {len(wm.facts)}")
