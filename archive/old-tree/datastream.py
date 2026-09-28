"""datastream.py — disk-backed corpus so training data is DISK-bounded, not RAM-bounded.

The training loop's corpus access is just `CORP[p][s:s+L]` (random segments) + `len(CORP[p])` (see self_organize
build_stream/seg_from). `MmapConcat` presents a set of on-disk files as ONE indexable byte sequence backed by mmap,
so the bytes stay on DISK (OS-paged) instead of being read into a RAM list. Combined with re-sampling the stream each
epoch, a run can draw fresh data from a corpus far larger than RAM (toward GPT-2 data scale) -- the in-RAM footprint
is only the current STREAM_LEN slice, not the whole corpus.

`python3 datastream.py` runs a CPU probe: it checks MmapConcat is byte-identical to the naive read-all-into-RAM path.
"""
import mmap
import os
import bisect
import glob


class MmapConcat:
    """Read-only virtual concatenation of files as one indexable byte sequence, backed by mmap (disk-paged). Supports
    len() and [start:stop] slicing (and int indexing) -- a drop-in for a `bytes` corpus in random-segment sampling."""
    def __init__(self, paths, cap=None):
        self.maps = []
        self.bounds = [0]
        for p in paths:
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if sz <= 0:
                continue
            f = open(p, "rb")
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            self.maps.append(mm)
            self.bounds.append(self.bounds[-1] + sz)
            if cap is not None and self.bounds[-1] >= cap:
                break
        self.total = self.bounds[-1] if cap is None else min(self.bounds[-1], cap)

    def __len__(self):
        return self.total

    def _slice(self, s, e):
        s = max(0, s)
        e = min(self.total, e)
        if e <= s:
            return b""
        out = bytearray()
        mi = bisect.bisect_right(self.bounds, s) - 1                # first file whose range covers s
        pos = s
        while pos < e and mi < len(self.maps):
            mstart, mend = self.bounds[mi], self.bounds[mi + 1]
            out += self.maps[mi][pos - mstart:min(e, mend) - mstart]
            pos = mend
            mi += 1
        return bytes(out)

    def __getitem__(self, key):
        if isinstance(key, slice):
            s = 0 if key.start is None else (key.start if key.start >= 0 else self.total + key.start)
            e = self.total if key.stop is None else (key.stop if key.stop >= 0 else self.total + key.stop)
            return self._slice(s, e)
        k = key if key >= 0 else self.total + key
        return self._slice(k, k + 1)[0]                            # int index -> int, matching bytes indexing


def open_corpus(data_dir, domains, cap=None, disk=False):
    """Return a per-domain corpus list. disk=True -> mmap-backed (disk-paged); else read-all-into-RAM (the original)."""
    out = []
    for d in domains:
        # `*` used to mean literally everything in the directory, including fetch_big.py's _fetch_manifest.json --
        # which would be spliced into the corpus and trained on as if it were English. Harmless at 300 bytes, but it
        # is corpus contamination that nothing downstream could detect, and a 40 GB pull writes one per domain.
        paths = [p for p in sorted(glob.glob(f"{data_dir}/train/{d}/*"))
                 if not os.path.basename(p).startswith("_") and not p.endswith(".json")]
        if not paths: raise SystemExit(
            f"no corpus files in {data_dir}/train/{d}/ -- DOMAINS names a domain with no data. "
            f"Pull one with: python3 fetch_big.py --dataset fineweb-edu --domain {d} --gb <n> --out {data_dir}")
        if disk:
            out.append(MmapConcat(paths, cap=cap))
        else:
            data = b"".join(open(f, "rb").read() for f in paths)
            out.append(data[:cap] if cap else data)
    return out


def _probe():
    paths = sorted(glob.glob("data/train/eng/*"))
    if not paths:
        print("no data/train/eng/* to probe"); return False
    import random
    mc = MmapConcat(paths)
    ref = b"".join(open(p, "rb").read() for p in paths)
    ok = len(mc) == len(ref)
    r = random.Random(0)
    n = 0
    for _ in range(300):
        L = r.randint(10, 8000)
        s = r.randint(0, max(1, len(ref) - L - 1))
        if bytes(mc[s:s + L]) != ref[s:s + L]:
            ok = False; break
        n += 1
    ok = ok and (mc[123] == ref[123]) and (bytes(mc[-500:]) == ref[-500:])   # int + negative-slice
    print(f"=== MmapConcat vs read-all-into-RAM ===")
    print(f"  files {len(paths)} | len {len(mc)} (ref {len(ref)}) | {n} random slices identical | int+neg-slice ok")
    print(f"  VERDICT: {'DROP-IN CORRECT' if ok else 'MISMATCH'}")
    return ok


if __name__ == "__main__":
    _probe()
