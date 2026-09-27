"""FABRIC INTERNALS: the selection pass, the shift stamp, the row events, the AE rows and HALT, driven.

Every check here stands over a defect that shipped and was measured on a real run before it was
repaired on 2026-09-24. Each builds a real population from a real assemble.build over a dict
environment at test widths, drives the entry point, and asserts what the repair promises. Run from the
repository root as `python3 tests/test_fabric_internals.py`; exit 0 = every check passed.

  I1  FAB.manage's failure cull judged "above the population" against the mean ef/es over EVERY live
      expert, never-selected zeros included, so every past-grace expert cleared the bar (11 of 13 at
      window 1001 of a default run). The baseline is comp_glob (Q-FAB-12): an expert under
      comp_glob + FAB_FAIL_TOL survives however many zeros sit in the population, one above it is
      culled, and the fabric.cull_eligible gate carries the ENTRY count, so a pass that culled every
      eligible expert does not print 'unreachable'.
  I2  the comp_protect spare compared `comp > comp_glob` -- comp is a LOSS, so it spared the WORSE
      experts. Under an open gate with a nonzero budget, the better-than-population expert is spared.
  I3  FAB_DEPTH_STAGE_MAX was read only as a depth ceiling. On a falling loss depth now advances after
      stage_max checks (fab.depth_forced counts it), and a stage_max below FAB_HOPS no longer caps depth.
  I4  one epoch roll's stamp was counted once per flush by FAB (158) and never reached OPT. Both now
      count one notification per distinct stamp, and FAB keeps the stamp so the blackout survives a
      caller that passes None (a resumed root).
  I5  _remove / _claim_slot rewrote rows of A and B and nothing moved AdamW's moments. The row events
      reach OPT.remap_rows through FabricOut.row_events: a moved expert carries its own exp_avg and
      exp_avg_sq, a cleared or re-born slot has zero state, and an accumulated .grad row moves too.
  I6  the identity round trip scored A[:256], a fixed prefix. The rotating block covers every live row
      in ceil(n / 256) passes and is exactly rows 0..n-1 at n <= 256.
  I7  HALT's column competed with the population's summed mass, so its share fell with log(n). The
      halt logit now carries +log(n) (Q-FAB-14): exactly the old column at n = 1.
  I8  the build-time fab.cull_gate read FIRED before any manage pass had run. At build it and the new
      fab.depth_advance are UNREACHABLE predictions, and a manage pass replaces both.
  I9  the roll stamped OPT's shift at the steps already taken, one short of the step it applies to,
      so OPT_LR_SHIFT_WARM=1 re-warmed nothing. A two-epoch loop run at WARM=1 applies it once.
  I10 FAB.manage's merge scan read sim[i, j] one scalar at a time (n^2/2 device syncs), which held
      the 2026-09-24 GPU fleet at ~2.5 windows/s per run from window 501 on. _merge_pairs is one
      tensor pass and must return the scalar loop's list EXACTLY -- same floats, same order, same
      tie-breaks -- on random, clustered, tied and exactly-at-threshold similarity matrices.
  I11 the blackout had pass counters and no WINDOWS count, so a quiet loss inside it read 0 however
      long it held growth off (2026-09-26, Q-RUN-17). fab.blackout_windows credits the windows each
      check that finds it open covers -- one per check at batch 1, the whole flush above it, never
      a window before the stamp, counted from the stamp when a checkpoint carries no previous
      check -- and is ABSENT at FAB_GROW=0 and FAB_COOLDOWN=0, where no stamp can block growth.
  I12 FAB_NORM_ONLY=1 merged, culled and grew (Proposal 05 §8 1.6, register LOW-FAB_NORM_ONLY-GROWS):
      manage and grow_check tested fab.on alone. On inputs that merge one pair and grow one expert
      at FAB_NORM_ONLY=0, the norm-only arm now does neither, both families are ABSENT, the build
      gates read UNREACHABLE naming the lever (and still do after a restore), and fab.births /
      fab.rescued are ABSENT.
  I13 gate:fab.merged PRINTED THE RUN TOTAL BESIDE THE LAST PASS'S VERDICT (register
      LOW-FAB-MERGED-REPORT): after a pass that merges one pair and one that merges none, the run
      gate FIRES with count 1 and gate:fab.merged_last_pass reads armed-but-zero at 0; with nothing
      past grace both are UNREACHABLE at 0, and at FAB_MERGE_DIST=0 both say off by configuration.

WHAT THIS FILE CANNOT CATCH: whether the new baselines make a LONG run better. That is a GPU-length
measurement the owner runs; these checks pin the arithmetic each repair promises.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import torch                                                            # noqa: E402

from spine import assemble                                              # noqa: E402
from spine import lever                                                 # noqa: E402
from spine import rng                                                   # noqa: E402
from spine import units as U                                            # noqa: E402

from fabric import api as FAB                                           # noqa: E402
from opt import api as OPT                                              # noqa: E402

torch.set_num_threads(1)

D_MODEL, SIG_D, BATCH, LEN = 16, 12, 2, 4
BASE = {"RUN_SEED": "7", "RUN_DEVICE": "cpu", "FAB_N0": "6", "FAB_SLOTS": "12"}


def _report(tag, title, ok, detail, findings):
    print(f"{'PASS' if ok else 'FAIL'}  {tag}  {title}")
    print(f"      {detail}")
    for f in findings[:12]:
        print(f"      - {f}")
    return 0 if ok else 1


def cfg(**env):
    """A real, frozen Config set from assemble.build over a dict environment (never os.environ)."""
    lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    configs, _wires, warnings = assemble.build(e)
    if warnings:
        raise AssertionError(f"assemble.build warned on {e}: {warnings}")
    return configs


def population(c, seed=1234):
    """A fresh population on the fabric stream. again=True because several checks build a second
    population from one Config, which is a deliberate rebuild and not a second consumer."""
    return FAB.build(c["FAB"], d_model=D_MODEL, signature_dim=SIG_D,
                     device=torch.device("cpu"), generator=rng.rng_for("fabric", seed, again=True))


def gate(pop, name):
    got = [g for g in pop.gates if g.name == name]
    return got[0] if got else None


def draw(seed=5):
    g = torch.Generator().manual_seed(seed)
    h = torch.randn(BATCH, LEN, D_MODEL, generator=g)
    s = torch.randn(BATCH, SIG_D, generator=g)
    s = s / s.norm(dim=-1, keepdim=True)
    return h, s, torch.rand(BATCH, generator=g)


def forward(c, pop, step=1):
    h, s, nov = draw(step)
    return FAB.forward(c["FAB"], pop, h=h, signature=s, novelty=nov, step_windows=U.Windows(step),
                       domain_id=0, live_domains=1, training=True)


# ==================================================================================================

def check_i1_failure_cull_baseline():
    c = cfg(FAB_GRACE=1, FAB_MERGE_DIST=0, FAB_PRESSURE=0.99)
    pop = population(c)
    n = int(pop.n_live)
    pop.comp_glob = 4.0
    for i in range(n):                      # half never selected: ef = es = 0.0, "never attributed"
        pop.uage[i], pop.ef[i], pop.es[i], pop.comp[i] = 0, 0.0, 0.0, 0.0
    # expert 0: selected, BELOW comp_glob + tol -- the mean over all live would have culled it
    # expert 1: selected, above comp_glob + tol on both EMAs and not adapting -- failing
    pop.uage[0], pop.ef[0], pop.es[0], pop.comp[0] = 5, 4.05, 4.1, 4.08
    pop.uage[1], pop.ef[1], pop.es[1], pop.comp[1] = 5, 4.6, 4.7, 4.65
    all_mean = sum(float(pop.ef[i]) for i in range(n)) / n
    r = FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), flush_loss=None)
    findings = []
    if r.cull_fail != 1:
        findings.append(f"cull_fail={r.cull_fail}, want 1 (the expert at ef 4.6 against comp_glob 4.0 "
                        f"+ FAB_FAIL_TOL 0.15); the all-live mean here is {all_mean:.3f}, under which "
                        f"both selected experts would fail")
    if r.eligible != 2:
        findings.append(f"ManageReport.eligible={r.eligible}, want the ENTRY count 2")
    ce = gate(pop, "fabric.cull_eligible")
    if ce is None or not ce.reachable or int(ce.value) != 2:
        findings.append(f"fabric.cull_eligible is {ce.line() if ce else None!r}; with 2 eligible at "
                        f"entry it must be reachable with value 2 even after the pass culled one")
    # A pass that culls EVERY eligible expert must still not print 'unreachable'.
    pop2 = population(c)
    pop2.comp_glob = 1.0
    pop2.uage[0], pop2.ef[0], pop2.es[0] = 5, 4.6, 4.7
    FAB.manage(c["FAB"], pop2, step_windows=U.Windows(500), flush_loss=None)
    ce2, mg2 = gate(pop2, "fabric.cull_eligible"), gate(pop2, "fab.merged")
    if int(pop2.counters.get("fab.cull_fail", 0)) != 1 or ce2 is None or not ce2.reachable:
        findings.append(f"a pass that culled its one eligible expert printed "
                        f"{ce2.line() if ce2 else None!r} (fab.cull_fail="
                        f"{pop2.counters.get('fab.cull_fail')})")
    # comp_glob None: nothing attributed yet, so nothing is judged.
    pop3 = population(c)
    pop3.uage[0], pop3.ef[0], pop3.es[0] = 5, 9.0, 9.0
    r3 = FAB.manage(c["FAB"], pop3, step_windows=U.Windows(500), flush_loss=None)
    if r3.cull_fail:
        findings.append("comp_glob None (no window attributed) still culled an expert")
    return _report("I1", "the failure cull is judged against comp_glob, and the gates carry the entry "
                   "count", not findings,
                   f"population of {n}, {n - 2} never selected; all-live ef mean {all_mean:.3f} vs "
                   f"comp_glob 4.0; cull_fail {r.cull_fail}; eligible at entry {r.eligible}; "
                   f"merged gate on the all-culled pass: {mg2.line() if mg2 else None}", findings)


def check_i2_comp_protect_direction():
    c = cfg(FAB_GRACE=1, FAB_MERGE_DIST=0, FAB_PRESSURE=0.1, FAB_CULL_FRAC=1.0, FAB_FAIL_TOL=100)
    pop = population(c)
    n = int(pop.n_live)
    pop.comp_glob = 4.0
    for i in range(n):
        pop.uage[i], pop.use[i] = 5, float(i + 1)
        pop.ef[i] = pop.es[i] = 4.0
        pop.comp[i] = 5.0                  # every expert worse than the population ...
    pop.comp[0] = 3.0                      # ... except expert 0, the least used
    r = FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), flush_loss=None)
    findings = []
    if r.spared_comp < 1:
        findings.append(f"spared_comp={r.spared_comp}: expert 0 (comp 3.0 < comp_glob 4.0, lowest "
                        f"use) was not spared by comp_protect")
    if r.spared_comp > 1:
        findings.append(f"spared_comp={r.spared_comp}: experts WORSE than comp_glob were spared -- "
                        f"the inverted `>` test")
    return _report("I2", "comp_protect spares the expert better than the population, not the worse",
                   not findings, f"{n} eligible under an open gate, budget {int(1.0 * n)}; "
                   f"spared_comp {r.spared_comp}, cull_util {r.cull_util}", findings)


def check_i3_depth_stage_max_forces():
    findings, seen = [], []
    for stage_max, want_depth, want_forced in ((3, 4, 3), (1000, 1, 0)):
        c = cfg(FAB_DEPTH0=1, FAB_HOPS=4, FAB_DEPTH_PATIENCE=6, FAB_DEPTH_STAGE_MAX=stage_max,
                FAB_MERGE_DIST=0)
        pop = population(c)
        loss = 6.0
        for i in range(1, 13):
            FAB.manage(c["FAB"], pop, step_windows=U.Windows(i * 500), flush_loss=loss)
            loss -= 0.05                                    # a falling loss: no plateau ever
        d, f = int(pop.depth_now), int(pop.counters.get("fab.depth_forced", -1))
        seen.append(f"stage_max={stage_max}: depth {d}, forced {f}")
        if d != want_depth or f != want_forced:
            findings.append(f"FAB_DEPTH_STAGE_MAX={stage_max} on a falling loss over 12 checks: "
                            f"depth_now={d} fab.depth_forced={f}, want {want_depth}/{want_forced}")
        g = gate(pop, "fab.depth_advance")
        if g is None:
            findings.append("no fab.depth_advance gate after a manage pass")
    # a small stage_max on a FLAT loss must not cap depth below FAB_HOPS
    c = cfg(FAB_DEPTH0=1, FAB_HOPS=4, FAB_DEPTH_PATIENCE=6, FAB_DEPTH_STAGE_MAX=2, FAB_MERGE_DIST=0)
    pop = population(c)
    for i in range(1, 20):
        FAB.manage(c["FAB"], pop, step_windows=U.Windows(i * 500), flush_loss=5.0)
    if int(pop.depth_now) != 4:
        findings.append(f"flat loss at FAB_DEPTH_STAGE_MAX=2 left depth at {int(pop.depth_now)}, "
                        f"want FAB_HOPS=4 -- stage_max is not a depth cap")
    seen.append(f"flat stage_max=2: depth {int(pop.depth_now)}")
    return _report("I3", "FAB_DEPTH_STAGE_MAX ends a stage; it does not cap depth", not findings,
                   "; ".join(seen), findings)


def check_i4_shift_stamp_counted_once():
    c = cfg()
    pop = population(c)
    findings = []
    caps = type("Caps", (), {"experts": 10**6, "headroom": lambda self, n: 10**6})()
    sig = torch.zeros(SIG_D)
    for w in range(1, 6):
        FAB.grow_check(c["FAB"], pop, flush_loss=torch.tensor(5.0), step_windows=U.Windows(100 + w),
                       soft_cap=caps, memory_pressure=None, signature=sig,
                       shift_at=U.Windows(100))
    n1 = int(pop.counters.get("fab.shift_notifications", 0))
    r = FAB.grow_check(c["FAB"], pop, flush_loss=torch.tensor(5.0), step_windows=U.Windows(110),
                       soft_cap=caps, memory_pressure=None, signature=sig, shift_at=None)
    if n1 != 1:
        findings.append(f"one stamp re-delivered on 5 checks counted {n1} notifications, want 1")
    if not r.blackout_open:
        findings.append("a check with shift_at=None 10 windows after a stamp did not keep the "
                        "blackout the stamp opened (a resumed root holds no stamp)")
    # OPT: the same stamp twice is one notification, a new stamp is a second
    oc = c["OPT"]
    p = torch.nn.Parameter(torch.zeros(3))
    st = OPT.build(oc, param_groups={"base": [p], "encoder": []}, run_windows=U.Windows(100))
    for _ in range(3):
        st.n_backward = st.n_backward + U.Backwards(1)
        p.grad = torch.ones(3)
        OPT.maybe_step(oc, st, shift_at=U.Steps(0))
    st.n_backward = st.n_backward + U.Backwards(1)
    OPT.maybe_step(oc, st, shift_at=U.Steps(3))
    on = int(st.counters["opt.shift.notifications"])
    if on != 2:
        findings.append(f"OPT counted {on} notifications for two distinct stamps over four calls")
    return _report("I4", "a shift stamp is one notification however often it is re-delivered",
                   not findings, f"FAB {n1} for one stamp on 5 checks, blackout kept with None: "
                   f"{r.blackout_open}; OPT {on} for stamps 0,0,0,3", findings)


def check_i5_row_events_move_the_moments():
    c = cfg(FAB_SPAWN=0, FAB_GROW=0)
    pop = population(c)
    oc = c["OPT"]
    st = OPT.build(oc, param_groups={"base": pop.parameters(), "encoder": []},
                   run_windows=U.Windows(100))
    findings = []
    # one real step so every row of A and B has distinct, nonzero moments
    for p in (pop.A, pop.B):
        p.grad = torch.randn(p.shape, generator=torch.Generator().manual_seed(3))
    st.base.step()
    stA = st.base.state[pop.A]
    last = int(pop.n_live) - 1
    own_avg, own_sq = stA["exp_avg"][last].clone(), stA["exp_avg_sq"][last].clone()
    # an accumulated gradient (OPT_ACCUM > 1) that must follow the row too
    pop.A.grad = torch.randn(pop.A.shape, generator=torch.Generator().manual_seed(4))
    own_grad = pop.A.grad[last].clone()
    FAB._remove(pop, 1)                           # swap-with-last: expert `last` now lives at 1
    FAB._claim_slot(pop, last, 7)                 # and the slot it left is re-born
    out = forward(c, pop, step=7)
    ev = out.row_events
    kinds = [e[0] for e in (ev.events if ev is not None else ())]
    if kinds != ["move", "clear", "birth"]:
        findings.append(f"FabricOut.row_events carried {kinds}, want ['move', 'clear', 'birth']")
    OPT.remap_rows(oc, st, ev)
    if not torch.equal(stA["exp_avg"][1], own_avg) or not torch.equal(stA["exp_avg_sq"][1], own_sq):
        findings.append("the moved expert's slot does not hold its OWN moments after remap_rows")
    if not torch.equal(pop.A.grad[1], own_grad):
        findings.append("the moved expert's accumulated gradient did not follow it")
    if float(stA["exp_avg"][last].abs().max()) != 0.0 or float(stA["exp_avg_sq"][last].abs().max()) != 0.0:
        findings.append("the re-born slot kept the previous occupant's moments")
    if pop.row_events:
        findings.append(f"{len(pop.row_events)} event(s) left undrained after a training pass")
    # an eval pass must not swallow events
    FAB._remove(pop, 0)
    h, s, nov = draw(9)
    ev_out = FAB.forward(c["FAB"], pop, h=h, signature=s, novelty=nov, step_windows=U.Windows(8),
                         domain_id=0, live_domains=1, training=False)
    if ev_out.row_events is not None or not pop.row_events:
        findings.append("an eval pass drained the row events a training pass must hand over")
    rc = {k: st.counters.get(k) for k in ("opt.rows.moved", "opt.rows.cleared", "opt.rows.reborn")}
    if rc != {"opt.rows.moved": 1, "opt.rows.cleared": 1, "opt.rows.reborn": 1}:
        findings.append(f"remap counters {rc}")
    # A CHAIN: manage removes victims in DESCENDING order, so the last expert can move twice in one
    # pass (last -> a, then a is the new last -> b). The events are applied in order, so its state
    # must end at b.
    pop.row_events = []
    n = int(pop.n_live)
    tail = n - 1
    tail_avg = stA["exp_avg"][tail].clone()
    FAB._remove(pop, n - 2)              # tail -> n-2
    FAB._remove(pop, 0)                  # n-2 is now last -> 0
    OPT.remap_rows(oc, st, FAB._drain_row_events(pop))
    if not torch.equal(stA["exp_avg"][0], tail_avg):
        findings.append("an expert moved twice in one pass did not arrive with its own moments")
    return _report("I5", "AdamW's per-row state follows the rows FAB moved, cleared and re-born",
                   not findings, f"events {kinds}; counters {rc}", findings)


def check_i6_ae_rows_cover_the_population():
    findings, notes = [], []
    for n in (6, 256, 2048, 2217):
        k = min(n, FAB._AE_ROWS)
        passes = -(-n // FAB._AE_ROWS)
        cover = torch.zeros(n, dtype=torch.bool)
        for p in range(passes):
            r = FAB._ae_rows(n, p, torch.device("cpu"))
            if int(r.numel()) != k:
                findings.append(f"n={n} pass {p}: {int(r.numel())} rows, want {k}")
            cover[r] = True
        notes.append(f"n={n}: {int(cover.sum())} of {n} in {passes} pass(es)")
        if int(cover.sum()) != n:
            findings.append(f"n={n}: {int(cover.sum())} of {n} rows covered in {passes} passes")
        if n <= FAB._AE_ROWS and not torch.equal(FAB._ae_rows(n, 5, torch.device("cpu")),
                                                 torch.arange(n)):
            findings.append(f"n={n} <= {FAB._AE_ROWS}: rows are not 0..n-1 (the old prefix)")
    return _report("I6", "the identity round trip covers every live row", not findings,
                   "; ".join(notes), findings)


def check_i7_halt_competes_with_one_expert():
    c = cfg()
    pop = population(c)
    q = torch.randn(3, int(c["FAB"].dk), generator=torch.Generator().manual_seed(2))
    one = FAB._halt_logit(pop, q, 0.1, True, 3, q.device, q.dtype, n=1)
    many = FAB._halt_logit(pop, q, 0.1, True, 3, q.device, q.dtype, n=2048)
    off = FAB._halt_logit(pop, q, 0.1, False, 3, q.device, q.dtype, n=2048)
    d = float((many - one).detach().mean())
    findings = []
    if abs(d - math.log(2048)) > 1e-4:
        findings.append(f"halt logit at n=2048 minus at n=1 is {d:.6f}, want log(2048)="
                        f"{math.log(2048):.6f}")
    if float(off.max()) != FAB._NEG:
        findings.append("FAB_HALT=0's pinned column moved with n")
    return _report("I7", "the halt logit carries +log(n): halt competes with one expert", not findings,
                   f"shift {d:.4f} at n=2048; pinned off-arm column {float(off.max())}", findings)


def check_i8_build_gates_are_predictions():
    c = cfg()
    pop = population(c)
    findings = []
    for name in ("fab.cull_gate", "fab.depth_advance"):
        g = gate(pop, name)
        if g is None or g.reachable or g.fired or "no fab.manage pass has run yet" not in g.reason:
            findings.append(f"build-time {name} is {g.line() if g else None!r}; before any manage "
                            f"pass it must be UNREACHABLE and say no pass has run")
    FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), flush_loss=None)
    cg = gate(pop, "fab.cull_gate")
    if cg is None or not cg.reachable or "/" not in str(cg.value):
        findings.append(f"after one manage pass fab.cull_gate is {cg.line() if cg else None!r}; it "
                        f"must be the evaluated verdict with the occupancy ratio as its pair")
    return _report("I8", "build-time cull and depth gates are predictions until manage runs",
                   not findings, f"after manage: {cg.line() if cg else None}", findings)


def check_i9_shift_warm_rewarms_n_steps():
    """The roll's Steps stamp is the step the shift applies to, so OPT_LR_SHIFT_WARM=1 re-warms one
    step. It stamped clock.opt_steps -- the steps already taken -- and maybe_step prices step
    stamp+1 first, so the ramp's first rung was skipped and WARM=1 re-warmed nothing (driven:
    notifications 1, applied 0). A real two-epoch run through the loop, because the stamp is the
    root's."""
    from spine import loop
    from spine.compose import compose
    lever._reopen_assembly()
    rng.reset_issued()
    sysm = compose(environ={"DATA_STREAM_BYTES": "12000", "RUN_EPOCHS": "2", "DATA_RESAMPLE": "1",
                            "OPT_LR_SHIFT_WARM": "1"})
    res = loop.run(sysm, max_windows=10 ** 6, progress=False)
    c = sysm.optimizer.counters
    got = (int(c.get("opt.shift.notifications", -1)), int(c.get("opt.lr.shift_warm_applied", -1)))
    findings = [] if got == (1, 1) else [
        f"OPT_LR_SHIFT_WARM=1 over one roll: notifications {got[0]}, shift_warm_applied {got[1]}; "
        f"want 1 and 1 (the stamp must be the first step the shift applies to)"]
    return _report("I9", "OPT_LR_SHIFT_WARM=N re-warms N steps after a roll (N=1)", not findings,
                   f"{res.windows} windows over 2 epochs; notifications {got[0]}, applied {got[1]}",
                   findings)


