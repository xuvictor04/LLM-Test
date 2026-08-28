"""Does the eviction rule select on ANYTHING?

This exists because the answer was no, silently, for the whole project. EVICT was documented as choosing victims by
utility ("least-RETRIEVED dies, so entries that stay useful survive"), but mem.read() was called only from generate()
and bpb_true() -- both eval-only -- so during training `use` stayed 0 for every entry and `last` was never written at
all on the global store. Every rule that claims to rank entries was ranking a constant, i.e. evicting by write order.

The observable consequence was the vanished English domain after the Python run: English was not less useful, it had
merely stopped being WRITTEN, and nothing in the training loop could notice that its entries were still being read.

The test drives one store two ways -- domain A retrieved-but-not-written vs A neither retrieved nor written -- and
asserts the store can tell them apart. It should also FAIL for EVICT=recency, which is the control: write-order
eviction cannot distinguish the two, and that equality is the bug stated as an assertion.

    python3 mem_evict_test.py
"""
import torch
from memory import EditableMemory

D, V, CAP, HALF = 16, 50, 200, 100


def _keys(dom, n, g):
    """Keys for domain `dom`, in a subspace disjoint from the other domain's."""
    k = torch.zeros(n, D)
    k[:, dom * 4:(dom + 1) * 4] = torch.randn(n, 4, generator=g).abs() + 1.0
    return k


def _fill(evict):
    # src_floor=0 ON PURPOSE. These three cases isolate WHICH CLOCK eviction ranks on, and the per-source floor
    # is a different mechanism layered above it -- at its default the absent domain is protected regardless of
    # the clock, which is the floor working and would leave this test unable to see the clock at all. The floor
    # gets its own case in domain_switch() below.
    g = torch.Generator().manual_seed(0)
    m = EditableMemory(CAP, D, "cpu", V, write_gate=0.0, topk=4, evict=evict, src_floor=0.0)
    m.write(_keys(0, HALF, g), torch.randint(0, V, (HALF,), generator=g), src=0)   # domain A
    m.write(_keys(1, HALF, g), torch.randint(0, V, (HALF,), generator=g), src=1)   # domain B
    return m, g


def _alive(m, src):
    return int(((m.src == src) & m.active).sum())


def _run(evict, read_a, rounds=40):
    """B is written continuously; A is written never and read only if read_a. Returns surviving A entries."""
    m, g = _fill(evict)
    assert _alive(m, 0) == HALF, "domain A did not land in the store"
    for _ in range(rounds):
        if read_a: m.read(_keys(0, 8, g))
        m.write(_keys(1, 8, g), torch.randint(0, V, (8,), generator=g), src=1)
    return _alive(m, 0)


def domain_switch(src_floor, rounds=60):
    """THE FAILURE THE LOGS SHOWED, as a test.

    A run trains on domain A, then switches to domain B for good. B is written continuously; A is neither
    written nor retrieved, because the read probe queries the CURRENT stream and no query resembles A any more.
    That is not a hypothetical -- it is what two real runs did, under write-recency and again under
    retrieval-recency, both ending with `p0=0 p1=198019`.

    Returns A's surviving entry count. With no floor this must go to 0; with a floor it must not."""
    g = torch.Generator().manual_seed(0)
    m = EditableMemory(CAP, D, "cpu", V, write_gate=0.0, topk=4, evict="lru", src_floor=src_floor, n_src_hint=8)
    m.write(_keys(0, HALF, g), torch.randint(0, V, (HALF,), generator=g), src=0)      # phase 1: domain A only
    # A IS READ DURING ITS OWN PHASE, which is what a real run does -- the training read probe queries the stream
    # being trained on, so a domain's entries are promoted while that domain is live. Without this the test has A
    # never retrieved even once, which is not the continual-learning scenario but a different one: unproven
    # material, which probation is *supposed* to discard.
    for _ in range(10):
        m.read(_keys(0, 8, g))
    for _ in range(rounds):
        m.read(_keys(1, 8, g))                                                        # phase 2: B streams,
        m.write(_keys(1, 8, g), torch.randint(0, V, (8,), generator=g), src=1)        #   and only B is queried
    return _alive(m, 0), _alive(m, 1)


