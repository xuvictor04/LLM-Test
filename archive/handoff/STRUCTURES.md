# STRUCTURES.md — what each structure IS, and its canonical name [names CONFIRMED 2026-07-21]

The system's structures with one clear definition + one canonical name each. Names below are **CONFIRMED by the user**
except where marked OPEN. Status: **PRESENT** (in code today) · **NEW** (about to be built) · **PLANNED** (vision).

## Confirmed this session
- **Verification** (was "B / wrongness") · **Router** + **Compositor** (was "Fabric", now retired) ·
  **Expert → Sub-skill → Tool-expert** (population grades) · **Domain** (kept) · **Sense = a MODALITY** (see below).

## The loop stages
| What it is | Name | Status |
|---|---|---|
| discover the stream's own structure (clusters) | **C — Assemble** | PRESENT |
| check understanding by RECONSTRUCTION (reverse-embed → compare) | **Verification** | NEW (replaces B) |
| update / remove knowledge by provenance | **A — Edit** | PRESENT |

## The two signals (the learning controller)
| What it is | Name | Status |
|---|---|---|
| "I didn't predict this" → drives LEARNING (where to write / discover) | **Surprise** | PRESENT |
| "I can't regenerate this" → drives VERIFICATION | **Reconstruction error** | NEW |

## Representation & encoders
| What it is | Name | Status |
|---|---|---|
| the shared embedding space everything lives in | **Signature space** | PRESENT |
| forward map: input → signature | **Signature Encoder** | PRESENT (`SigEncoder`) |
| reverse map: signature → input / expectation | **Reconstructor** (reverse embedder) | NEW |
| the base sequence model | **Base model** (GRU / Transformer) | PRESENT |

## The populations — ONE primitive at many GRAINS (subtokenize → embed → match → discover → crystallize)
| What it is | Name | Status |
|---|---|---|
| byte-pattern unit | **Token** | PRESENT |
| emergent cluster of the stream; provenance / edit index | **Domain** | PRESENT |
| independent compute unit (adapter) | **Expert** | PRESENT |
| an Expert reused across many tasks | **Sub-skill** | PLANNED |
| a crystallized procedure / script | **Tool-expert** | PLANNED |

## Senses = MODALITIES (a DIFFERENT axis — the multimodality avenue) [USER]
A **Sense** is a perceptual/modality channel (input AND output), integrated at the LOWEST tokenizer layer. The system is
**one sense today — language** (an LLM). Adding a modality = adding a sense: attach a mic → an **audio** sense; a camera →
a **vision** sense. This IS the north-star "pluggable avenues" / multimodality goal. Senses are PARALLEL channels — each
runs the population primitive at its own token grain, feeding the shared signature space. (See
`designed-but-not-built/multimodality-pluggable-avenues.md`.) **PLANNED** (one sense present).

## Routing & composition (Fabric RETIRED — split into two honest names) [USER]
| What it is | Name | Status |
|---|---|---|
| selects which experts handle the input | **Router** | PRESENT (in `Fabric`; code flag `FABRIC=1` until renamed) |
| blends the selected experts' OUTPUTS into the prediction (`Σ wᵢ·head`) | **Compositor** | PRESENT (`fab_logits`) |
| how many experts' outputs blend | **Ensemble** (`ENS_K`) | PRESENT |
| trains each top expert to solve alone (redundancy) | **Independence loss** — *under revision → subcontracting* | PRESENT |
| routing keys as EMA centroids in signature space | **Grounded routing** | PRESENT |
| Router that embeds input → nearest expert | **Router-as-embedder** | PLANNED |

## Memory (the knowledge base)
| What it is | Name | Status |
|---|---|---|
| the editable external store | **Memory** | PRESENT (`EditableMemory`) |
| one key→token record with provenance + pos | **Entry** | PRESENT |
| which domain wrote an entry | **Provenance** | PRESENT (`src`) |
| built-in retrieval over the store | **Retrieval** | PRESENT |

## Still OPEN (needs a name)
- **Polysemy / multiple-meanings-per-surface-form** — the "which vector when a surface form has multiple meanings" idea.
  This is NOT a Sense (Sense = modality). Provisional: **"Meaning"**. Confirm or override. (Lives in the knowledge-base
  design direction.)

> NOTE: code identifiers (`SigEncoder`, `Fabric`, `fab_logits`, `is_wrong`, `selfcheck`, `FABRIC=1`) keep their old
> names until the build renames them; these are the DOC-level canonical names to migrate toward.
**Source:** user, session 2026-07-21 (naming pass).
</content>