def _merge_pairs_scalar(sim, merge_dist):
    """THE REFERENCE: the scan exactly as it shipped before 2026-09-25, kept here and nowhere else."""
    n = sim.shape[0]
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if float(1.0 - sim[i, j]) <= merge_dist:
                pairs.append((float(sim[i, j]), i, j))
    pairs.sort(reverse=True)
    return pairs


def check_i11_blackout_windows_counts_windows():
    """fab.blackout_windows credits (max(previous check, stamp), this check] on each check that finds
    the blackout open (Q-RUN-17): one per check at batch 1, the whole flush above it, never a window
    before the stamp; counted from the stamp when no previous check is on record; ABSENT where no
    stamp can block growth; and `checked_at` crosses a state_dict round trip."""
    findings, seen = [], []
    caps = type("Caps", (), {"experts": 10**6, "headroom": lambda self, n: 10**6})()
    sig = torch.zeros(SIG_D)

    def at(c, pop, w, shift):
        FAB.grow_check(c["FAB"], pop, flush_loss=torch.tensor(5.0), step_windows=U.Windows(w),
                       soft_cap=caps, memory_pressure=None, signature=sig,
                       shift_at=None if shift is None else U.Windows(shift))
        return pop.counters.get("fab.blackout_windows", "ABSENT")

    c = cfg(FAB_COOLDOWN=40)
    pop = population(c)
    # (1) ARMED, NOTHING STAMPED: present-and-0, and shift_notifications says why.
    for w in (1, 2, 3):
        got = at(c, pop, w, None)
    if got != 0 or pop.counters.get("fab.shift_notifications") != 0:
        findings.append(f"armed with no stamp: fab.blackout_windows {got!r}, notifications "
                        f"{pop.counters.get('fab.shift_notifications')!r}; want 0 and 0")
    # (2) ONE PER CHECK AT BATCH 1: a stamp at 10, checks at 11..15.
    for w in range(11, 16):
        got = at(c, pop, w, 10)
    if got != 5:
        findings.append(f"stamp 10, checks 11..15: {got!r}, want 5")
    seen.append(f"batch 1: {got}")
    # (3) THE WHOLE FLUSH ABOVE BATCH 1: checks at 31 and 47 add 16 each; the check at 63 is 53
    # windows past the stamp, outside the 40-window cooldown, and adds nothing.
    got31, got47, got63 = at(c, pop, 31, 10), at(c, pop, 47, 10), at(c, pop, 63, 10)
    if (got31, got47, got63) != (21, 37, 37):
        findings.append(f"batch-16 checks 31/47/63: {(got31, got47, got63)}, want (21, 37, 37)")
    seen.append(f"batch 16: {got31}, {got47}, {got63}")
    # (4) NEVER A WINDOW BEFORE THE STAMP: a stamp at 80 first seen at the check at 96, 33 windows
    # after the previous check (63), credits 81..96 only.
    got = at(c, pop, 96, 80)
    if got != 53:
        findings.append(f"stamp 80 first seen at 96 after a check at 63: {got!r}, want 53 (+16)")
    seen.append(f"after a gap: {got}")
    # (7) checked_at CROSSES A ROUND TRIP; (5) A CHECKPOINT WITHOUT IT COUNTS FROM THE STAMP.
    sd = FAB.state_dict(c["FAB"], pop)
    same = population(c, seed=99)
    FAB.load_state_dict(c["FAB"], same, sd, sidecar=sd["sidecar"])
    if same.growth.get("checked_at") != 96:
        findings.append(f"checked_at after a round trip: {same.growth.get('checked_at')!r}, want 96")
    old = {k: v for k, v in sd.items()}
    old["growth"] = {k: v for k, v in sd["growth"].items() if k != "checked_at"}
    older = population(c, seed=98)
    FAB.load_state_dict(c["FAB"], older, old, sidecar=sd["sidecar"])
    was = int(older.counters.get("fab.blackout_windows", 0))
    got = at(c, older, 116, 100)
    if older.growth.get("checked_at") != 116 or got - was != 16:
        findings.append(f"a checkpoint without checked_at, stamp 100, first check 116: +{got - was}, "
                        f"want +16 counted from the stamp")
    seen.append(f"older checkpoint: +{got - was}")
    # (6) ABSENT WHERE NO STAMP CAN BLOCK GROWTH.
    for env in ({"FAB_GROW": 0, "FAB_COOLDOWN": 40}, {"FAB_COOLDOWN": 0}):
        c6 = cfg(**env)
        p6 = population(c6)
        for w in range(11, 16):
            got = at(c6, p6, w, 10)
        if got != "ABSENT" or p6.counters.get("fab.shift_notifications") != 1:
            findings.append(f"{env}: fab.blackout_windows {got!r} after a stamp, want ABSENT "
                            f"(notifications {p6.counters.get('fab.shift_notifications')!r})")
        seen.append(f"{env}: {got}")
    return _report("I11", "fab.blackout_windows counts the windows each blocked check covers",
                   not findings, "; ".join(seen), findings)