def scan_resistance(prob_frac, rounds=60):
    """THE SCAN. A working set is established and stays useful -- it keeps being retrieved. Then a flood of
    one-hit material arrives and is never asked for again.

    Plain LRU has no defence: every flooded entry is inserted at maximum recency and pushes the working set out.
    A probationary region bounds how much of the store the flood can hold at once, and makes it earn the rest by
    being retrieved. Returns (working-set survivors, flood occupancy)."""
    g = torch.Generator().manual_seed(3)
    m = EditableMemory(CAP, D, "cpu", V, write_gate=0.0, topk=4, evict="lru",
                       src_floor=0.0, prob_frac=prob_frac, n_src_hint=8)
    m.write(_keys(0, HALF, g), torch.randint(0, V, (HALF,), generator=g), src=0)      # the working set
    for _ in range(rounds):
        m.read(_keys(0, 8, g))                                                        # still wanted, every round
        m.write(_keys(1, 8, g), torch.randint(0, V, (8,), generator=g), src=1)        # scan: written, never read
    return _alive(m, 0), _alive(m, 1)


def census_survives_resume():
    """Does the per-source floor still work after a RESUME?

    THE FLOOR'S ONLY INPUT IS nsrc, and nsrc is maintained incrementally in _commit because an O(cap) recount
    on every write is 200k elements per step. A resume does not go through _commit: it restores keys/tok/src/
    pos/use and sets `active` directly. nsrc therefore stayed at the zeros a fresh store starts with, so
    `has = (nsrc > 0)` was all False, `prot` was all False, and MEM_SRC_FLOOR protected NOTHING for the rest of
    the run -- while the banner still printed "src floor 0.5" and this very file still proved the floor works.

    That is the shape the project keeps getting caught by: the test covers the hot path, the bug lives on the
    path the test does not take, and every report about the mechanism keeps printing.

    Restores are simulated exactly as self_organize.py does them -- assign the arrays, set active, DO NOT call
    write() -- and then rebuild_census() has to put the census back.
    """
    g = torch.Generator().manual_seed(0)
    m = EditableMemory(CAP, D, "cpu", V, write_gate=0.0, topk=4, evict="lru", src_floor=0.5, n_src_hint=8)
    for dom in (0, 1):
        m.write(_keys(dom, HALF, g), torch.randint(0, V, (HALF,), generator=g), src=dom)
    before = m.nsrc.clone()
    live_before = int((before > 0).sum())

    # THE RESUME, as self_organize.py performs it: arrays in, active set, _commit never called.
    n = int(m.active.sum())
    keys, tok, src, pos = m.keys.clone(), m.tok.clone(), m.src.clone(), m.pos.clone()
    r = EditableMemory(CAP, D, "cpu", V, write_gate=0.0, topk=4, evict="lru", src_floor=0.5, n_src_hint=8)
    r.keys[:n] = keys[:n]; r.tok[:n] = tok[:n]; r.src[:n] = src[:n]; r.pos[:n] = pos[:n]
    r.active[:n] = True; r.ptr = n % r.cap

    ok = True
    if int(r.nsrc.sum()) != 0:
        print("  note: a fresh store's census was not zero, so this test cannot show the gap")
    # The bug, stated as the assertion: without the rebuild the floor has nothing to protect with.
    blocked_broken = int((r._eligible()).sum())
    r.rebuild_census()
    live_after = int((r.nsrc > 0).sum())
    same = bool(torch.equal(r.nsrc[:before.numel()], before))
    print(f"  before resume: {live_before} source id(s) hold memory, census sum {int(before.sum())}")
    print(f"  restored without rebuild: {blocked_broken} eligible source(s) -- the floor sees nothing")
    print(f"  after rebuild_census():   {live_after} source id(s), census sum {int(r.nsrc.sum())}")
    if blocked_broken != 0:
        print("  !! a restored store already had a live census -- the gap this guards is not reproduced"); ok = False
    if not same:
        print("  !! rebuild_census did not reproduce the census the store had before the resume"); ok = False
    if live_after != live_before:
        print(f"  !! {live_after} live sources after rebuild, {live_before} before"); ok = False
    # ...and the rebuild must count only ACTIVE entries, or a deleted entry keeps its slot in the floor.
    r.active[0] = False
    r.rebuild_census()
    if int(r.nsrc.sum()) != int(before.sum()) - 1:
        print(f"  !! deactivating one entry did not drop the census by exactly 1 "
              f"({int(r.nsrc.sum())} vs {int(before.sum()) - 1})"); ok = False
    else:
        print("  deactivating one entry drops the census by exactly 1 -- it counts ACTIVE rows, not slots")
    print("  ok -- the per-source floor survives a resume" if ok else "  !! FAILED")
    return ok


