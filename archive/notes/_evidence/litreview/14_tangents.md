# The two tangents

## Neuroevolution × gradient descent — yes, it has a name and a literature

**You are reinventing something, but only partly, and the part you're not reinventing is the
interesting part.**

### What has a name

The hybrid itself is a defined, decades-old thing. Miikkulainen's encyclopedia entry on
Neuroevolution lists it as one of the three defining properties of the field: neuroevolution
allows combining **evolution over a population of solutions with lifetime learning in
individual solutions**, where the lifetime learning is backpropagation or Hebbian. So
"population + fitness + crossover + mutation, with backprop inside" is not novel; it is a named
configuration. Terms to search under: **Lamarckian evolution** (when learned weights are written
back to the genotype), **memetic algorithms** (evolution + local search, the general framing),
and **Evolutionary Deep Learning / neuroevolution with box mutation** for recent PyTorch-era
work that explicitly mutates architectures while using backprop for parameters.

Your specific operators map onto standard ones:

| Your term | Standard term |
|---|---|
| birth | complexification / structural mutation (adding a node) |
| grace period | **speciation protection** in NEAT — new structures are protected from being outcompeted before they've had time to optimize |
| fitness ranking + culling | selection / truncation selection |
| mutation, crossover | mutation, crossover (NEAT uses historical markings to align genes) |
| rescue | no clean standard equivalent; closest is elitism or re-seeding |

**Grace period is worth flagging specifically.** NEAT's speciation exists *precisely* because a
newly-added structure is initially worse than the incumbents and would be culled before it
could prove itself. Stanley's argument is that innovation needs protection from immediate
competition. That is your grace period, invented for the same reason, and it means there is
prior art you can cite for the design and prior analysis of how long the protection should
last.

### What does not have a name

Every system above evolves a **population of separate networks**, each independently trained.
CoDeepNEAT co-evolves *modules* and *blueprints* — the closest structural match — but they are
still assembled into separate candidate networks that are evaluated independently. Population-
Based Training perturbs hyperparameters across a population of whole models.

**Your population lives inside one network, is trained by one shared backward pass, and its
fitness is measured on shared routing mass.** That means:

- Fitness is not independent. An expert's measured fitness depends on what the router sends it,
  which depends on every other expert. You have frequency-dependent selection — an ecology, not
  a tournament. This is why the file-02 paper reaches for ecological language even though its
  execution is weak; the framing is apt even if the paper isn't.
- Crossover between two experts inside a live network is a genuinely odd operation. In NEAT,
  crossover produces an offspring that is then evaluated standalone. In yours, the offspring is
  spliced into a running system whose router has learned assumptions about the parent. This is
  the same problem as function-preserving growth (file 06) and the growth literature's answer —
  make the operator loss-preserving — is probably the relevant one.
- There is no separate evaluation phase. Fitness and training are the same forward pass.

**Assessment:** the hybrid is not novel, the operators are not novel, but *within-network
population dynamics under a shared router* is a coherent thing that the neuroevolution
literature does not cover and the MoE literature covers only as "load balancing." Framing your
Fabric that way is both more honest and more distinctive than framing it as novel evolution.

**One unverified lead worth chasing:** DeepMind's **PathNet** used a genetic algorithm to select
pathways through a single fixed network trained by SGD, for continual learning. If my
recollection is right, that is the closest published thing to within-network evolution + backprop.
**I did not verify it this session — check it before relying on it.**

**Confidence:** high on the named-hybrid claim (read in the Miikkulainen source); moderate on
the NEAT speciation mapping (well-known but not re-read here); low on PathNet.

---

## Online vocabulary growth — common in one form, unusual in yours

### The form that is common

Adding tokens to a pretrained vocabulary and resizing the embedding matrix is a **large and
active literature**, mostly under language adaptation and domain adaptation. Representative
points:

- Chau et al. 2020 extend multilingual BERT; Wang et al. 2020 extend to low-resource languages
- Kim et al. 2024 add **8,960 Korean tokens to SOLAR-10.7B** with progressive unfreezing
- AdaptiVocab (arXiv:2503.19693) replaces removed tokens with domain n-tokens
- Chemistry vocabulary extension on Llama3-8B (arXiv:2511.14365)
- Estonian extension of Llama-3.2-3B (arXiv:2512.03989)
- Defragmenting Language Models (arXiv:2604.16656) — **continues the BPE merge process on new
  training data to extend a pretrained tokenizer's merges.** This is the closest published thing
  to what you're doing, and it's the paper I'd read first.

Three axes: **expand** (grow the matrix), **replace** (new tokenizer, reinitialize all), or
**reallocate** (keep vocab size fixed, swap which tokens exist — arXiv:2608.00582).

### Initialization of the new rows — the settled part

Standard baseline is **mean of constituent token embeddings** (used by Casanueva et al. 2020,
Hofmann et al. 2021, Sachidananda et al. 2021, Liu et al. 2023). The chemistry paper used the
mean of *all* existing embeddings, which is cruder. More elaborate schemes exist — FVT, OFA
(convex combination of source embeddings), HyperOFA (hypernetwork), description-based
initialization — and all of them beat random.

**Random/He initialization for new rows is documented but is the weak baseline.** If you're
minting merges and initializing randomly, switching to mean-of-constituents is a free
improvement with a large citation base behind it.

### The failure mode you should actually watch for

This is the concrete finding worth the whole section. From arXiv:2512.03989, analyzing
embeddings of newly-added tokens during continued pretraining:

**New tokens become undertrained, and weight decay drives their embeddings toward zero.** They
measured L2 distance from initialization and change in L2 norm, and found naive extension
produced noticeably more undertrained tokens — smaller L2 changes and *a longer tail of
negative L2-norm differences*, i.e. embeddings shrinking rather than learning. Vocabulary
utilization was correspondingly lower.

**Why this is severe in your setting specifically.** A token minted late in training appears
rarely (that's why it wasn't minted earlier), so it gets few gradient updates — but weight decay
applies to its row on **every** step regardless. The decay-to-update ratio for a rare new token
is unboundedly bad. In continued-pretraining papers the exposure is at least bounded by a known
finetuning budget; in your setup, if merges are minted continuously, your newest tokens are
permanently in the worst regime.

**Three things I'd do:**
1. Exclude embedding and unembedding rows for newly-minted tokens from weight decay for some
   grace period after minting. (Note: this is the same "grace period" idea as your expert births
   — same underlying problem, newborn units can't survive competition immediately.)
2. Log per-token L2 norm of new rows vs age-since-minting. The diagnostic is nearly free and it
   directly detects the failure.
3. Initialize new rows as the mean of their constituents, not randomly.

**One more thing you already have and should exploit:** because you're changing vocabulary
mid-run, **perplexity is not comparable across your own checkpoints.** Bits-per-byte is. You
are already using b/B, which is the right call for exactly this reason — make sure nobody on
the team reports a PPL number across a vocab change.

**Novelty assessment:** minting merges *during* pretraining rather than at a fixed adaptation
point is unusual and I found no paper doing it. The tokenizer literature all assumes a discrete
adaptation event on a fixed pretrained model. **That is a genuine gap.** But you should expect
reviewers to ask about the undertrained-token effect above, so measure it before they ask.