def check_i10_merge_pairs_match_the_scalar_scan():
    findings = []
    g = torch.Generator().manual_seed(10)
    cases = []
    for n, d in ((1, 4), (2, 4), (7, 3), (40, 8), (120, 16)):
        cn = torch.nn.functional.normalize(torch.randn(n, d, generator=g), dim=-1)
        cases.append((f"random n={n}", cn @ cn.t()))
    # CLUSTERED: near-duplicates, the replicate/xover births the scan exists for.
    base = torch.randn(6, 16, generator=g)
    cn = torch.nn.functional.normalize(base.repeat(10, 1) + 1e-3 * torch.randn(60, 16, generator=g), dim=-1)
    cases.append(("clustered n=60", cn @ cn.t()))
    # TIED: exact duplicates, so equal similarities and the (i, j) tie-break decides the order.
    cn = torch.nn.functional.normalize(torch.randn(3, 8, generator=g), dim=-1).repeat(5, 1)
    cases.append(("tied n=15", cn @ cn.t()))
    ran = 0
    for name, sim in cases:
        off = (1.0 - sim).double()
        # THRESHOLDS INCLUDE VALUES THAT SIT EXACTLY ON AN ENTRY'S DISTANCE, where <= is decided.
        cuts = [0.0, 1e-6, 0.01, 0.1, 0.5, 2.0]
        if sim.shape[0] > 1:
            cuts += [float(off[0, 1]), float(off[-2, -1])]
            # ONE DOUBLE ULP UNDER AN ENTRY: excluded in double, INCLUDED if merge_dist were rounded to
            # float32 -- the compare must stay in double, as float(...) <= merge_dist was.
            cuts += [math.nextafter(float(off[0, 1]), -math.inf), math.nextafter(float(off[-2, -1]), -math.inf)]
        for md in cuts:
            want = _merge_pairs_scalar(sim, md)
            got = FAB._merge_pairs(sim, md)
            ran += 1
            if got != want:
                findings.append(f"{name} merge_dist={md!r}: {len(got)} pairs vs reference {len(want)}; "
                                f"first difference at "
                                f"{next((k for k, (x, y) in enumerate(zip(got, want)) if x != y), min(len(got), len(want)))}")
            if any(type(v) is not float or type(i) is not int or type(j) is not int for v, i, j in got):
                findings.append(f"{name} merge_dist={md!r}: element types are not (float, int, int)")
    return _report("I10", "the vectorised merge scan returns the scalar scan's list exactly", not findings,
                   f"{ran} (matrix, merge_dist) cases against the scalar reference", findings)


