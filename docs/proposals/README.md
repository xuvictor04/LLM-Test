# Proposals — designs agreed in principle, not yet built

Everything here is **future work with an owner's decision behind it and no implementation**. Each
document gets its own git branch when it starts; none of them is on `rm-predict-DC`, and nothing in
`src/` implements any of it.

A proposal here is *not* a question. The questions live in `docs/04_CONTRACT.md` under **FOR THE
OWNER** and are about the system as it stands. These are about the system as it is meant to become,
and the owner has already said they want them. What each document does is work out **what the
current architecture forces**, so the branch starts from a set of constraints rather than a blank
page — and raise the questions that only the design work can surface.

| # | Proposal | Branch | Status |
|---|---|---|---|
| 01 | [Modalities](01_MODALITIES.md) — image, audio and video, read and generated, through the common router | *not yet cut* | design only |
| 02 | [Router recursion](02_ROUTER_RECURSION.md) — stacked independent routers, experts at the leaves, results passed up | *not yet cut* | design only |
| 03 | [Audio and video](03_AUDIO_VIDEO.md) — understand and generate, codecs learned from scratch, synthetic first; supersedes 01's build order for audio and video | *not yet cut* | design, reviewed (sound with fixes, all adopted in its §0) |

**They are one change wearing two names, and the order matters.** Proposal 02 is what makes 01
tractable: a flat population routed by one signature has to put an image window and a text window in
the same 64-dimensional space and compare them, and there is no good answer to that. A hierarchy
lets the top of the tree route by *modality* and the leaves route by *content within a modality*,
which is a question each level can actually answer. So 02 is the load-bearing one and should be
built first, on synthetic multi-modal data, before 01 brings real encoders and decoders.

**UPDATE 2026-09-25: the ordering below is superseded for audio and video by Proposal 03.** The tree now trains end to end (the 2026-09-24 GPU fleet ran 20,000-window runs), so the precondition in the next paragraph is met. Proposal 03 routes media through the existing flat router with a typed signature and makes 02's modality top CONDITIONAL: it lands only if the S5 measurement (M2) finds flat domains below 0.95 modality purity on the mixed stream. The text below is kept as written.

**Neither is started until P3 runs.** 116 of 121 entry points are still stubs and nothing trains yet.
A hierarchy of routers over a population that has never routed anything is unfalsifiable — every
number it produced would be about the scaffolding.

## The standing rules these inherit

Anything built from these documents is still bound by the architecture, and the documents work out
what that costs rather than asking for an exemption:

- **No cross-package imports.** A package may import stdlib, torch and `spine.{lever, units, derive,
  rng, wire}`. Cross-package values arrive as arguments the spine assembled.
- **One environment reader**, generated names, frozen Configs, a latched assembly.
- **Wires are build-time.** A coupling's compute sees only frozen Configs, so a value *measured* at
  runtime can never be a wire, however much it looks like one.
- **Clock kinds are checked** and cross-kind conversions are named functions in `spine.derive`.
- **DID IT FIRE.** Every gated mechanism answers `fired N` / `armed but 0` / `unreachable`, and a
  guard whose condition cannot be satisfied is a defect even where the code is correct.
- **The two definitives**: good language production with room for further modalities; continual
  learning without catastrophic forgetting. Everything else is a preference.