def wrong_gates_reads():
    """set_selfcon / is_wrong / read had no test at all, and is_wrong gates EVERY retrieval.

    Two states are invisible in a log and print exactly the same nothing:
      - INERT. is_wrong() opens with `if int(checked.sum()) > 10`, so with ten or fewer entries ever
        self-consistency-checked it returns all-False and the filter does nothing whatever.
      - OVER-EAGER. On the first continual-learning run it flagged 63,146 genuine entries of 200,000 at 3%
        precision, and the log said "detect-only: sweep OFF ... too low to delete safely" -- which is true of
        DELETION and says nothing about reads, because Memory.read filters on the same predicate. About a third
        of the store was unreachable while the report read as reassurance.
    MEM_WRONG_READ separates the two decisions. This checks all three: the floor, the gating, and the knob.
    """
    ok = True
    V, D, CAP = 32, 8, 64
    m = EditableMemory(CAP, D, "cpu", V, write_gate=0.0, topk=4, evict="lru", src_floor=0.0)
    q = torch.nn.functional.normalize(torch.randn(CAP, D), dim=-1)
    for i in range(CAP):
        m.write(q[i:i + 1], torch.tensor([i % V]), src=torch.tensor([0]))
    n_act = int(m.active.sum())

    # 1. THE FLOOR. Fewer than 11 checked entries and nothing can ever be flagged, however implausible.
    m.set_selfcon(torch.arange(5), torch.ones(5))              # maximally implausible, but only 5 of them
    n_wrong_few = int(m.is_wrong().sum())
    print(f"   5 entries checked, all at implausibility 1.0 -> flagged {n_wrong_few}")
    if n_wrong_few != 0:
        print("!! the >10 floor did not hold; is_wrong() flagged on a sample too small to have a threshold"); ok = False

    # 2. IT FLAGS ONCE IT HAS ENOUGH, and only the tail.
    frac = torch.cat([torch.zeros(n_act - 8), torch.ones(8)])   # a clear implausible tail
    m.set_selfcon(torch.arange(n_act), frac)
    n_wrong = int(m.is_wrong().sum())
    print(f"   {n_act} entries checked, 8 in the implausible tail -> flagged {n_wrong}")
    if not (0 < n_wrong <= 16):
        print(f"!! expected the tail and only the tail to be flagged, got {n_wrong} of {n_act}"); ok = False

    # 3. READ IS GATED BY IT. This is the half "detect-only" never covered.
    probe = q[:4]
    _, _, hit_on, _ = m.read(probe)
    flagged = m.is_wrong().nonzero(as_tuple=True)[0].tolist()
    reached_on = [int(h) for h in hit_on.reshape(-1).tolist() if h >= 0]
    if any(h in flagged for h in reached_on):
        print("!! read() returned an entry the WRONG flag had excluded -- the gate is not doing its job"); ok = False
    else:
        print(f"   read() with MEM_WRONG_READ=1 reached {len(set(reached_on))} entries, none of them flagged")

    # 4. ...AND THE KNOB TURNS THAT OFF WITHOUT TOUCHING THE FLAG.
    # PROBE AT A FLAGGED ENTRY'S OWN KEY, not at arbitrary queries. The first version of this check read with
    # four unrelated probes, reached the same 14 entries either way, and passed -- because none of the flagged
    # entries was in the top-k for those queries. A test that cannot reach the thing it is gating proves the
    # gate works no matter what the gate does, which is the failure mode this whole suite exists to catch.
    tgt = int(m.is_wrong().nonzero(as_tuple=True)[0][0])
    aim = m.keys[tgt:tgt + 1].clone()                          # exactly the flagged entry's own key
    _, _, hit_gated, _ = m.read(aim)
    gated = [int(h) for h in hit_gated.reshape(-1).tolist() if h >= 0]
    if tgt in gated:
        print(f"!! entry {tgt} is flagged WRONG and read() returned it anyway -- the gate does nothing"); ok = False
    else:
        print(f"   querying flagged entry {tgt} at its OWN key with MEM_WRONG_READ=1 -> not returned")

    m.wrong_read = False
    _, _, hit_open, _ = m.read(aim)
    opened = [int(h) for h in hit_open.reshape(-1).tolist() if h >= 0]
    still_flagged = int(m.is_wrong().sum())
    if tgt not in opened:
        print(f"!! MEM_WRONG_READ=0 and entry {tgt} is STILL unreachable -- the knob is not the thing gating it")
        ok = False
    else:
        print(f"   MEM_WRONG_READ=0 -> the same query returns it, so the knob is what was gating retrieval")
    if still_flagged != n_wrong:
        print("!! turning off the read gate changed the FLAG; the two decisions are still coupled"); ok = False
    else:
        print(f"   ...and the flag still marks {still_flagged} entries, so reporting is unaffected")
    return ok