def _merge_population(c):
    """I12's and I13's population: all six experts past grace (uage 5 against FAB_GRACE=1) and expert
    1's centroid on expert 0's, so that one pair merges at FAB_MERGE_DIST=0.01 and every other pair
    sits at cosine distance 0.43 or more (measured), so no second pass merges anything."""
    pop = population(c)
    for i in range(int(pop.n_live)):
        pop.uage[i] = 5
    with torch.no_grad():
        pop.cent[1] = pop.cent[0].clone()
    return pop


_BIG_CAPS = type("Caps", (), {"experts": 10**6, "headroom": lambda self, n: 10**6})()


def _grow_series(c, pop):
    """30 flat checks at loss 3.0 and one at 30.0 -- a regression the MAD trigger grows one expert
    for on this population (measured) -- returning the last call's GrowReport."""
    sig = torch.nn.functional.normalize(torch.randn(SIG_D, generator=torch.Generator().manual_seed(12)),
                                        dim=0)
    r = None
    for w, loss in enumerate([3.0] * 30 + [30.0], 1):
        r = FAB.grow_check(c["FAB"], pop, flush_loss=torch.tensor(loss), step_windows=U.Windows(w),
                           soft_cap=_BIG_CAPS, memory_pressure=None, signature=sig)
    return r


