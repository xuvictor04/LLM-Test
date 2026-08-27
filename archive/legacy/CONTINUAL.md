# Continual learning: emergent tokenizer + system

The tokenizer and the system co-train, and new domains are streamed in from `data/continual/`, one shift
at a time. Two strategies, selected by `CONTINUAL_MODE`.

## plastic (default) — shared, fully-plastic + experience replay
ONE shared network: a gist-routed pool of `N_EXPERTS` **shared** experts that every domain uses and keeps
updating, plus a bounded reservoir **replay** buffer that rehearses past domains while learning new ones.
Nothing is frozen; knowledge integrates in shared weights.
- **Verified** on a chain (prose+Python base → C → Rust → numbers): every new domain was learned AND the
  earlier domains **improved** as later ones arrived — *backward transfer* of prose −0.26, Python −0.23,
  C −0.15 bits/byte — which a frozen stack structurally cannot do (it can only hold or drift up). The
  shared experts **specialized without collapsing**: each domain has a distinct routing signature, and the
  two code domains (C, Rust) share the same experts (cross-domain reinforcement visible in the routing).
- **Cost:** keeps a bounded replay buffer of past windows (`REPLAY_CAP`); forgetting is held down by
  rehearsal rather than guaranteed, so at very large domain counts (buffer thinning) some forgetting can
  return. Part of the backward-transfer gain is that old domains keep training via replay — a real
  advantage a frozen expert forecloses, but not purely cross-domain transfer.

## frozen — compounding gated-expert stack (`CONTINUAL_MODE=frozen`)
Each shift adds a gist-gated expert, frozen after training, on top of the accumulated stack.
- Guaranteed ~zero forgetting; a new domain is gist-gated so old domains' logits stay untouched.
- **Verified:** a distinct-gist shift (Rust) recovers to ~2.6 bits/byte with the gate firing ~0 on old
  domains; an overlapping-gist shift (Sherlock prose) makes the gate fire 0.58 on the old prose domain yet
  that domain drifts only −0.04 (benign leak — the overlap means the leaked learning is relevant).
- **Cost:** parameters grow by one expert per shift (linear); no backward transfer (old experts frozen).

## Run
    python get_data.py                          # or place your own files
    # data/train/<domain>/*.txt ; data/continual/01_<name>/*.txt ; 02_<name>/ ...
    python continual_tokenizer.py               # plastic (default)
    CONTINUAL_MODE=frozen python continual_tokenizer.py
Logs per-domain bits/byte before/after each shift to `runs/continual_log.jsonl`, including
`drift_vs_first_seen` (negative = that domain improved after later domains were added).

## Honest scope
Toy-scale validation on CPU; the *relative* properties (stability, plasticity, backward transfer,
collapse-free routing) are the point, not absolute perplexity. The decoupling/novelty signal separates
genuinely-novel domains from familiar ones — it stays (correctly) quiet for unseen samples of seen types.