def census_is_exact():
    """ONE SLOT, ONE ROW -- and the per-source census that depends on it.

    THE FAILURE THIS ASSERTS AGAINST, in the form it actually appeared. A pilot's memory report printed

        !! MEMORY STARVATION: ... s779 (-2 now, peaked 111230), ... s899 (-3 now, peaked 5566) ...

    A count of ACTIVE ENTRIES cannot be negative. No amount of eviction produces one; only bad arithmetic does.
    Both producers were slots named MORE THAN ONCE inside a single write:

      - the global path drew its victim pool with torch.randint, i.e. WITH REPLACEMENT, so a slot could appear
        twice in the pool carrying the same `last`, and if it ranked into the victims both copies were taken;
        the circular pad could also re-take a slot the pool had already chosen.
      - the per-owner path ranked the WHOLE block by `last` to find victims, and free slots have never been
        stamped, so their clock reads 0 -- the oldest possible. The "victims" were therefore exactly the free
        slots the line above had already taken, and cat([free, lru]) returned m indices of which only
        free.numel() were distinct.

    A repeated slot costs twice. Index assignment collapses it silently, so the store holds fewer rows than the
    caller was told; and _commit decrements the DISPLACED owner once per occurrence while crediting the new
    source idx.numel(), so the displaced source is overcharged on every write. nsrc is the per-source floor's
    only input and `has = (nsrc > 0)` is what makes a source eligible for protection at all -- so an
    undercounted source loses the protection of the floor that exists to stop it being driven to zero, which is
    the exact failure MEM_SRC_FLOOR was added for.

    Asserted three ways, because the clamp alone would only hide the next drift:
      1. no repeats are produced (mem.n_dup_slot == 0) on either path,
      2. no decrement ever went below zero (mem.n_src_underflow == 0),
      3. the incremental census EQUALS an exact recount from `src & active`, source by source.
    """
    ok = True
    g = torch.Generator().manual_seed(11)

    for tag, kw in (("global  (n_own=1)", dict(evict="lru")),
                    ("per-owner (n_own=8)", dict(evict="lru", n_own=8, quota=25))):
        mem = EditableMemory(CAP, D, "cpu", V, write_gate=0.0, topk=4, src_floor=0.5, n_src_hint=8, **kw)
        # Enough writes to cycle the store many times over, from a rotating set of sources, so that every source
        # spends time being displaced by the others. That rotation is what drove the counts negative.
        # The per-owner arm calls _store directly: write() takes no owner, and the owner-partitioned path is
        # reached in the engine through write_batch(owners=...) -- which is a batching wrapper around this same
        # call. The slot selection under test is _store's, so _store is what the test drives.
        for t in range(400):
            n = 3 + (t % 5)
            k = torch.randn(n, D, generator=g)
            tok = torch.randint(0, V, (n,), generator=g)
            if mem.n_own > 1:
                mem._store(k, tok, t % 7, None, None, own=(t % 8))
            else:
                mem.write(k, tok, src=t % 7)
        exact = torch.zeros_like(mem.nsrc)
        for s in mem.src[mem.active].unique().tolist():
            if s >= 0: exact[int(s)] = float(((mem.src == int(s)) & mem.active).sum())
        drift = (mem.nsrc - exact).abs().max().item()
        neg = int((mem.nsrc < 0).sum())
        print(f"  {tag:20s} dup slots {mem.n_dup_slot:3d} | underflows {mem.n_src_underflow:3d} | "
              f"negative sources {neg} | max |census - recount| {drift:g}")
        if mem.n_dup_slot:
            print(f"!! a write named {mem.n_dup_slot} slot(s) more than once on the {tag} path -- those rows were "
                  f"never stored, and the displaced source was charged for each repeat."); ok = False
        if mem.n_src_underflow or neg:
            print(f"!! the per-source census went below zero ({mem.n_src_underflow} underflow(s), {neg} negative "
                  f"source(s)) -- a count of active entries cannot be negative."); ok = False
        if drift > 0:
            print(f"!! the incremental census disagrees with an exact recount by {drift:g}. nsrc is the floor's "
                  f"only input, so this is protection granted or withheld on numbers that are not true."); ok = False

    # THE PER-OWNER DEFECT NEEDS AIMING AT, because it lives in a transient the random arm above walks straight
    # past. It fires only while 0 < free < m -- once a block is FULL there are no free slots to re-take, and
    # while it is EMPTY the free list covers the whole write. That is one write per owner, during fill-up, which
    # is why the random arm reported 0 drift on a path that was genuinely broken. Measured on the pre-fix code
    # this exact sequence stored FOUR of the six rows handed over and credited the source with six.
    mem = EditableMemory(200, D, "cpu", V, write_gate=0.0, topk=4, evict="lru",
                         src_floor=0.5, n_src_hint=8, n_own=8, quota=25)
    mem._store(torch.randn(23, D, generator=g), torch.randint(0, V, (23,), generator=g), 1, None, None, own=0)
    mem._store(torch.randn(6, D, generator=g), torch.randint(0, V, (6,), generator=g), 2, None, None, own=0)
    _true = int(((mem.src == 2) & mem.active).sum())
    print(f"  {'per-owner fill-up':20s} 23 then 6 rows into a 25-slot block: 6 asked for, {_true} stored, "
          f"census says {int(mem.nsrc[2])}")
    if _true != 6 or int(mem.nsrc[2]) != _true:
        print(f"!! {6 - _true} row(s) handed to the store were never written, and the source was charged for "
              f"{int(mem.nsrc[2])}. Two free slots read last=0 -- the oldest possible -- so ranking the whole "
              f"block for victims picks the slots the free list had already taken."); ok = False

    # AND THE INVARIANT ITSELF, driven directly. Both checks above now pass because the SELECTION no longer
    # produces repeats -- which means the collapse in _commit is never entered, and a guard that is never
    # entered is not a guard that works. A third caller could build `idx` its own way at any time, so hand
    # _commit the exact shape the old selection produced and assert the backstop holds: fewer rows written,
    # counted, and a census that still matches the truth.
    mem = EditableMemory(50, D, "cpu", V, write_gate=0.0, topk=4, evict="lru", src_floor=0.5, n_src_hint=8)
    mem._commit(torch.tensor([3, 4]), torch.randn(2, D, generator=g), torch.randint(0, V, (2,), generator=g),
                1, None, torch.tensor([10, 11]), 2)
    n = mem._commit(torch.tensor([3, 7, 3, 9]), torch.randn(4, D, generator=g),
                    torch.randint(0, V, (4,), generator=g), 2, None, torch.tensor([20, 21, 22, 23]), 4)
    t1 = int(((mem.src == 1) & mem.active).sum()); t2 = int(((mem.src == 2) & mem.active).sum())
    _kept = [int(v) for v in mem.pos[torch.tensor([3, 7, 9])]]
    print(f"  {'_commit backstop':20s} idx [3,7,3,9] -> wrote {n} row(s), dup_slot {mem.n_dup_slot} | "
          f"census s1={int(mem.nsrc[1])} s2={int(mem.nsrc[2])} vs truth s1={t1} s2={t2} | kept pos {_kept}")
    if n != 3 or mem.n_dup_slot != 1 or int(mem.nsrc[1]) != t1 or int(mem.nsrc[2]) != t2:
        print(f"!! _commit did not collapse a repeated slot: it returned {n} for 3 distinct slots, counted "
              f"{mem.n_dup_slot} repeat(s), and left a census that disagrees with `src & active`."); ok = False
    if _kept != [20, 21, 23]:
        print(f"!! the collapse kept the wrong payload rows ({_kept}, expected [20, 21, 23]): the survivor of a "
              f"repeated slot must be a row the caller actually handed over, at the position it handed it."); ok = False
    return ok


