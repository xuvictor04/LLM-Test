# STRUCTURES.md — what each structure IS, and a clear name for it [naming pass — PROPOSED]

You asked to CLARIFY what the structures are and establish clear, consistent names before locking terminology. This
project has a documented history of overloaded terms ("domain / expert / node" changed meaning several times), so the
goal is: one clear definition and one canonical name per structure. **All proposed names are `[me]` — confirm or override.**
Once settled, they propagate to code + docs. Status: **PRESENT** (in code today) · **NEW** (about to be built) · **PLANNED** (vision).

## First — what "V" is (the thing that replaced B)
V is the **verification** structure. It answers *"do I actually understand this?"* by **RECONSTRUCTION**: take the
internal representation, run it BACKWARD through a reverse embedder to regenerate the input/expectation, and measure the
error. Low error = understood; high error = not understood. NOT wrongness-detection, NOT surprise. (Name **V / Verify**
proposed; alternatives R/Reconstruct, U/Understand.)

## The loop stages
| What it is | Current name | Proposed | Status |
|---|---|---|---|
| discover the stream's own structure (clusters) | C / self-assemble | **C — Assemble** | PRESENT |
| check understanding by reconstruction | B → | **V — Verify** | NEW (replaces B) |
| update / remove knowledge by provenance | A / edit | **A — Edit** | PRESENT |

## The two signals (the learning controller)
| What it is | Current name | Proposed | Status |
|---|---|---|---|
| "I didn't predict this" → drives learning / where to write / discover | surprise (write-gate) | **Surprise** (learning signal) | PRESENT |
| "I can't regenerate this" → drives verification | — | **Reconstruction error** (verify signal) | NEW |

## Representation & encoders
| What it is | Current name | Proposed | Status |
|---|---|---|---|
| the shared embedding space everything lives in | signature space (`SIG_D`) | **Signature space** | PRESENT |
| forward map: input → signature | `SigEncoder` | **Signature Encoder** (forward) | PRESENT |
| reverse map: signature → input / expectation | — | **Reconstructor** (reverse embedder) | NEW |
| the base sequence model | `MiniLM` / `TinyTransformer` | **Base model** (GRU / Transformer) | PRESENT |

## The populations — one primitive at many grains (subtokenize → embed → match → discover → crystallize)
| What it is | Current name | Proposed | Status |
|---|---|---|---|
| byte-pattern unit | token (`DynamicTokenizer`) | **Token** | PRESENT |
| meaning-unit of a surface form (polysemy) | — | **Sense** | PLANNED |
| emergent cluster of the stream; provenance / edit index | domain | **Domain** | PRESENT |
| independent compute unit (adapter) | expert (was "node") | **Expert** | PRESENT |
| an expert reused across many tasks | — | **Sub-skill** | PLANNED |
| a crystallized procedure / script | — | **Tool-expert** (skill-script) | PLANNED |

## Routing & composition
| What it is | Current name | Proposed | Status |
|---|---|---|---|
| the routing + composition layer experts sit in | `Fabric` | **Fabric (router)** — *overloaded, see below* | PRESENT |
| how many experts' outputs blend | `ENS_K` / ensemble | **Ensemble** | PRESENT |
| trains each top expert to solve alone (redundancy) | independence loss | **Independence loss** — *under revision → subcontracting* | PRESENT |
| router keys as EMA centroids in signature space | grounded routing | **Grounded routing** | PRESENT |
| router that embeds input → nearest expert | (partial) | **Router-as-embedder** | PLANNED |

## Memory (the knowledge base)
| What it is | Current name | Proposed | Status |
|---|---|---|---|
| the editable external store | `EditableMemory` | **Memory** (editable store) | PRESENT |
| one key→token record with provenance + pos | entry | **Entry** | PRESENT |
| which domain wrote an entry | `src` / provenance | **Provenance** | PRESENT |
| built-in retrieval over the store | read / kNN | **Retrieval** | PRESENT |

## Overloaded / risky names to settle (these need a call)
- **Fabric** — means the routing+composition layer AND (loosely) the whole society. Split into **Router** (selection) +
  **Compositor** (output blending)? Or keep "Fabric" as the umbrella?
- **Population grades** — Expert (unit) vs Sub-skill (reused expert) vs Tool-expert (crystallized script): confirm this three-grade hierarchy and its names.
- **Domain vs Sense** — the SAME emergent mechanism at window-grain vs token-grain. Name them explicitly as siblings?
- **Signature space** — one space carrying domains, senses, AND expert routing keys. Confirm it stays one named space.

## What needs your input
Confirm / override the proposed names — especially **V**, **Fabric**, and the **population grades**. Once set, I'll
propagate them, then proceed to the **full V integration + fix anything broken** (the build approach you chose).
**Source:** user, session 2026-07-21 (naming pass requested).
</content>
