# Glossary — terms as actually used in this codebase

Several overload common ML words; a few (node, expert) meant different things at different points. This is the CURRENT
meaning of each. Numbers live in `../STATE.md §7`; this file defines terms, it does not restate results.

**Domain** — a self-assembled cluster in signature space, created/merged/culled by `DomainAssembler` as the stream is
read. Its only functional job is PROVENANCE: memory entries and (if `SOCIETY=1`) expert routing traffic are tagged by
domain, so a domain can be looked up and its memory deleted. It does **not** partition retrieval (retrieval is always a
global kNN) — over-segmenting into many domains costs nothing in prediction quality. Not the same as a "true process"
in the test data (there are usually far more domains than true processes — expected, not a bug).

**Expert** — an independent computational unit: a small residual adapter with its own parameters, mapping the base
model's hidden state to its own output. Selected/blended by the router. The current unit of deletion for the headline
result. Superseded two rejected designs (a 1:1 domain-tied bank; and a "node").

**Node** — an abandoned name for what an expert is inside the "fabric." In old comments/history, "node" = today's
"expert"; renamed once the chained/entangled fabric was rejected for the society design.

**Fabric** — RETIRED name (2026-07-21). It conflated two jobs, now split into **Router** (selects which experts) and
**Compositor** (blends their outputs, `fab_logits`). The code flag `FABRIC=1` and identifier keep the old name until the
build renames them. Historical: a *chained* fabric (rejected, `SOCIETY=0`) fed each step's blend into the next step,
entangling experts; the current *society* (`SOCIETY=1`) has each expert map the shared base representation to its own
output independently, blended once at the end by the Compositor.

**Router** — selects which experts handle the input (routing by grounded keys / similarity). **Compositor** — blends the
selected experts' OUTPUTS (`Σ wᵢ·head`, never hidden states) into the final prediction. (Together = the retired "Fabric".)

**Sense** — a MODALITY / perceptual channel (input AND output), integrated at the LOWEST tokenizer layer. One sense today
= language (the system is an LLM). Adding a modality = adding a sense (mic → audio, camera → vision) — the multimodality
"pluggable avenues" goal. NOT the same as polysemy (multiple meanings of one surface form; that's provisionally "Meaning").

**Society** — shorthand for the current expert architecture: independent experts + prediction-level ensembling + an
independence loss training each expert to solve the task alone. The opposite of a "decomposition" (parts that only work in combination).

**Ensemble (`ENS_K`)** — how many top-routed experts' OUTPUTS (not hidden states) get blended into the final prediction, weighted by routing mass. `ENS_K=2` default.

**Prediction-level vs hidden-state blending** — a real, previously-buggy distinction. Averaging experts' HIDDEN STATES
before decoding produces a representation none was trained to emit (degenerate generation, broken self-check). Averaging
their DECODED predictions (`Σ wᵢ·head(oᵢ)`, via `fab_logits`) does not. Keep it the latter.

**Independence loss** — trains each top-`IND_K` routed expert to independently predict the target, weighted by routing mass, on top of the ensembled loss. This is what makes deleting one expert cost little. NOTE (direction): the user wants work SUBCONTRACTED / distributed via the router rather than each expert solving the whole task alone — a proposed revision to this premise; see `design-directions/interchangeable-base-with-emergent-subspecialties.md`.

**Grounded routing (`ROUTE_GROUNDED`)** — expert routing keys as EMA centroids in signature space (like domains), not
freely-learned keys. Free keys stay symmetric → every expert serves every domain equally (redundancy). Grounded +
sharpened (`ROUTE_T` low) breaks symmetry into real, uneven constituencies (modularity).

**Redundancy vs modularity** — the two characterized regimes. Redundancy: every expert interchangeable, deletion free, no
specialization. Modularity: experts specialize, deletion costs something but CONCENTRATED on what that expert served
(auditable). Not a bug either way — a genuine open fork (`../STATE.md §4 Q-regime`).

**Affiliation map** — a DIAGNOSTIC (not a deletion mechanism) reporting which experts serve which domains and by how
much; used to preview the "blast radius" before deleting a domain. Revealed 0 exclusive experts in every run → domain
deletion must RELEASE affiliations, not cascade-delete experts.

**Memory / A (edit)** — the external key→token store with per-entry provenance. Deleting by provenance is the oldest, most consistently proven result. Surprise-gated writes; `pos` records the source byte position.

**Verification** — *renamed from B (wrongness).* Verification by RECONSTRUCTION: reverse-embed the representation and
compare to the original/expectation ("can I regenerate this from my understanding?"), DECOUPLED from surprise. Replaces
the old B, which was self-consistency-on-surprise and stuck at ~1% precision (surprise ≡ its detection signal — a
category error; surprise drives learning, not truth). See `decisions/B-renamed-to-Verification-reconstruction-based.md`
and `design-directions/reverse-embedders-for-thought-verification-and-training.md`. (Old code names `is_wrong`/`selfcheck`/`sweep_wrong` persist until the build replaces them.)

**C (self-assemble)** — the domain-discovery loop. Works; over-segments; harmless. The signature encoder reads the BYTE stream (not tokens).

**Online tokenizer (`TOK_ONLINE`)** — byte-grounded BPE that mints tokens DURING training as it reads the stream, not in a pre-pass. Lossless (falls back to raw bytes for unmerged pieces).

**Garry** — the frozen milestone snapshot in `garry/` (redundancy regime, 1.967 b/B, −0.0009 expert-deletion collateral). Do not edit it; it is the fallback reference.

**BATCH_W** — batched-window LM training (throughput fix). Domain assembly + memory writes stay strictly per-window/sequential. Caveat: scale `STREAM_LEN` WITH it or the model sees fewer optimizer steps.
</content>
