# Proposal 01 — Modalities: image, audio and video, read and generated

**Status: design only.** Nothing in `src/` implements this. It gets its own branch when it starts,
and it should start **after** Proposal 02 — the reason is in §*Why 02 comes first*.

## The owner's words, verbatim

> Also, for next steps, I want to add a fully integrated video image and audio generator and reader.
> (Along with the world model, and other stuff to be generated) again, everything should be routed
> through the common router.

Four claims: **generator and reader** (both directions, not captioning alone); **fully integrated**
(not a bolt-on pipeline); **the world model and other things to be generated** belong in the same
frame; and **everything routes through the common router** — one router, not one per modality.

## This is goal A's second clause being cashed in

The two definitives are *"good language production, with room for additional modalities to be
strapped on later"* and *"continual learning without catastrophic forgetting."* This proposal is the
first half's second clause. That matters for how it is judged: **it is not a new goal, it is the
goal the architecture was shaped to allow**, so the test of the design is whether the existing
shape absorbs it or has to be bent.

Mostly it absorbs it. The places it does not are below, and they are specific.

## What exists today

| | today | what a modality needs |
|---|---|---|
| **stream** | `DATA` yields bytes; `DATA.stream_bytes` (120000) | frames, samples, patches — and a window that means something in each |
| **window** | `LM.ctx` (128) **tokens**; `step` advances once per window | a window in each modality, and one clock that spans them |
| **tokenizer** | `TOK`, online byte-BPE, `TOK.max_bytes` (24) | a discretiser per modality, or a shared continuous space |
| **signature** | `SIG.encode` → `SIG.d`=64 vectors, `SIG.space='bytes'` | **the crux — see below** |
| **model** | `LM`, `arch='gru'`, one token vocabulary of `LM.vocab_slots` rows | a head per modality, or one head over a joint vocabulary |
| **generation** | none. `LM.decode` produces logits; `EVAL.generate` is a **P6 stub** | sampling in each modality |
| **world model** | `WORLD.forecast(world, w, obs_emb)` — forecasts latents, `WORLD.lat` | already a generator in latent space |
| **metric** | bits per byte, on a held-out tail | bits per *what*, per modality — and one number that compares |

Three of those are worth stating plainly rather than as a table row.

**The router's only input is the signature**, and it is 64 dimensions of byte statistics. Every
routing decision in the system is made on `SIG.encode`'s output. A modality that cannot produce a
comparable signature cannot be routed, and *"everything should be routed through the common router"*
is therefore a constraint on `SIG` before it is a constraint on anything else.

**`bytes_per_token` is MEASURED**, on a corpus the tokenizer has not seen when `build()` freezes —
which is why the signature width is `derive.signature_width_bytes` called once and kept, and **not**
a wire. Every modality adds a measured quantity of the same shape, and each one is a value that
cannot become a coupling however much it looks like one.

**Nothing generates anything yet.** `EVAL.generate` returns a Sample and is deferred to P6;
`LM.decode` produces logits and no sampler exists. So "generator" is new work in text as well, and
building the text sampler first is the cheap way to find out what the interface has to be.

## Why 02 comes first

*"Everything should be routed through the common router"* has a straightforward reading that does not
survive contact with the signature: put an image window and a text window in the same 64-dimensional
space and let one flat router compare them.

That asks the signature encoder to make *"this is a photograph of a cat"* and *"this is Python
source"* comparable **as points**, on an axis where nearness means *should be handled by the same
expert*. There is no reason to think that space exists, and one strong reason to think a flat router
would collapse onto modality: modality is the largest source of variance in the input, so a
contrastive encoder minimising its objective will spend its 64 dimensions separating image from text
and have little left for separating *kinds of text* — which is the distinction goal B needs.

**A hierarchy makes the question answerable at each level.** The top routes by modality, which is a
question a 64-d signature *can* answer. A leaf routes within one modality, where the signature can
be modality-specific and the comparison is between things of a kind. That is Proposal 02, and it is
why it is the load-bearing one.

**This is a prediction, not a finding, and it is falsifiable.** It can be measured before either
proposal is built: train `SIG` on a mixed corpus and look at whether the leading dimensions separate
modality or content. If a flat signature turns out to carry both, the hierarchy is not needed for
*this* reason — and the measurement is cheap next to either build.

## What the architecture forces

### Ownership: one package per modality

Adding `IMG`, `AUD` and `VID` as packages with their own `PREFIX` is the shape that costs least and
buys most. Names are **generated** as `PREFIX_FIELD`, so `IMG_PATCH` and `AUD_HOP` are unforgeable
and the census stays a complete index. 13 packages become 16; nothing about the spine changes.

The alternative — modality as a *lever* on the existing packages, `DATA_MODALITY='image'` — is worse
for a reason the census already records twice: a knob that changes what other knobs *mean* is the
coupling class, and `LM.ctx` meaning tokens under one setting and patches under another makes every
number in the report ambiguous about which run produced it.

### The clock question is the sharp one

