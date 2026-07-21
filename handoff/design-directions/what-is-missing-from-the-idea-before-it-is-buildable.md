# What's missing from the idea before it's buildable — the gap list [build-readiness]

The vision is internally coherent (see the other `design-directions/` files). These are the gaps that must be resolved
to turn it into code. Grounded in the current code: forward encoders exist (`SigEncoder` byte→signature at
`self_organize.py:355`; `MiniLM.encode` hidden=key source at `:129`); the old B is `selfcheck` (`:565`) +
`memory.py` `set_selfcon`/`is_wrong`/`sweep_wrong`. **Nothing decodes back from the representation** — the reverse
embedder is entirely new.

## The keystone gap (blocks everything)
1. **Reconstruction TARGET: content or function?** Does the reverse embedder regenerate the SURFACE (input bytes/tokens)
   or the FUNCTION/effect (what a sub-skill does)? This single choice decides whether the embedding space encodes content
   or function — and functional similarity is what routing/reuse/transfer needs. (See
   `routing-is-embedding-plus-similarity-for-reuse-and-transfer.md`.)

## Reverse-embedder / V gaps
2. **Architecture of the reverse embedder** — decode from WHICH representation (SigEncoder signature? LM hidden? memory
   key?) back to what, and is it tied to the forward encoder (autoencoder) or independent?
3. **The V signal + threshold** — reconstruction ERROR as a scalar; what threshold flags "not understood," and is it
   adaptive like the old `is_wrong` (median+k·MAD) or absolute?
4. **What V gates** — does high reconstruction error block INTEGRATION of a new sense/expert, trigger more learning,
   demote a memory entry, or just report? (Handling table in `learning-signal-classification-...`.)

## Signal-classification gaps
5. **The 2×2 in code** — surprise (exists) × reconstruction (new): where each is computed and how the four cells are acted on.
6. **The "modification" step** — the abstraction the router applies before embedding (the candidate content→function bridge). Undefined.

## Structural gaps (later)
7. Meanings (polysemy) at the token layer: bounding vectors/surface-form, reconcile stage, edit propagation. AND Senses
   (modalities) at the lowest tokenizer layer: discovery-on-unusual-input, per-sense tokenizer/embedding into the shared space.
8. Sub-skill routing (router-as-embedder), emergent subspecialties without losing redundancy.
9. Tool-experts: distilling a recurring neural pattern into a script; validation; shared routing space.

## The cheapest first probe (does the core idea even hold?)
Build ONLY a reverse embedder over the existing representation + a reconstruction-error signal, and test the ONE claim
that justifies the whole reframe: **does reconstruction error separate genuine-novel from wrong where surprise cannot?**
Reuse the existing `cl_bench` wrongness harness (inject corruption) but score with reconstruction error instead of
self-consistency, and compare precision. If reconstruction beats ~1% cleanly, the reframe is validated cheaply before
any large build. Small model, short run — the user runs it on the H100; estimate first.
**Source:** grounded read of the code, 2026-07-21.
</content>
