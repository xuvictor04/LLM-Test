"""growth.py -- self-regulating fabric population (replaces fixed-threshold spawn/prune).

Population dynamics that find their own equilibrium, with NO fixed loss target and NO fixed usage
floor (both of which require knowing the loss scale in advance and cause grow/prune sawtooth):

  SPAWN   on a PLATEAU -- loss stopped improving, detected by fast-vs-slow EMA (scale-free, works
          in byte or token mode without retuning). By DEFAULT it grows on any plateau, even if some
          experts are idle (set require_balance=True to only grow when load is balanced).
  PRUNE   DEFAULT OFF -- the system is biased to keep growing and never cull. (When enabled, prunes an
          expert that is OLD, past GRACE, and persistently under-used relative to the others.)
  GRACE   protects a newborn from pruning for `grace` steps (only relevant when prune is enabled).
  DEPTH   when breadth is saturated (at nmax) and still plateaued, grow a layer instead of a node.

Net behavior (default): capacity is added whenever progress stalls, even if the loss is already good,
and nodes are never removed -- the population grows toward nmax (then depth, if enabled). Set prune=True
for the older self-settling turnover dynamics. The population size is an OUTCOME of the growth pressure.
"""


class GrowthController:
    def __init__(self, n_init, nmax=16, minn=2, max_layers=None, n_layers=None,
                 grace=400, patience=400, rel_improve=0.01, prune_frac=0.25,
                 cooldown=150, af=0.05, aslow=0.01, prune=False, require_balance=False):
        self.nmax, self.minn = nmax, minn
        self.max_layers, self.n_layers = max_layers, n_layers
        self.grace, self.patience, self.rel_improve = grace, patience, rel_improve
        self.prune_frac, self.cooldown = prune_frac, cooldown
        self.af, self.aslow = af, aslow
        self.prune = prune                      # OFF by default: bias toward growth, never cull nodes
        self.require_balance = require_balance   # OFF by default: spawn on any plateau, even if load uneven
        self.age = [10 ** 9] * n_init           # initial nodes count as mature (not in grace)
        self.fast = self.slow = None
        self.since_improve = 0
        self.last_change = -10 ** 9

    # lifecycle hooks (keep age[] aligned with the model's expert list)
    def on_spawn(self): self.age.append(0)      # newborn: grace clock starts at 0
    def on_prune(self, i): self.age.pop(i)
    def on_depth(self): self.n_layers = (self.n_layers or 0) + 1

    def decide(self, g, loss_val, usage):
        """Call every training step with the step's raw train-CE and the per-expert usage EMAs.
        Returns None | ('spawn', None) | ('prune', idx) | ('depth', None)."""
        for k in range(len(self.age)): self.age[k] += 1
        self.fast = loss_val if self.fast is None else (1 - self.af) * self.fast + self.af * loss_val
        self.slow = loss_val if self.slow is None else (1 - self.aslow) * self.slow + self.aslow * loss_val
        improving = self.fast < self.slow * (1 - self.rel_improve)   # fast still dropping below slow
        self.since_improve = 0 if improving else self.since_improve + 1

        n = len(usage)
        if g - self.last_change < self.cooldown:
            return None
        mean_u = sum(usage) / max(1, n)

        # PRUNE (default OFF -- the system is biased to grow, not cull): an OLD, relatively-idle expert
        if self.prune and n > self.minn and mean_u > 0:
            cand = [(usage[i], i) for i in range(n)
                    if self.age[i] > self.grace and usage[i] < self.prune_frac * mean_u]
            if cand:
                self.last_change = g
                return ('prune', min(cand)[1])

        if self.since_improve < self.patience:      # still learning -> don't add capacity
            return None

        # SPAWN breadth on a PLATEAU. Default grows whenever stagnating (even if every node is idle);
        # set require_balance=True to only grow when existing nodes are all pulling weight.
        if n < self.nmax:
            if (not self.require_balance) or mean_u <= 0 or min(usage) > 0.5 * mean_u:
                self.since_improve = 0; self.last_change = g
                return ('spawn', None)
            return None

        # breadth saturated -> grow DEPTH instead
        if self.max_layers and self.n_layers is not None and self.n_layers < self.max_layers:
            self.since_improve = 0; self.last_change = g
            return ('depth', None)
        return None
