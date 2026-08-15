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
    g = torch.Generator().manual_seed(0)
    m = EditableMemory(CAP, D, "cpu", V, write_gate=0.0, topk=4, evict=evict)
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

    print("\nok -- eviction selects on retrieval." if ok else "\n!! FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
