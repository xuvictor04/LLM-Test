"""Multiprocess tokenizer -- parallel segmentation across CPU cores, bypassing the GIL.

The dynamic tokenizer is single-threaded Python; caching + prefetch hide it behind the GPU, but at very
large batch / cold cache (enwik9's ~1M windows) it still bottlenecks on one core. Here N worker PROCESSES
each hold a vocab replica and segment windows into ready batches in parallel; the main process pulls
batches, tallies them to mint new tokens, and broadcasts new merges back to workers.

Design (learned the hard way in testing):
- Uses **spawn**, not fork. By the time train.py starts this, torch/numpy have spawned BLAS/OpenMP threads,
  and forking a multithreaded process leaves inherited dead locks that hang the workers. Spawn gives each
  worker a fresh interpreter. (train.py MUST be a guarded `if __name__=="__main__"` script, which it is.)
- The corpus is shared via a memory-mapped .npy of raw byte windows, so spawn doesn't pickle gigabytes to
  every worker; all workers mmap the same file.
- Correct because the vocab only GROWS: a worker on a slightly-stale replica still emits valid ids; the main
  folds newly-minted merges in via the broadcast queues.

MP_WORKERS>0 to enable; default 0 -> not used (the proven single-thread prefetch runs).
"""
import os, random, tempfile
import multiprocessing as mp
import numpy as np
import torch


def _worker(corpus_path, n_chunks, merges0, vmax, max_tok, ctx, bs, batch_q, merge_q, stop_ev):
    from tokenizer import DynamicTokenizer                     # fresh import in the spawned interpreter
    arr = np.load(corpus_path, mmap_mode="r")                  # (n_chunks, L) uint8, shared read across workers
    tok = DynamicTokenizer(vmax=vmax, min_pair=10**9, max_tok=max_tok)   # min_pair huge -> never mints locally
    for a, b in merges0:
        tok.apply_merge(a, b)
    while not stop_ev.is_set():
        while not merge_q.empty():                             # fold in merges the main process minted
            try:
                for a, b in merge_q.get_nowait():
                    tok.apply_merge(a, b)
            except Exception:
                break
        rows, tries = [], 0
        while len(rows) < bs and tries < bs * 6:
            tries += 1
            ids = tok.segment(arr[random.randrange(n_chunks)].tolist(), count=False)
            if len(ids) < ctx:
                continue
            s = random.randint(0, len(ids) - ctx)
            rows.append(ids[s:s + ctx])
        if rows:
            try:
                batch_q.put(rows, timeout=1.0)                 # plain list; pickled by value, spawn-safe
            except Exception:
                pass                                           # queue full: drop and loop (backpressure)


class MPBatchProducer:
    def __init__(self, chunks, dyntok, ctx, batch, n_workers):
        arr = np.stack([c.numpy().astype(np.uint8) for c in chunks])   # raw byte windows (0-255)
        self._tmp = tempfile.NamedTemporaryFile(suffix=".npy", delete=False); self._tmp.close()
        np.save(self._tmp.name, arr)
        self.dyntok = dyntok; self.vm = dyntok.vmax
        self.ctxmp = mp.get_context("spawn")
        self.batch_q = self.ctxmp.Queue(maxsize=max(4, 2 * n_workers))
        self.merge_qs = [self.ctxmp.Queue() for _ in range(n_workers)]
        self.stop_ev = self.ctxmp.Event()
        self.procs = [self.ctxmp.Process(target=_worker, daemon=True,
                      args=(self._tmp.name, len(chunks), dyntok.merges, dyntok.vmax, dyntok.max_tok,
                            ctx, batch, self.batch_q, self.merge_qs[i], self.stop_ev)) for i in range(n_workers)]
        for p in self.procs:
            p.start()

    def get(self, timeout=60):
        """Pull a ready batch (plain list) and tally its pairs into the main tokenizer (drives minting)."""
        arr = np.asarray(self.batch_q.get(timeout=timeout), dtype=np.int64)
        codes = (arr[:, :-1] * self.vm + arr[:, 1:]).ravel()
        uniq, cnts = np.unique(codes, return_counts=True)
        pair = self.dyntok.pair
        for c, k in zip(uniq.tolist(), cnts.tolist()):
            pair[(c // self.vm, c % self.vm)] += k
        return torch.from_numpy(arr)

    def broadcast(self, merges):                               # tell workers about newly-minted tokens
        for q in self.merge_qs:
            try:
                q.put(list(merges), timeout=0.5)
            except Exception:
                pass

    def stop(self):
        self.stop_ev.set()
        for p in self.procs:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()
        try:
            os.unlink(self._tmp.name)
        except Exception:
            pass


if __name__ == "__main__":
    from tokenizer import DynamicTokenizer
    import data_utils as D
    random.seed(0)
    text = b"the quick brown fox jumps over the lazy dog 0123456789 " * 40000
    chunks = [torch.tensor(list(text[i * 512:(i + 1) * 512]), dtype=torch.long) for i in range(1500)]
    main = DynamicTokenizer(vmax=4096, min_pair=200)
    for _ in range(200):
        D.dyn_batch(chunks, main, 32, 128)
        for _ in range(4):
            main.maybe_grow()
    rep = DynamicTokenizer(vmax=4096, min_pair=10**9)
    for a, b in main.merges:
        rep.apply_merge(a, b)
    w = chunks[7].tolist()
    print("replica matches main segmentation:", main.segment(w, count=False) == rep.segment(w, count=False),
          "| merges replayed:", len(rep.merges))