`step` advances once per **window** and everything is denominated against that. A text window is
`LM.ctx` tokens. An audio window is some number of samples; a video window is some number of frames;
an image is arguably one window or many patches.

`spine/units.py` has `Steps, Flushes, Windows, Backwards, Epochs, Selections` and comparing across
kinds raises `UnitError`. **The design decision is whether `Windows` stays one kind across modalities
or splits.** Both have a real cost:

- **One kind**: a video window and a text window are the same unit, so `manage_every=500` means the
  same thing everywhere — and it silently means *different amounts of content*, since a video window
  carries orders of magnitude more information than a 128-token text window.
- **Split kinds** (`TextWindows`, `AudioWindows`, …): the type system refuses the conflation, which
  is what it is for — and every cadence lever multiplies by the number of modalities, and every
  cross-modal comparison needs a **named conversion in `spine.derive`**, which is the rule.

The second is more honest and more work. **It should be decided before any encoder is written**,
because it is the decision that is invisible at small scale and expensive to reverse — exactly the
shape of the defect that made the pin clock read 43,645 real ticks as 2,650.

### The metric has to survive the crossing

Everything is reported in **bits per byte** on a held-out tail. For images and audio, bits per byte
of *what* — the raw file, the patch encoding, the discretised token? The three differ by large
constant factors, and a report that compares them without saying which is the wrong-measurement
family (98 records) at the level of the whole system.

This is P5's territory. `Reading` cannot be constructed without its value, its unit, the `Sample` it
came from, its estimator and its null (graft G6) — so **the instrument line already has a place to
put the answer**, and the modality branch should be the thing that proves that design carries its
weight rather than discovering it does not.

### Generation is a second direction the contract does not have

Every entry point today is read-side. Generation adds, per modality, a sampler, a decode path, and a
*quality* question that bits-per-byte does not answer — `EVAL.coherence` and `EVAL.generate` exist as
P6 stubs for text and both are deferred, one of them on a contradiction between its own signature and
its docstring (**Q-EVAL-10**).

**Build the text sampler first.** It is the cheapest way to find out what the interface has to be,
it is needed for goal A regardless, and it makes the multi-modal version a second instance of a
shape that already works rather than the first instance of a shape nobody has tried.

### The world model is already a generator

`WORLD.forecast(world, w, obs_emb)` predicts in a `WORLD.lat`-dimensional latent space. The owner
groups it with *"other stuff to be generated"*, which is right: a forecaster over latents is a
generator whose decoder is missing. If modalities share a latent space, `WORLD` is where the
cross-modal prediction would live — and `WORLD.feedback` already exists as the switch that lets its
output re-enter the loss.

That makes `WORLD` the most likely place for the design to become *"fully integrated"* rather than
three pipelines sharing a router. It is also the package with the least implemented (**0 of 8 entry
points**) and one open question about whether its cadence is even the right kind (**Q-WORLD-6**).

## Questions this raises

| # | Question | Why it matters |
|---|---|---|
| M1 | Does `Windows` stay one clock kind across modalities, or split per modality? | The decision is invisible at small scale, expensive to reverse, and is the exact shape of the project's most repeated defect. |
| M2 | One signature space or one per modality with a shared top level? | Decides whether Proposal 02 is a prerequisite or an option. **Measurable before either is built.** |
| M3 | Bits per byte of *what*, per modality — and what makes two modalities' numbers comparable? | Without an answer the report can compare things that are not comparable, and P5's `Reading` is where the answer has to live. |
| M4 | One package per modality, or modality as a lever? | Names are generated from `PREFIX`; a knob that changes what other knobs mean is the coupling class. |
| M5 | Does each modality get its own tokenizer, or is there one joint vocabulary? | `LM.vocab_slots` is the model's row count and `TOK` may not mint past it — one wire, or three. |
| M6 | Is a still image one window or many patches? | Decides whether images have an internal sequence at all, and therefore whether `LM.ctx` means anything for them. |
| M7 | Does generation share the routed path with reading, or is there a second forward? | `ISSUES P1-C4/C5` are what happens when a second path resolves a shared quantity differently — the eval signature came out at one byte while training used 614. |
| M8 | Where does cross-modal prediction live — `WORLD`, or a new package? | `WORLD.forecast` is already a latent generator with a `feedback` switch. |
| M9 | What is the held-out split for a modality with no natural byte order? | `Q-DATA-6` asks this for text and is unresolved; images make it sharper. |
| M10 | Does adding a modality count as **adding an area** for the continual-learning benchmark? | If yes, this is goal B's benchmark and the R matrix (graft G8) has to carry it. If no, say what it is instead. |

## What to build first

1. **Measure M2** on a mixed corpus, before committing to either proposal's premise. Cheapest
   experiment here and it decides the shape of both.
2. **The text sampler** — needed for goal A anyway, and it defines the generation interface.
3. **One second modality end to end**, read *and* generated, on synthetic data with a known
   structure. Two modalities is where every cross-modal question becomes concrete; three is where it
   becomes expensive to change the answer.
4. **Video last.** It is audio and images with a time axis, and the time axis is M1 — the question
   that should already be answered by then.
