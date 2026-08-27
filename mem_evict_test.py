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


def main():
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
    if a_off != 0:
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


    print("\nok -- eviction selects on retrieval, and a floor survives a domain switch." if ok else "\n!! FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