def check_i12_norm_only_grows_and_selects_nothing():
    """FAB_NORM_ONLY=1 grows, culls and merges nothing (register LOW-FAB_NORM_ONLY-GROWS): FAB.manage
    and FAB.grow_check return before seeding, as at FAB_ON=0, the build gates that predict selection
    and growth read UNREACHABLE naming the lever, a restore re-renders none of them, and
    fab.births / fab.rescued are ABSENT. The same inputs at FAB_NORM_ONLY=0 merge one pair and grow
    one expert, which is the witness that the inputs reach both mechanisms."""
    findings, seen = [], []
    for no in (0, 1):
        c = cfg(FAB_GRACE=1, FAB_MERGE_DIST=0.01, FAB_PRESSURE=0.99, FAB_NORM_ONLY=no)
        pop = _merge_population(c)
        r = FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), flush_loss=None)
        gpop = population(c)
        gr = _grow_series(c, gpop)
        seen.append(f"FAB_NORM_ONLY={no}: merged {r.merged}, n_live {int(pop.n_live)}; grown to "
                    f"{int(gpop.n_live)} with {int(gpop.births)} birth(s)")
        if not no:
            if r.merged != 1 or int(pop.n_live) != 5 or int(gpop.n_live) != 7 or int(gpop.births) != 1:
                findings.append(f"the FAB_NORM_ONLY=0 witness: merged {r.merged} (want 1), n_live "
                                f"{int(pop.n_live)} (want 5), grown n_live {int(gpop.n_live)} (want 7), "
                                f"births {int(gpop.births)} (want 1) -- the inputs no longer reach "
                                f"the mechanisms, so the check below proves nothing")
            continue
        if (r.merged, r.cull_fail, r.cull_util, r.rescued, r.eligible) != (0, 0, 0, 0, 0) \
                or "FAB_NORM_ONLY=1" not in r.cull_gate or int(pop.n_live) != 6:
            findings.append(f"FAB.manage on the norm-only arm returned {r} with n_live {int(pop.n_live)}; "
                            f"want an empty report naming FAB_NORM_ONLY=1 and n_live 6")
        fam = [k for k in ("fab.manage_passes", "fab.merged", "fab.cull_fail", "fab.merge_armed_passes",
                           "fab.grow_checks", "fab.grown_regression", "fab.grow_asked_regression")
               if k in pop.counters or k in gpop.counters]
        if fam:
            findings.append(f"the manage/grow family is PRESENT on the norm-only arm: {fam}")
        if int(gpop.n_live) != 6 or int(gpop.births) != 0:
            findings.append(f"grow_check grew on the norm-only arm: n_live {int(gpop.n_live)}, births "
                            f"{int(gpop.births)}")
        g = gr.gates[0] if gr is not None and gr.gates else None
        if g is None or g.name != "fab.grow_check" or g.reachable or "FAB_NORM_ONLY=1" not in g.reason:
            findings.append(f"grow_check's returned gate is {g.line() if g else None!r}; want "
                            f"fab.grow_check UNREACHABLE naming FAB_NORM_ONLY=1")
        out = FAB.counters(c["FAB"], pop)
        for name in ("fab.growth_armed", "fab.cull_gate", "fab.depth_advance"):
            st = out.get(f"gate:{name}", ("ABSENT", 0, ""))
            if st[0] != "unreachable" or "FAB_NORM_ONLY=1" not in st[2]:
                findings.append(f"build gate {name} reads {st!r:.160}; want UNREACHABLE naming "
                                f"FAB_NORM_ONLY=1")
        if "fab.births" in out or "fab.rescued" in out:
            findings.append("fab.births / fab.rescued are PRESENT on the norm-only arm; the family is "
                            "unreachable there and ABSENT is its reading (Q-FAB-11 (3))")
        # A RESUME RE-RENDERS NOTHING ON THIS ARM: the build's UNREACHABLE lines stand.
        sd = FAB.state_dict(c["FAB"], gpop)
        back = population(c, seed=77)
        FAB.load_state_dict(c["FAB"], back, sd, sidecar=sd["sidecar"])
        rb = {gg.name: gg for gg in back.gates}
        for name in ("fab.cull_gate", "fab.depth_advance"):
            gg = rb.get(name)
            if gg is None or gg.reachable or "FAB_NORM_ONLY=1" not in gg.reason:
                findings.append(f"after a restore {name} reads {gg.line() if gg else None!r:.160}; "
                                f"want build's UNREACHABLE line naming FAB_NORM_ONLY=1")
        if "fab.state_written" not in sd["counters"] or not any(p is back.A for p in back.parameters()):
            findings.append("the norm-only population was not checkpointed with its ledger or left "
                            "the optimizer's parameter list")
    return _report("I12", "FAB_NORM_ONLY=1 grows, culls and merges nothing, and says why", not findings,
                   "; ".join(seen), findings)