def main():
    # SEEDED, BECAUSE THIS SUITE FAILED THREE TIMES IN TWENTY ON UNCHANGED CODE. The per-case generators cover
    # the KEYS; the store's victim sampling calls torch.randint/randperm on the global RNG and was never seeded,
    # so every run drew a different pool and the knife-edge assertion below landed on either side of its own
    # threshold at random. A regression test that fails 15% of the time on code nobody touched cannot be used to
    # judge a change -- the first instinct on a red run is to re-run it, which is the instinct that lets a real
    # regression through. Seeding makes a failure mean something.
    torch.manual_seed(0)
    ok = True
    lru_read, lru_quiet = _run("lru", True), _run("lru", False)
    use_read, use_quiet = _run("usage", True), _run("usage", False)
    rec_read, rec_quiet = _run("recency", True), _run("recency", False)

    print(f"EVICT=lru      A retrieved {lru_read:3d}/{HALF} | A never retrieved {lru_quiet:3d}/{HALF}")
    print(f"EVICT=usage    A retrieved {use_read:3d}/{HALF} | A never retrieved {use_quiet:3d}/{HALF}")
    print(f"EVICT=recency  A retrieved {rec_read:3d}/{HALF} | A never retrieved {rec_quiet:3d}/{HALF}   (control)")

    # THE POINT. Being read has to be worth something.
    for name, r, q in (("lru", lru_read, lru_quiet), ("usage", use_read, use_quiet)):
        if not r > q:
            print(f"!! EVICT={name}: retrieval bought NOTHING ({r} vs {q}) -- the signal is dead again."); ok = False
    # lru has a strictly monotone clock, so an unread + unwritten domain has nowhere to hide: every one of its
    # entries is older than everything written after it and eviction must reach all of them.
    if lru_quiet != 0:
        print(f"!! EVICT=lru: an unread, unwritten domain kept {lru_quiet} entries -- eviction is not reaching it.")
        ok = False
    # usage is DIFFERENT, and the difference is worth naming rather than asserting away: it ranks by `use`, and with
    # no retrievals every entry ties at 0, so the sampled topk breaks ties arbitrarily and a chunk of the dead domain
    # survives by luck. That residue IS the "ranking a constant" failure, visible. lru degrades to FIFO instead,
    # which is at least a defined rule, which is why it is the default.
    if use_quiet:
        print(f"   (EVICT=usage left {use_quiet}/{HALF} of the dead domain alive on tie-break -- expected: with no "
              f"retrievals every `use` is 0 and the ranking is arbitrary.)")

    # The control states the bug. If this ever stops holding, write-order eviction has quietly acquired a use signal
    # and the two rules are no longer measuring different things.
    if rec_read != rec_quiet:
        print(f"!! EVICT=recency distinguished read from unread ({rec_read} vs {rec_quiet}); it is not write-order any more.")
        ok = False

    # --- the domain-switch test, which is the one that matters for continual learning -----------------
    print()
    a_off, b_off = domain_switch(0.0)
    a_on,  b_on  = domain_switch(0.5)
    print(f"domain switch, MEM_SRC_FLOOR=0    A kept {a_off:3d}/{HALF}  B {b_off}")
    print(f"domain switch, MEM_SRC_FLOOR=0.5  A kept {a_on:3d}/{HALF}  B {b_on}")
    # A TOLERANCE, NOT AN EXACT ZERO, and the seed above is what makes even this reproducible. The control's
    # claim is "without the floor the unqueried domain is wiped out"; whether the last one or two of a hundred
    # entries happen to survive a random victim sample is not part of that claim, and asserting == 0 made the
    # suite's verdict depend on it. The number that matters is the CONTRAST with the floor arm below, which
    # keeps ~44 of 100 -- a margin two entries cannot touch.
    if a_off > 2:
        print(f"!! with no floor an unqueried domain kept {a_off} entries -- the test is not reproducing the "
              f"failure it exists to guard, so its pass below proves nothing."); ok = False
    if a_on <= 0:
        print(f"!! MEM_SRC_FLOOR=0.5 did NOT protect the absent domain ({a_on} entries left). This is the "
              f"measured continual-learning failure, unfixed."); ok = False
    if b_on <= 0:
        print(f"!! the floor starved the ACTIVE domain ({b_on} entries) -- protection must not deadlock the "
              f"store against the material actually streaming."); ok = False

    # --- scan resistance: the flood must not evict a working set that is still being retrieved ---------
    print()
    w_off, f_off = scan_resistance(0.0)      # no probation: plain LRU
    w_on,  f_on  = scan_resistance(0.10)     # 10% probationary region, S3-FIFO's size
    print(f"scan, probation OFF   working set kept {w_off:3d}/{HALF}  flood holds {f_off}")
    print(f"scan, probation 10%   working set kept {w_on:3d}/{HALF}  flood holds {f_on}")
    # REPORTED, NOT ASSERTED, and the reason is worth keeping. At this scale probation and plain LRU come out
    # within a point or two of each other, and it is not because probation is broken -- it is because only about
    # a third of the synthetic "working set" is ever actually retrieved. Cosine kNN with a handful of queries
    # keeps hitting the same near neighbours, so the other two thirds are never asked for, are indistinguishable
    # from the flood on the only evidence the store has, and are correctly discarded by both rules.
    # The honest conclusion is that this toy cannot separate them, so it does not claim to. The case where the
    # two rules genuinely diverge is the DOMAIN SWITCH above, which is also the one the project actually hit.
    if w_on < w_off - 5:
        print(f"!! probation made scan resistance materially WORSE ({w_on} vs {w_off}); it is inverting its job.")
        ok = False
    else:
        print(f"   difference {w_on - w_off:+d} of {HALF}. This toy cannot separate the two rules: only ~a third")
        print(f"   of the working set is ever retrieved here, and the rest is indistinguishable from the flood on")
        print(f"   the evidence available, so both rules correctly discard it. The domain-switch case above is")
        print(f"   where they diverge, and is the one this project actually hit.")

    print("\n--- does the floor survive a RESUME? ---")

    ok = census_survives_resume() and ok

    print("\n--- does the WRONG flag gate reads, and does it say so? ---")
    ok = wrong_gates_reads() and ok

    print("\n--- is the per-source census EXACT? (one slot, one row) ---")
    ok = census_is_exact() and ok


    print("\nok -- eviction selects on retrieval, and a floor survives a domain switch." if ok else "\n!! FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