def check_i13_merge_gates_carry_their_own_scope():
    """gate:fab.merged is the RUN-scope verdict over the ledger total it prints, and the last pass's
    verdict is gate:fab.merged_last_pass over the fab.merged_last_pass gauge (register
    LOW-FAB-MERGED-REPORT). Pass 1 merges one pair and pass 2 none: the run gate FIRES with count
    1 and the last-pass gate reads armed-but-zero with count 0 -- where one gate used to print
    ('armed-but-zero', 1, '... no pair ...'). With nothing past grace both read UNREACHABLE at 0,
    and at FAB_MERGE_DIST=0 both say merging is off by configuration."""
    findings, seen = [], []

    def lines(c, pop):
        out = FAB.counters(c["FAB"], pop)
        return out, out.get("gate:fab.merged"), out.get("gate:fab.merged_last_pass")

    c = cfg(FAB_GRACE=1, FAB_MERGE_DIST=0.01, FAB_PRESSURE=0.99)
    pop = _merge_population(c)
    r1 = FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), flush_loss=None)
    r2 = FAB.manage(c["FAB"], pop, step_windows=U.Windows(1000), flush_loss=None)
    out, run, last = lines(c, pop)
    seen.append(f"passes merged {r1.merged}, {r2.merged}: run {run[:2] if run else None}, last pass "
                f"{last[:2] if last else None}, armed passes {out.get('fab.merge_armed_passes')}")
    if (r1.merged, r2.merged) != (1, 0):
        findings.append(f"the two passes merged {(r1.merged, r2.merged)}, want (1, 0): the fixture moved")
    if run is None or run[0] != "fired" or run[1] != 1 or run[1] != out.get("fab.merged"):
        findings.append(f"gate:fab.merged is {run!r:.160}; want ('fired', 1, ...) with the count "
                        f"equal to the ledger's fab.merged {out.get('fab.merged')}")
    if last is None or last[0] != "armed-but-zero" or last[1] != 0 or "no pair" not in last[2] \
            or out.get("fab.merged_last_pass") != 0:
        findings.append(f"gate:fab.merged_last_pass is {last!r:.160} beside the gauge "
                        f"{out.get('fab.merged_last_pass')!r}; want ('armed-but-zero', 0, '... no "
                        f"pair ...')")
    if out.get("fab.merge_armed_passes") != 2:
        findings.append(f"fab.merge_armed_passes {out.get('fab.merge_armed_passes')!r}, want 2")
    # NO LINE ANYWHERE IN THE LEDGER PAIRS A NONZERO COUNT WITH 'armed-but-zero'.
    mixed = [k for k, v in out.items() if k.startswith("gate:") and isinstance(v, tuple)
             and v[0] == "armed-but-zero" and isinstance(v[1], int) and v[1] > 0]
    if mixed:
        findings.append(f"gate line(s) printing a nonzero count beside 'armed-but-zero': {mixed}")
    # NOTHING PAST GRACE ON EITHER PASS: both UNREACHABLE at 0, and the run gate says the ledger's.
    c0 = cfg(FAB_GRACE=1000, FAB_MERGE_DIST=0.01, FAB_PRESSURE=0.99)
    p0 = population(c0)
    with torch.no_grad():
        p0.cent[1] = p0.cent[0].clone()
    for w in (500, 1000):
        FAB.manage(c0["FAB"], p0, step_windows=U.Windows(w), flush_loss=None)
    out0, run0, last0 = lines(c0, p0)
    seen.append(f"nothing past grace: {run0[:2] if run0 else None}, {last0[:2] if last0 else None}")
    if not (run0 and last0 and run0[:2] == ("unreachable", 0) and last0[:2] == ("unreachable", 0)
            and "none of the ledger's 2 manage pass(es)" in run0[2]
            and out0.get("fab.merge_armed_passes") == 0):
        findings.append(f"nothing past grace over two passes: run {run0!r:.200}, last {last0!r:.120}, "
                        f"armed passes {out0.get('fab.merge_armed_passes')!r}; want both UNREACHABLE "
                        f"at 0, the run gate over the ledger's 2 passes, and 0 armed passes")
    # OFF BY CONFIGURATION.
    cz = cfg(FAB_GRACE=1, FAB_MERGE_DIST=0, FAB_PRESSURE=0.99)
    pz = _merge_population(cz)
    FAB.manage(cz["FAB"], pz, step_windows=U.Windows(500), flush_loss=None)
    outz, runz, lastz = lines(cz, pz)
    seen.append(f"FAB_MERGE_DIST=0: {runz[:2] if runz else None}, {lastz[:2] if lastz else None}")
    if not (runz and lastz and runz[0] == lastz[0] == "unreachable"
            and "off by configuration" in runz[2] and "off by configuration" in lastz[2]
            and int(pz.n_live) == 6):
        findings.append(f"FAB_MERGE_DIST=0: run {runz!r:.160}, last {lastz!r:.160}, n_live "
                        f"{int(pz.n_live)}; want both UNREACHABLE and off by configuration, nothing "
                        f"merged")
    return _report("I13", "each merge gate prints the count of its own scope", not findings,
                   "; ".join(seen), findings)


CHECKS = (
    check_i1_failure_cull_baseline,
    check_i2_comp_protect_direction,
    check_i3_depth_stage_max_forces,
    check_i4_shift_stamp_counted_once,
    check_i5_row_events_move_the_moments,
    check_i6_ae_rows_cover_the_population,
    check_i7_halt_competes_with_one_expert,
    check_i8_build_gates_are_predictions,
    check_i9_shift_warm_rewarms_n_steps,
    check_i10_merge_pairs_match_the_scalar_scan,
    check_i11_blackout_windows_counts_windows,
    check_i12_norm_only_grows_and_selects_nothing,
    check_i13_merge_gates_carry_their_own_scope,
)


def main():
    print(f"=== fabric internals, driven at d_model={D_MODEL} sig_d={SIG_D}; base {BASE} ===")
    failed = 0
    for check in CHECKS:
        failed += check()
        print()
    print(f"=== {len(CHECKS)} checks, {failed} failing ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
