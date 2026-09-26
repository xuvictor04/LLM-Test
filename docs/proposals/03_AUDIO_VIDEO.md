# Proposal 03 — Audio and video: understand and generate, learned from scratch, synthetic first

> **Superseded in part (2026-09-25) by [03b — Nothing frozen](03b_LIVE_CODEC.md).** The owner rejected the frozen codec and the hand-fixed 25 Hz. Where 03b disagrees with anything here, 03b wins; §6 is replaced whole.

Status: **design, reviewed, not built.** The judge's synthesis of three prototyped designs, on tree d97779d (rm-predict-DC), then reviewed by an adversarial critic (verdict: *sound with fixes*). **§0 carries the review's fixes and overrides any sentence below that disagrees with it.** Prototypes, logs and measurements: `results/multimodal_design_2026-09-25/prototypes/{design-stream,design-world,design-hybrid,judge,map,research-codecs,profile}/`; the full workflow output (research, three designs, judge, critic, profile) is `results/multimodal_design_2026-09-25/workflow_result.json`. Every number here is a CPU prototype measurement at toy scale, one seed unless stated: a signal, not a result.

This document supersedes the build-order section of `docs/proposals/01_MODALITIES.md` for audio and video. It answers M1, M3, M4, M5, M8 and M10. It leaves M2 as the first measurement of stage S5.

---

## 0. Revisions from the review — binding over everything below

The critic re-ran the tones inverse (360/360), checked the tree claims it could, and found two
blocking gaps and eight major ones. Each is adopted here as design, not left as a note. Where a
revision needs an owner ruling it says so and gives the recommendation; the recommendation is what
gets built unless the owner rules otherwise.

**R1 — THE TIMELINE IS THE OWNER'S RUN SHAPE: RUN_EPOCHS=1, one ~20 MB stream, 20k windows, batch 1.**
(blocking) The first draft hung the codec encode, clip freshness and the freeze re-encode on the
epoch roll, which at RUN_EPOCHS=1 never happens (Q-RUN-8), and put the freeze at 20,000 windows — the
whole run. The repair is a **codec-independent stream layout**: every clip occupies exactly
`[task marker] BEGIN + F placeholders + END`, with `F = clip_s(family) × derive.frames_per_second(...)`
known from levers at compose. TOK.interleave emits final positions at compose, so `run_windows`,
`windows_in_epoch` and OPT's horizon are right from window 0. At the freeze, AUD.encode writes code
ids into the placeholder positions in place: no window boundary moves, nothing is re-segmented. A
media LM phase before the freeze stays refused. The run reads:

```
window 0 ............ AUD_FREEZE_AT (3000) ............................................ 20000
|  text phases; codec trains on DATA.media_batch   | freeze: encode in place | media phases (share by DATA_TEXT_SHARE)
|  every AUD_TRAIN_EVERY windows (R12)             | OPT shift stamp (R13)   | WORLD.media_terms, EVAL.grounding
```

**R2 — FRESH CLIPS WITHOUT AN EPOCH ROLL, AND SEEDS THAT VARY THE DATA.** Clip i of area a renders
from `derive_seed('data.synth.<key>', RUN_SEED, i)`, so every clip in one epoch is distinct — which
is what the measured *fresh beats a fixed 2.4k set* result needs — and the clips change with the
seed, so media arms do not inherit DEFECT D-A13 (text seeds varied initialisation only). *(Corrected
2026-09-26: D-A13 was already closed for text before the 2026-09-24 fleet -- text seeds varied the
data too; see `docs/04_CONTRACT.md` Q-WORLD-10's correction. The requirement on media stands.)*

**R3 — AUD_FREEZE_AT IS AN int WITH UNIT U.Windows, DEFAULT 3000**, read through an
`AUD.freeze_at(aud) -> Windows` accessor (K9 refuses a bare lever read as a cadence), plus an AUD
startup refusal when `freeze_at >= planned run windows` while a media phase is scheduled. S3's CPU
acceptance already asks for a usable codec in 5 CPU-minutes, well inside 3000 windows.

**R4 — HOW MEDIA AREAS ENTER THE STREAM.** (blocking) Media areas are not text areas:
- a new `Areas.media` dict beside `Areas.bodies`, so TOK's build corpus, `bytes_per_token` and
  exposure stay text-only BY CONSTRUCTION (closes the measured 9% signature-width shrink);
- DATA_PHASE_SCHED names resolve over `bodies ∪ media`;
- inside a phase that lists media areas, **DATA_TEXT_SHARE (0.3) is the one lever that sets the
  amount**; the even per-phase byte split applies to the text areas' share only;
  DATA_MEDIA_SECONDS is removed, and media seconds and media windows per phase become a startup
  READING through a data_plan Gate (at the old 600 s default media would have been ~170 windows,
  under 1% of a 20k run);
- media segments are drawn INSIDE draw_stream while the phase fill is computed, so splice_starts,
  area_changes, phase_bounds and per_area_drawn are produced in final coordinates rather than
  patched afterwards.

**R5 — EVERY ID-INDEXED OPERATION GOES THROUGH ONE JOIN.** Ids ≥ 2^24 would crash `token_seen.index_add_`
(loop.py, a device-side assert on CUDA), and corrupt lm_loss targets, the surprise gather,
`LM.anchor_term` and MEM.write. One root join `_rows_of(ids, modality)` on `derive.token_row` is
applied before each. token_seen gains per-block segments carried in the LOOP payload with a geometry
rule. S4 adds a test driving a full flush over a window with media ids on every arm (FAB, MEM, WORLD
on) and a grep guard over index_add_/gather/bincount/scatter on x or y.

**R6 — CONTRACT ACCOUNTING.** K12 deferral reasons name the unproduced ARGUMENTS, not the consumers
(`wave` has no producer until EVAL.grounding generates clips; `n` and `crop_s` are AUD levers and AUD
does not exist yet). K13's populations all move and are synced with tools/sync_counts.py: the DATA
lever heading, the U.FRACTION count, the census-amendment count, the lever total and the §7
entry-point count. AUD (17 levers, all amendments, 11 entry points with `freeze_at`) and VID are
budgeted the same way.

**R7 — "BIT-IDENTICAL" NEEDS SOMETHING TO BE IDENTICAL TO.** tests/test_determinism.py is a
noise-floor harness, not a baseline. Before S1 touches the tree, the loss trace and integer
fingerprints of `run.py --max-windows 80` (DATA_STREAM_BYTES=120000, one thread) are recorded at the
S1 base commit into a checked-in fixture, and a named test compares against it. (4feb65f is
byte-identical to d97779d on a 300-window merge-firing run, so either serves.)

**R8 — ONE SAMPLE-RATE LEVER.** DATA renders the waves, so DATA owns `DATA_AUD_SR`; the root passes it
to `AUD.build(aud, *, sr=...)` as a Config-derived argument (the `open_store(key_dim=LM.width)`
idiom), costing no wire. AUD_SR is dropped. A duplicated knob guarded by an agreement check is the
SIG_WIN defect the spine exists to refuse.

**R9 — ONLY aud/tones HAS A VERIFIED INVERSE.** It lands first and is the S1 gate family. The vowel
and melody inverses are written and measured in scratch before any test promises 1.0; a family whose
inverse measures below 1.0 has its sanity reading refused, not its test weakened. Clip length is per
family (melody is 4 × 0.64 s = 2.56 s), derived from the family's parameters, so F is exact.

**R10 — GENERATION RECOMPUTES THE WINDOW.** The LM has no incremental-decoding entry point; the first
draft's "GRU state cache / KV cache" was an uncounted frozen-signature move. S2 recomputes the window
per token (O(ctx)); an `LM.step` or `encode(..., state=)` entry point is an S8 arm with its own
ruling and count bump. One grounding pass is timed in-tree at S5 and its cost goes into §12.

**R11 — THE OWNER'S LOSS CURVE STAYS COMPARABLE.** `run.py --loss-curve` keeps TEXT positions only, so
every new curve is comparable with every earlier run; a sibling `media_loss_curve` per modality is
added. The per-modality running baselines FAB competence and DOM.note_competence receive get an
owner: **recommendation — FAB owns them** (state_dict key, restore row, geometry note) and the root
passes DOM its copy as an argument. *Owner ruling.*

**R12 — COSTS ARE CHOSEN, NOT IMPLIED.** At OPT_BATCH_WINDOWS=1, "one codec step per flush" is one
per window: +16-22% on CPU. `AUD_TRAIN_EVERY` (U.Windows, default 4) sets the codec cadence;
modality masks are cached keyed by the window's modality pattern; and a GPU bench arm (RUN_BENCH,
RUN_PROFILE: media off / codec phase / media phase at the owner's geometry under MPS) runs before any
S3 or S4 default is fixed.

**R13 — OPT AT MEDIA ARRIVAL.** The LM's cosine horizon is run_windows, so the first media phase would
arrive on a decayed LR. The freeze stamps an OPT shift exactly as an epoch roll does, so the existing
OPT_LR_SHIFT_WARM re-warm applies; the codec's own parameters are a separate OPT group ('codec',
OPT_CODEC_LR) that retires at the freeze. *Owner ruling (R-OPT).*

**R14 — MINOR.** DATA has no counters() entry point: `data.media.*` rides Stream.counters and gates,
ABSENT with `reachable=False` and reason "DATA_MEDIA_AREAS is empty" when off, and recover /
media_batch return their tallies on their result records. `derive.media_rows` takes the lever's
string form (`media_rows('8,5,5,5') == 1002`, refusing a malformed one), so the LM wire compute stays
inside the allowlist.

---

## 1. Goals and the owner's decisions

The two goals, in the owner's terms:
- **A** is good language production.
- **B** is continual learning without catastrophic forgetting.
Performance is the deciding factor, and no functionality is removed or downgraded.

For video and audio the owner has decided:

| Decision | Consequence in this design |
|---|---|
| UNDERSTAND and GENERATE both modalities | One next-token sampler both reads (media -> caption) and writes (caption -> media codes -> decoder) |
| SYNTHETIC data first; real datasets later into the same slots | Media are DATA **areas**; every synthetic clip carries its generating parameters; a real area has `params=None` and is scored by bits/code only |
| Encoders and codecs LEARNED FROM SCRATCH, no pretrained weights | AUD and VID packages train their codecs in-loop in a codec phase, then freeze and version them. Griffin-Lim is a fixed algorithm with no weights |
| WORLD stays enabled and is included in multimodal training | WORLD trains on every mixed window (existing path) and on a new temporal media head over continuous codec latents. WORLD_FEEDBACK still ships False, and the media feedback is wired and born-zero |
| Owner runs all GPU experiments (140 GiB card) | Every stage ends with a named GPU experiment list (§14) |
| Phase now is "build everything" | Every arm in this document gets built behind a lever; honing chooses defaults later |

Constraints inherited from the tree:
- The Ownership Spine.
- Frozen Configs.
- d_ wires only for declared lever arithmetic.
- No cross-package imports (O10).
- Clock kinds may not be mixed.
- Did-it-fire counters.
- Save, restore and geometry for every checkpointed quantity.
- K/O/N/A test series.
- Throughput: a 20k-window GPU run fell from about 38 to 2-3 windows/s with 12 runs sharing the card. The cause was FAB.manage's scalar merge scan, repaired bit-identically in 4feb65f (docs/04_CONTRACT.md, Q-WORLD-10); the post-repair GPU rate is a projection until the next fleet measures it. Sequence length still costs twice under card sharing.

---

## 2. Decision in one paragraph

Media become **discrete codes in the one sequence the LM already predicts** (early fusion). The codes come from **learned FSQ codecs** (AUD now, VID next) that are trained inside the loop during a codec phase and then **frozen and versioned**.

The codes live at a **fixed transport-id base far above the BPE id space**, in **LM-owned per-modality row tables**. A **per-position modality mask** confines each position's softmax to its own alphabet.

Paired caption<->clip examples train understanding (clip -> caption) and generation (caption -> clip) as next-token prediction, with loss on the **output segment only**. Text windows are bit-identical when media is off.

WORLD trains on the mixed stream through its existing obs_emb path, with cross-modality pairs masked. It also gets a **temporal media head over the frozen codec's continuous latents**. That head is the continuous-prediction half of the design; its forecast feedback is born-zero and ships off.

A modality is an **area**, so adding one is the existing rehearsed add-an-area protocol, measured on the R matrix with exact synthetic grounding scores.

---

## 3. Architecture

```
                         DATA (areas: text bytes | aud/<family> clips+params | later vid/<family>)
                              |  draw_stream: Stream.bytes (TEXT ONLY, bit-identical)
                              |               Stream.media: MediaSegment(at_byte, modality, area,
                              |                             clip_ref, params, task, pair_id)
                 +------------+-------------------------------+
                 v                                            v
     TOK.tokenize (text only;                    AUD.encode (frozen codec, epoch roll)
     bpt measured on text only)                  -> CodecOut(codes (F,), latents (F,64))
                 |                                            |
                 +---------------> TOK.interleave <-----------+
                                    |  ONE Segmentation:
                                    |   ids      text ids | 2^24+k*2^20+{code,BEGIN,END}
                                    |   byte_pos true byte for text; anchor for media
                                    |   unit_pos strictly increasing stream coordinate
                                    |   modality 0 text / 1 aud / 2 vid
                                    |   role     0 prompt segment / 1 output segment
                                    v
         windows: x = ids[a:a+ctx], y = ids[a+1:b]      (unchanged; ONE Windows clock)
                                    |
     A stage (per window)           |   SIG 'typed' sample ending before the window
       DOM.observe(tokens = text ids only, filtered by root)
       TOK.on_window skips pairs with an id outside id2bytes
                                    v
     B stage (per flush)
       obs_emb = LM.embed(x)          --- ids >= 2^24 route to emb_media[k] (no signature move)
       WORLD.loss_terms(obs_emb, valid=same-modality (t,t+h) pairs)
       WORLD.media_terms(latents, valid, context=h@BEGIN)   <- continuous, frozen target
       extra = WORLD.forecast(...) + WORLD.media_forecast(...)   (both None at FEEDBACK=0)
       h = LM.encode(x, extra=extra)
       FAB.forward(h, head = lambda h: LM.decode(h, live_vocab, retired, modality=mod[y]),
                   live_domains = the window's class)
       logits = [text head | aud head | vid head] masked per position:
            text position -> live text rows + BEGIN_k   ;  media position -> codes_k + END_k
       loss = LM.lm_loss(logits, y, weights = role x modality_weight)
            + WORLD terms + WORLD_MEDIA_W * media_terms
            + AUD.loss_terms(raw clips)          (codec phase only, OPT group 'codec')
       MEM.write/read on TEXT positions only (first cut; MEM-over-media is an arm)
                                    v
     EVAL: generate (sampler, mode_fn = grammar), grounding (DATA.recover on generations)
           R matrix per area at every phase boundary
```

### 3.1 The id layout (spine/derive.py, known-answer tables in tests/test_derive.py)

- `MEDIA_ID_BASE = 1 << 24`.
- `media_id(k, c) = MEDIA_ID_BASE + k * (1 << 20) + c`.
- `media_code(id) -> (k, c)`.
- `is_media(id)`.
- Module indices k are fixed forever: AUD=0, VID=1, IMG=2 reserved.
- Inside block k: codes `[0, codebook)`, then `BEGIN = codebook` and `END = codebook + 1`. Rows per modality = `prod(levels) + 2`, which is 1002 for FSQ 8,5,5,5.
- A code of 2^20 or more is refused, with a known-answer test.

Why this layout:
- Media ids never sit inside `[0, LM_VOCAB_SLOTS)`, so `lm.vocab_slots` stays MAY_WIDEN (the prefix rule still holds).
- BPE minting, CAP's vocab arm and TOK's at_cap never see them, because media ids are not in id2bytes.
- Widening text, or adding VID, moves no stored id.
- The id-to-row mapping is ephemeral: `derive.token_row`, one `torch.where` per forward. Everything persisted stores ABSOLUTE ids: DOM histograms, eval samples, checkpoints, and later MEM entries.
- Measured in the real tree: putting codes inside the joint table (4096 -> 5120 slots) cost 11-13% windows/s on EVERY text window. Separate tables cost nothing on text-only windows.

### 3.2 One clock (M1)

There is **one Windows kind**. A window is LM_CTX ids of the unified stream in any modality, and every cadence stays in Windows. `spine/units.py` gains unit LABELS only (`HZ`, `FRAMES`), not clock kinds.

Named conversions go in `spine/derive.py`:
- `frames_per_second(sr, hop, stride)`
- `media_seconds_per_window(ctx, fps)`
- `windows_per_media_second(ctx, fps)`

Per-modality content differences are carried by readings (bits/code, bits/s), never by clocks.

### 3.3 Loss units (M3)

- Every term reports in its own unit: bits/byte for text, bits/code and bits/s for audio.
- No reading averages across units.
- `lm_loss` per-window numbers feed FAB competence and DOM.note_competence. When media is on, those consumers receive per-modality values normalised by that modality's running baseline, so comparisons stay within one modality.
- OPT's best_bpb and CKPT Retention read text bits/byte only.

---

## 4. New packages

### 4.1 AUD (prefix AUD; `src/aud/{__init__,api,levers}.py`)

Registered in `spine/assemble.py` PACKAGES, `compose.APIS`, `compose.RNG_SUBSYSTEMS` (aud, aud.train), `loop._PKG_DIR`, `tests/test_contract.py` PKG_DIR, the census and §7.

| Lever | Default | Unit / note |
|---|---|---|
| AUD_ENABLED | False | Null codec (D4 pattern): every entry point answers inertly |
| AUD_ARCH | 'spec' | 'spec' (STFT log-mag conv codec + Griffin-Lim) \| 'wave' (SEANet, GPU arm) |
| AUD_HOP | 160 | samples (STFT hop) |
| AUD_STRIDE | 2 | latent stride; frame rate = sr/(hop*stride) = **25 Hz** |
| AUD_LEVELS | '8,5,5,5' | FSQ, 1000 codes |
| AUD_D | 64 | pre-quantisation latent width (also WORLD's media observation) |
| AUD_HID | 256 | conv width |
| AUD_ENT_W | 1.0 | per-dimension marginal-entropy bonus (collapse guard) |
| AUD_BATCH | 16 | clips per codec step |
| AUD_CROP_S | 0.5 | seconds per training crop |
| AUD_FREEZE_AT | 3000 (U.Windows, read through `AUD.freeze_at`) | end of the codec phase; 0 = load only (§0 R3) |
| AUD_COLLAPSE_MIN | 64 | codes used per batch below this fires aud.collapse |
| AUD_QUIET_MIN | 0.25 | recon RMS / input RMS below this fires aud.quiet |
| AUD_GL_ITERS | 32 | Griffin-Lim iterations (decode and eval only) |
| AUD_LM_W | 1.0 | weight of code-position CE, per code unit (Emu3.5 used 0.5 for vision) |
| AUD_VERSION | 1 | EXACT geometry; a retrained codec is a new version |

Entry points (10):

| Entry point | Returns / behaviour |
|---|---|
| `build(aud, *, device, rng)` | Codec; a null Codec when disabled |
| `startup_refusals(aud, *, phase_plan, freeze_at)` | Refuses a media LM phase that starts before the freeze |
| `loss_terms(aud, codec, wave)` | CodecStep(loss, codes_used, entropy_bits, rms_ratio) |
| `encode(aud, codec, wave)` | CodecOut(codes, latents) |
| `decode(aud, codec, codes)` | wave |
| `freeze(aud, codec, *, clock)` | A Gate: runs the collapse and quiet checks, then freezes and hashes the weights into the version; refused and extended once if a check fails |
| `state_dict`, `load_into`, `geometry`, `counters` | Save path, restore path, geometry fields, did-it-fire counters |

Counters:
- `aud.built`: live or null.
- `aud.loss_terms.calls`.
- Gauges `aud.codes_used`, `aud.entropy_bits` and `aud.rms_ratio`, seeded at build and read at every R row.
- `aud.collapse` and `aud.quiet`: PRESENT-AND-0 while armed.
- `aud.freeze`, a Gate.
- `aud.encode.calls` and `aud.decode.calls`.

Collapse is silent in the loss curve: 7 of 15 research-codec runs collapsed, and the Route 3 SEANet decoder went near-silent. That is why both gauges exist.

`Codec.parameters()` is listed in `compose._base_parameters`' sibling list for the new OPT group `'codec'`. `_base_parameters` should REFUSE, not warn, when an enabled package that has trainable state has no parameters() (map risk 12; the WORLD frozen-weights defect).

### 4.2 VID (prefix VID; stage S7)

- Same shape and the same 10 entry points.
- Causal 3-D conv tokenizer (MAGVIT-v2 / Cosmos style): the first frame is encoded alone, 4x temporal, FSQ plus entropy bonus.

| Lever | Default |
|---|---|
| VID_ENABLED | False |
| VID_SIZE | 32 |
| VID_FPS | 8 |
| VID_PATCH | 8 (spatial) |
| VID_TSTRIDE | 4 |
| VID_LEVELS | '8,5,5,5' |
| VID_D | 64 |
| VID_HID | 128 |
| VID_ENT_W | 1.0 |
| VID_FREEZE_AT | 3000 (U.Windows, read through `VID.freeze_at`) |
| VID_COLLAPSE_MIN | 64 |
| VID_LM_W | 0.5 (Emu3.5 prior) |
| VID_VERSION | 1 |

At 32x32, 8 fps, 8x spatial and 4x temporal:
- 16 tokens per latent frame, 2 latent frames/s, so **32 tokens/s**;
- 4 s of video per 128-id window, 0.25 windows per video-second.

64x64 with 8x spatial (128 tokens/s) comes only after the throughput profile.

---

## 5. Changed packages and entry points

Unconditional frozen-signature moves. Each needs a `### Q-<PKG>-n` ruling plus the §7 edit plus the tree edit in the same commit. The None/()-defaults keep text-only calls bit-identical.

| # | Move | Why | Evidence |
|---|---|---|---|
| 1 | `LM.decode(..., modality=None)` | Per-position modality mask over [text \| media_k] rows | Route 1: early-CLOSE grammar violations 116 masked vs 185 shared; Route 3: 5.9% of sampled audio positions were non-code ids without the mask; mask saves 0.06 bits/byte in text phases |
| 2 | `LM.lm_loss(lm, logits, y, *, weights=None)` | Output-segment-only loss (role) x modality weight | Understanding 14% -> 28% exact at 50 Hz (Route 1) |
| 3 | `WORLD.loss_terms(world, w, obs_emb, *, valid=None)` | Drop (t, t+h) pairs that cross a modality boundary | Today horizon-1 pairs straddle caption/code boundaries in every paired window |
| 4 | `DATA.data_plan(..., media_units=None)` | Per-modality units per window, from derive.frames_per_second (a root argument) | splice_window gate and plan arithmetic |
| 5 | `EVAL.generate(ev, *, logits_fn, prompts_by_domain, rng, mode_fn=None, decode_fn=None)`, un-deferred | One sampler for text and media | Proposal 01: build the text sampler first |
| 6 | OPT.build accepts param_groups key `'codec'` (a Q-OPT-7 extension), plus lever `OPT_CODEC_LR` 1e-3 | Codec parameters in their own group, stepped only before the freeze | |

Conditional moves, made only when a measurement asks for them:

| # | Move | Trigger |
|---|---|---|
| 7 | `DOM.observe(..., modality=0)`, a hard class gate | Only if the M2 measurement (S5) shows flat domains are modality-impure (purity < 0.95). Otherwise the root's filtering is enough |
| 8 | `MEM.open_store(..., media_spans=())` plus `MEM_MEDIA` lever | The MEM-over-media arm (S8). The first cut keeps MEM text-only, with the per-source floor counting text sources only, so media never dilutes text's protected memory |
| 9 | `LM.encode(..., media=None)` | The continuous-insert understanding arm (S8, Route 2 graft) |

New entry points: 137 -> **153** at the audio stages, and **163** with VID. K13's prose restatements move with the count.

| Stage | Entry point |
|---|---|
| S3 | AUD x10 |
| S4 | `TOK.interleave(tok, seg, media, *, id_fn)` -> Segmentation with modality, unit_pos, role |
| S1 | `DATA.media_batch(dat, areas, *, n, crop_s, rng)` -> raw clips for the codec phase |
| S1 | `DATA.recover(dat, area, wave)` -> params or None (analytic inverse; None for real areas) |
| S5 | `EVAL.grounding(ev, *, pairs_by_area, caption_fn, generate_fn, recover_fn, rng)` |
| S6 | `WORLD.media_terms(world, w, *, latents, valid, context=None)` -> WorldStep |
| S6 | `WORLD.media_forecast(world, w, *, latents, valid)` -> (B, L, d_model) or None; born zero |

Each carries the docstring triple LEVERS READ / WIRES READ / DID IT FIRE. Each is named by an ASSEMBLY_ORDER or LOOP_ORDER row (produces column spelled as the consumer names it), or is listed in DEFERRED_ENTRY_POINTS with every missing producer named.

Changes with no signature move:
- **TOK**:
  - its build corpus is text areas only, so bytes_per_token is measured on text only (closes map risk 1: a measured 9% signature-width shrink);
  - `on_window` skips any pair containing an id outside id2bytes (counter `tok.on_window.media_pairs_skipped`);
  - vocab_state is unchanged.
- **LM**:
  - tables `emb_media[k]` and `head_media[k]`;
  - `embed` routes ids >= 2^24 through `derive.token_row`;
  - the dead-row mask applies to TEXT rows only (today's `dead[int(live_vocab):] = True` would put -inf on every appended media row; a test is required);
  - levers `LM_MEDIA_MASK` True (False is the measured joint-softmax arm), `LM_QK_NORM` False and `LM_Z_LOSS` 0.0 (transformer arm);
  - counters `lm.media.rows` and `lm.decode.modality_masked`.
- **SIG**:
  - new `SIG_SPACE='typed'`: the unit is a byte for text and a code for media, and there is a declared PAD unit that is never code 0 (map risk 5);
  - text windows sign exactly as under 'bytes', and the alphabet is 256 + media rows;
  - required when media is on (a startup refusal otherwise);
  - geometry `sig.space`: bytes -> typed is admitted as an alphabet widening (ruling R-SIG below).
- **FAB**:
  - the root rebinds the head closure per flush with the modality array and maps targets to columns;
  - it passes `live_domains` of the window's class, so the breadth cap and cull act within a modality;
  - arm lever `FAB_MOD_GROUPS` False (MoMa-style hard expert blocks, against learned routing).
- **DOM**: the root filters `tokens` to text ids, so tokc stays text-only; spawn and merge thresholds are re-measured on the typed space in S5.
- **CAP**: none. Media rows are not BPE rows.
- **RUN**:
  - `windows_in_epoch` counts the unified stream;
  - `bench_summary` reports positions/s and media-seconds/s alongside bytes/s.
- **CKPT**: payload keys `aud`, `vid` and `world_media`; manifest fields in §11.

Wires: 19 -> **21 of 25**. Each needs a written `why`, and `docs/03_WIRING.md` is re-rendered.
- `LM.d_aud_rows <- AUD.levels`: `prod(levels) + 2` if enabled, else 0. Irreducible, because the rows must hold the codebook.
- `WORLD.d_media_lat <- AUD.d`: declared, not measured.
- VID would add two more (23/25) unless the owner rules that multi-source wires into one consumer field count once (open question).
- Measured values (codes used, entropy, actual media share, bits per code) are derive-and-keep joins or readings, never wires.

New compose rows and joins:
- ASSEMBLY rows: `AUD.build`, then restore `AUD.load_into` BEFORE `OPT.build` (the WORLD.load_into precedent).
- LOOP rows:
  - `AUD.encode` at the epoch roll;
  - `TOK.interleave` after `TOK.tokenize`;
  - flush-stage `AUD.loss_terms` in the codec phase;
  - an A-stage `AUD.freeze` on Cadences key `aud.freeze`;
  - `WORLD.media_terms` and `WORLD.media_forecast`;
  - C-stage `AUD.state_dict`;
  - R-stage `AUD.counters`;
  - `EVAL.grounding` on the curve period.
- Joins that change: `_signature_width`, `_alphabet_size`, `_signature_stream`, `_signature_cursor`, `_sample_window`, `_base_parameters`, `_geometry_manifest`, `_head`, `_periods`, `_bytes_per_window`, `_windows_in_epoch`, plus a new `_media_join`.
- In loop.py: `_CALLS` per stage; the batch cut carries modality and role; the loss sum and non-finite blame list gain the media terms; `_payload` gains the new keys.

---

## 6. Codecs

### 6.1 AUD default: 'spec' at 25 Hz

- Features: STFT log-magnitude, n_fft 512, hop 160 at 8 kHz (50 frames/s).
- Encoder: Conv1d(257->256) ELU, Conv1d(256->256) ELU, stride-2 Conv1d, then a 1x1 to 64-d. The result is a 25 Hz, 64-d latent, which is also WORLD's media observation.
- Quantiser: GroupNorm, then FSQ 8,5,5,5 plus the entropy bonus. The decoder mirrors the encoder with a transposed stride-2 layer and predicts log-magnitude.
- Waveform: Griffin-Lim 32, a fixed algorithm with no weights.
- Loss: L1 on log-magnitude + 2 x L1 on magnitude + entropy bonus.

Measured on CPU with 1 thread, 250-260 s of training each:

| Codec | Params | Steps | mel held-out (silence 1.706, GL-oracle 0.185) | Codes used | Bits/code | Probe exact on reconstructions |
|---|---|---|---|---|---|---|
| spec 50 Hz (Route 3) | 724k | 5,614 | 0.463 | 630 | 7.46 | 40.3% |
| **spec 25 Hz (judge)** | 1.2M | 4,161 | 0.525 | 559 | 7.60 | **44.4%** |
| SEANet wave 25 Hz (Route 1, its data) | 0.65M | 1,687 | 1.03 (silence 1.81) | 109 | 5.65 | 57.8% (different probe/task) |
| SEANet wave 50 Hz (Route 3, its data) | 0.65M | 2,153 | 1.169, RMS 0.002-0.02 (near silent) | — | — | 2.8% (chance) |

Per-attribute probe accuracy on reconstructions:
- spec 50 Hz: band 0.98, kind 0.77, timbre 0.60, count 0.72.
- spec 25 Hz: band 0.89, kind 0.76, timbre 0.60, count 0.75.

Encode and decode real-time factors:
- spec 50 Hz: encode 0.0008, decode 0.031.
- spec 25 Hz: encode 0.0008, decode 0.031.
- SEANet wave 25 Hz: 0.03 encode+decode.

Reading of the table:
- The spectral codec at 25 Hz keeps its codebook and generation ceiling at half the token rate.
- Timbre (harmonic structure) is the weak attribute of every codec.
- The SEANet waveform codec does not reach phase at CPU budget. It either learns only the envelope (SNR about 0 dB) or goes quiet. It stays as the GPU `'wave'` arm, with GAN and feature-matching losses and quantizer dropout at DAC/EnCodec step counts (100k-400k).

### 6.2 Training and freezing

- For windows < AUD_FREEZE_AT, AUD.loss_terms runs once per flush on DATA.media_batch clips (rng child aud.train) under OPT group 'codec'.
- Meanwhile the LM trains on text only: audio areas are phase-gated out of the stream, and a startup refusal fires if a media LM phase is scheduled earlier.
- At the freeze Gate:
  1. collapse check (`codes_used >= AUD_COLLAPSE_MIN`) and quiet check (`rms_ratio >= AUD_QUIET_MIN`); if either fails, the freeze is refused and extended once, and reported;
  2. the weights are hashed into `aud.version`;
  3. AUD.encode fills every media segment's placeholder positions with code ids IN PLACE; no window boundary moves and no Segmentation is rebuilt (§0 R1).
- The LM loss NEVER back-propagates into the codec. Codes are integers. REPA-E latent collapse, STE codebook collapse and AQM's "old codes must stay decodable" all argue against it.
- Codec drift: a retrain (for example on real audio) is a NEW version. It either keeps the old block for old areas (the payload holds both codecs), or goes to a new block k with rows initialised from the nearest old-code rows (the LM_NEW_ROW_INIT analogue). A codec never changes silently under a trained LM.

### 6.3 Rejected codec options

| Option | Reason for rejection |
|---|---|
| Flattened RVQ 4x256 | 200 tokens/s, 0.64 s per window; levels 2-4 gave no reconstruction gain in the research runs. If RVQ is ever used, use MusicGen's delay pattern |
| Plain FSQ | Collapsed in 3 of 5 runs |
| Joint codec+LM backprop | Collapse evidence above; token meaning drifts under the LM |

---

## 7. Synthetic generators (DATA)

Generators are DATA's, because the corpus is DATA's and real data later goes into the same Areas slots. They are private functions in `data/api.py`, since packages hold only api.py and levers.py; a helper module needs a ruling.

Every clip carries its parameter tuple. Its caption is rendered from the discrete parameters by template, and the continuous parameters (exact frequency, f0, gain, jitter, noise) add variety.

### Audio families

Build order:
1. **aud/tones**, "beeps-and-tones" (Route 3), 36 combinations, 1 s clips:
   - kind: tone, rise, fall or beeps;
   - band: low, mid or high;
   - timbre: pure or buzzy;
   - count: 2-4 for beeps.
   Captions look like "three low pure beeps". The analytic probe scores 360/360 on ground truth.
2. **aud/vowels**: Klatt-style formant synthesis, vowels a/i/u plus consonant bursts.
3. **aud/melody** (Route 2): 4 notes of 0.64 s, 8 pitches, 3 timbres, and an **order-2 Markov grammar per area** (successor probabilities 0.7/0.3). It separates a memoryless WORLD from a context WORLD, and continuation legality against the known table is an exact metric. Different grammar seeds give controllable distribution shifts for goal B.
4. **aud/chirps**: AM/FM and linear/exponential chirps.

### Video families (S7)

- **vid/sprites**: dSprites-factor shapes (shape, colour, size, velocity).
- **vid/bounce**: bouncing and colliding 2-D balls with 2-D physics.
- **vid/glyphs**: procedurally drawn digits (not MNIST).
- **av/bounce**: paired audio-video, where a collision emits a click and shape maps to pitch. This gives WORLD a cross-modal forecasting target and gives grounding checks in both directions.

### Tasks and layout

- `t2a`: caption, then [BEGIN codes END]; loss on the codes only.
- `a2t`: [BEGIN codes END], then caption; loss on the caption only.
- `a`: a plain clip with loss on all codes.
- `cont`: half a clip as the prompt, the rest as the output.
- VideoPoet-style task prefixes are marker ids in the media block's reserved range.

### DATA levers

| Lever | Default | Meaning |
|---|---|---|
| DATA_MEDIA_AREAS | "" | Off; the tree stays bit-identical |
| ~~DATA_MEDIA_SECONDS~~ | — | Removed (§0 R4): the media amount is set by DATA_TEXT_SHARE alone; media seconds and windows per phase are a startup READING |
| DATA_MEDIA_CLIP_S | 1.0 | |
| DATA_MEDIA_TASKS | 't2a,a2t,a' | |
| DATA_PAIR_CAPTION_FIRST | 0.5 | |
| DATA_MEDIA_HOLDOUT | 0.1 | |
| DATA_MEDIA_HOLD_COMBOS | 'auto' | 4 per area, drawn from data.holdout.<key> |
| DATA_MEDIA_FRESH | True | **Every clip distinct** (§0 R2): clip i of an area renders from its own seed, so freshness needs no epoch roll. False = a fixed pool of DATA_MEDIA_POOL clips reused, the measured-overfit arm (held-out bits/code 3.44 -> 4.51 against 2.45 fresh) |
| DATA_MEDIA_POOL | 2400 | Pool size when DATA_MEDIA_FRESH=False |
| DATA_AUD_SR | 8000 | Hz. THE ONE sample-rate lever (§0 R8); AUD receives it as an argument |
| DATA_TEXT_SHARE | 0.3 | Text rehearsal share inside media phases. Measured sufficient at 25% (Route 3) and 30% (Route 1); matches DeepSeek-VL |

### Held-out sets

This fixes "synthetic holds nothing out", data/api.py:455-457. There are two:
- a seed-disjoint block per area from `data.holdout.<key>`;
- a COMBINATION holdout: attribute combinations never drawn in training, for the composition test.

### Scheduled switches

Modality arrival is a DATA_PHASE_SCHED entry. Example: `eng,py,num,c | eng,py,num,c | eng,py,num,c,aud/tones | ...,aud/vowels | ...,vid/bounce`. The codec phase runs during the text phases.

### Cost

- Generating a clip costs 0.4-1.3 ms.
- Encoding runs 1,250x faster than real time on one thread (spec codec).
- Regenerating 10 minutes of audio per epoch costs well under a second.

---

## 8. Generation and its evaluation

**Sampler.** EVAL.generate becomes the sampler for text first (stage S2) and then media, through the same function. It uses the whole-path `logits_fn` (FAB, MEM blend, decode) and RECOMPUTES the window per sampled token (O(ctx), fine at ctx 128); an incremental-state entry point is an S8 arm with its own Q-LM ruling (§0 R10).

**Media generation:**
- Prompt: `[t2a] caption [BEGIN]`.
- Sample exactly F = clip_s x fps codes under the audio mask. The `mode_fn` grammar keeps END masked until F codes, then forces END.
- Temperature: EVAL_MEDIA_TEMP, default 0.7; the measured best was 0.3-0.7.
- AUD.decode turns the codes into a waveform.

**Understanding:** a greedy caption after `[a2t] [BEGIN] codes [END]`, masked to text rows, stopping at "." or at BEGIN.

**Continuation** and cross-modal chains (text -> audio -> text) use the same sampler.

**EVAL.grounding, per area**, under frozen_rng on fixed held-out prompts, every curve period:

| Reading | Unit |
|---|---|
| Ground-truth sanity: DATA.recover on true clips | must read 1.0 or the reading is refused |
| Codec ceiling: recover on reconstructions | exact and per attribute |
| Generation: recover on generated clips | exact and per attribute, **train combos and held-out combos separately** |
| Understanding: caption exact match and per attribute | same split |
| Continuation legality (aud/melody) | against the known Markov table |
| Bits per code; bits per second (= fps x bits/code) | exact likelihood |
| Caption bits given the right clip minus given a wrong clip | grounding bits per clip (hidden-forgetting guard) |
| Codes used and entropy of generated codes | mode-collapse check |
| Codec mel and rms_ratio | codec health |

The learned probe is secondary only. It is fragile: 2.3% on reconstructions before augmentation. Analytic recovery is primary and cannot drift.

**Measured baselines**, CPU, one seed, the regression bands to reproduce in-tree:

| Configuration | Understanding exact | Generation | Ceiling |
|---|---|---|---|
| Route 1, tree GRU, 16 classes, 25 Hz SEANet, 8k windows | 41% | 20-36% probe | 58% |
| Route 1, same, 20k windows | 34% | 22-41% | 58% |
| Route 3, W128, 24k fresh clips, 36 combos, 50 Hz spec | 53.9% | 16.7% exact (T=0.7) | 40% |
| Route 3, held-out combinations | 0% | 0-8% | |

---

## 9. Continual-learning measurement (goal B)

**Modality = area (M10).** Adding one is the existing add-an-area protocol (Q-DATA-7). The default is **rehearsed**, with DATA_TEXT_SHARE 0.3. Pure-add is the named lower-bound arm.

Measured:

| Arm | Text before -> after | WORLD text MSE | Source |
|---|---|---|---|
| Pure-add, tree GRU+WORLD | 2.966 -> 3.196 bits/token (+7.8%) | 1.02 -> 3.21 | Route 1 |
| 30% replay, tree GRU+WORLD | 2.966 -> 2.906 (still improving); audio 3.03 vs 2.96 bits/code | 1.10 | Route 1 |
| Pure-add, masked | 1.936 -> 7.846 bits/byte | | Route 3 |
| Pure-add, joint softmax | 1.997 -> 8.549 (the mask is itself protection: 0.64 bits/byte less) | | Route 3 |
| 25% replay | 1.936 -> 1.931 bits/byte | | Route 3 |

The machinery doing work:
- **DOM**: tokc stays text-only. Under SIG 'typed', DOM spawns media domains from typed signatures. The **M2 measurement** (S5) reports the modality purity of flat domains on the mixed stream. If purity < 0.95, the hard class gate (`DOM.observe(modality=)`, Proposal 02's modality top) lands. Spawn and merge thresholds are re-measured per class.
- **FAB**: the breadth cap, grow and cull are computed within the window's class. `FAB_MOD_GROUPS` (hard modality expert blocks, MoMa) runs against learned routing (Shukor 2025).
- **MEM**: text-only first. The floor counts text sources, so media never shrinks text's protected memory. MEM over media (retrieval over codec ids as a next-token distribution) is an S8 arm.
- **WORLD**: per-area forward MSE goes in the R matrix. WORLD forgetting is 3x the LM's on pure-add, so it must be reported per area or it hides.
- **Isolation arms**: an lr-shield of text rows and experts (OPT_LR_SHIFT_WARM re-warm at the boundary); zero-born tanh gates on new pathways; upcycling new-modality experts from text experts; generative self-replay of old audio from its captions.

**R matrix.** R[phase_end][area] is filled at every phase boundary on both holdouts. Each cell holds:
- text: bits/byte;
- audio: bits/code, bits/s, understanding and generation grounding (train and held-out combos), continuation legality, codec mel;
- WORLD: forward MSE (and media_terms relative MSE).

ACC, BWT and FWT use the existing forgetting_of and bwt_of per metric. Units are never mixed. There is a joint i.i.d. upper-bound arm and a fine-tune-only lower-bound arm.

---

## 10. WORLD's role

1. **Existing path over mixed windows.** `WORLD.loss_terms(obs_emb = LM.embed(x), valid=...)`. Codec ids are rows in LM's embedding, which honours world/api.py's claim that "a second sense needs new rows in LM's embedding and nothing new here". Measured with the tree's WORLD: forward MSE about 1.0 on text latents (no better than unit variance) and 0.54-0.72 on audio-code latents.
2. **Temporal media head (new): `WORLD.media_terms`.** A causal GRU (WORLD_MEDIA_HID 128) over the frozen codec's 64-d latents at 25 Hz. It predicts horizons `WORLD_MEDIA_HORIZONS='1,5'` frames (40 ms and 200 ms). `WORLD_MEDIA_COND` True conditions h0 on the LM hidden state at BEGIN. `WORLD_MEDIA_W` is 0.1. `WORLD_MEDIA_CTX` 'none' is today's memoryless form, kept as the control.
   - There is no VICReg on this path: the target is frozen and cannot collapse, so the historic WORLD_W folding defect cannot recur here.
   - Forecasts are decodable: 1-step forecasts decode to mel 0.47-0.50 against the codec's 0.46.

   Measured relative MSE against persistence (Route 3, 50 Hz latents):

   | Predictor | h1 | h5 |
   |---|---|---|
   | Memoryless residual-linear (today) | 0.321 | 0.678 |
   | Temporal GRU | 0.134 | 0.386 |
   | Caption-conditioned GRU | 0.138 | 0.314 |

3. **Feedback (wired, off).** `WORLD.media_forecast` is a born-zero world_proj_media added to LM.encode's extra at media positions, inert under WORLD_FEEDBACK=False (Q-WORLD-10). The GPU test (§14) uses captions that describe the clip's FUTURE (notes 3-4 given notes 1-2), which only a forecast can answer.
4. **Reporting rule (from Route 2).** One-step inv against persistence is never read as generation quality. Rollout readings carry their horizon and rollout length. Any WORLD-rollout generation arm must train with the **free-running loss**: teacher forcing alone left notes 2-4 at chance in every arm.
5. **Video.** WORLD_LAT 32 is probably too small for video. lat is EXACT, so raising it is a new-run decision at S7.

---

## 11. Checkpoint and geometry

**Rulings needed:**
- **R-CKPT (absent-field rule).** A manifest field may declare `absent=<off value>`. A checkpoint that lacks it reads as that value, so an old text checkpoint reads as `aud.enabled=False`, `lm.media_rows.aud=0`, `world.media_ctx='none'`.
  - A resume that turns AUD on over such a checkpoint is an **add-a-modality resume**. The LM media rows, WORLD media parameters, codec tensors and the OPT 'codec' group are BORN (via add_param_group, the WORLD.manage precedent). The LoadReport lists every born tensor and counter `ckpt.geometry.born.<field>`.
  - Every other absent field is still refused.
- **R-SIG.** `sig.space` bytes -> typed is admitted as an alphabet widening, because text units are identical. Any other change of sig.space stays refused.
- **R-OPT.** OPT.load_state with a group absent from the checkpoint creates that group fresh with fresh moments. Every other group change stays refused.

Fields:

| Field | Rule | Absent means |
|---|---|---|
| aud.enabled, aud.arch, aud.sr, aud.hop, aud.stride, aud.levels, aud.d, aud.version | EXACT | off / — |
| lm.media_rows.aud (and .vid) | EXACT once > 0 | 0 |
| world.media_ctx, world.media_lat | EXACT | 'none' / 0 |
| lm.vocab_slots | MAY_WIDEN (unchanged; now safe, because media ids are not on the prefix) | — |
| sig.space | EXACT except bytes -> typed | — |

- Changing levels, hop, stride, sr, arch or version against a checkpoint that has them is refused: it is a new token space.
- Payload keys: `aud`, `vid` and `world_media`. The codec's frozen weights are saved, so old codes stay decodable (AQM).

---

## 12. Cost

**Per window:** unchanged. Windows stay 128 ids, and the measured step cost is the same for text and audio windows (34-39 ms LM+WORLD per window in Route 1's prototype).

**Windows per media-second:**

| Media | Windows per media-second | Seconds per window |
|---|---|---|
| Audio, 25 Hz | 0.2 | 5.12 s |
| Audio, 50 Hz | 0.39 | |
| Video, 32 tokens/s | 0.25 | |

- A captioned 1 s clip at 25 Hz is 36.6 ids against 9.6 for its caption, a 3.8x multiplier.
- 1 h of audio = 703 windows at 25 Hz. That is 18 s at 38 windows/s early, and 4-6 min per run at 2-3 windows/s late.

**Codec phase:**
- spec codec step (batch 16 x 0.5 s): about 45-60 ms on one CPU thread; small on GPU.
- Only for AUD_FREEZE_AT windows.

**WORLD media head:** 91-140k params, a GRU over F frames per segment.

**Parameters:** media rows 1002 x 128 x 2 = 0.26M per modality at width 128.

**Text-only windows:**
- The text-only head is unchanged because media tables are separate.
- Mixed windows pay a head over vocab_slots + 1002 columns.
- Media windows skip TOK.on_window and MEM.

---

## 13. Staged build plan

Each stage ends runnable (run.py or a named probe) with the full suite green, and `run.py --max-windows 80` is bit-identical with media off.

| Stage | Build | Tests / acceptance |
|---|---|---|
| **S0 Rulings** | Written Q-entries: M1 (one Windows kind), the id layout, M3 (units never mixed), M4 (one package per modality), M5 (per-modality tables + transport ids), M8 (WORLD owns continuous media prediction), M10 (modality = area), R-CKPT, R-SIG, R-OPT, wire accounting for VID | — |
| **S1 Spine + synthetic audio (FIRST)** | baseline fixture first; derive ids and frame conversions; units labels; Areas.media; DATA aud/tones generator, placeholder media track in final coordinates, holdout, recover, media_batch | Appendix A |
| **S2 Text sampler** | EVAL.generate un-deferred with the whole-path logits_fn, window recompute per token (§0 R10), prompts_by_domain from DATA held-out | Reproducible under frozen_rng; bits/byte unchanged; K6/K12 un-deferral |
| **S3 AUD + codec phase** | AUD package ('spec' default, 'wave' arm), FSQ + entropy bonus, null arm, collapse/quiet/freeze Gates, OPT 'codec' group, OPT_CODEC_LR, _base_parameters refusal | FSQ round trip; null inert; collapse fires on a constant-encoder fixture and is PRESENT-0 when healthy; quiet fires on a zero decoder; bit-exact resume mid-phase; levels change refused; text checkpoint resumes with AUD on and born tensors listed; **CPU acceptance: mel < 0.6, codes_used >= 300, probe ceiling >= 30% within 5 CPU-minutes on aud/tones** |
| **S4 Shared stream** | TOK.interleave; LM media tables via the wire; token_row; text-only dead mask; decode mask; lm_loss weights; SIG 'typed'; WORLD valid=; CKPT fields + absent rule; FAB class-scoped live_domains; DOM and MEM root filters | Media off bit-identical; a 200-window audio+text run completes; the mask never lets a text id into a clip or the reverse; unit_pos monotone; interleave known answer; build bpt unchanged with media on; causality for typed samples; resume bit-exact; K1/K6/K10/K12/K13, N2, A9/A10 |
| **S5 Grounding + goal B** | EVAL.grounding; R matrix per area; the M2 purity measurement; DOM class gate if M2 < 0.95 | **CPU regression band at 8k windows, 25 Hz**: understanding exact > 25% on train combos; generation exact > 10% (chance 1/36 on aud/tones); grounding bits per clip > 2; rehearsed phase text bits/byte within +1% of pre-phase |
| **S6 WORLD media head** | WORLD.media_terms (ctx gru/none), media_forecast (born zero), geometry fields | First call of media_forecast is an exact no-op; world.media_forecast.calls PRESENT-0 when feedback is off; horizon slices stay within segments; relative MSE at h5 < 0.6 on aud/melody |
| **S7 VID** | Synthetic sprites/bounce/glyphs, av/bounce, causal 3-D FSQ codec, VID rows | Same as S3/S4; 163 entry points |
| **S8 Arms** | See the list below | Each arm judged on grounding per FLOP |

S8 arms, in priority order:
1. **Continuous insert for understanding**: LM.encode(media=), K=8 WORLD-latent embeddings (Route 2: 0.978 notes vs 0.485).
2. Factorised FSQ head (8+5+5+5 logits).
3. GIVT/MAR continuous head over codec latents.
4. WORLD-rollout generator with free-running loss plus a stochastic head.
5. FAB_MOD_GROUPS.
6. lr-shield / zero-init gates.
7. Generative self-replay.
8. MEM over media.
9. Codec version handover.

---

## 14. Rejected routes

**Route 2: continuous latents through WORLD as the generator and the only media path.**
- Today's memoryless WORLD diverges on rollout (L1 6.8 held-out / 84 compositional) and leaves note 4 at chance (0.228).
- With a context GRU and a free-running loss it generates perfectly only on a task whose captions spell out every note, and it gets the first note wrong in every held-out combination (0.0).
- There is no working stochastic sampler: GMM heads 0.54-0.64 legal against 0.99.
- There is no exact media likelihood.
- 64 sequential rollout steps per media window are latency-bound on a shared GPU (+18% CPU window cost at gen_every=1).
- It needs a new clock kind (Frames) and the heaviest WORLD surgery.
- What survives: its understanding result (inserting WORLD latents through the trunk: 0.94 exact) is the first S8 arm; the free-running loss; the reporting rule; the melody family.

**Route 3 as proposed.**
- It is adopted almost entirely. Two things changed:
  - The default frame rate is 25 Hz, not 50: Route 1 found the LM learns 25 Hz codes better at every budget, and the judge measured that the spectral codec keeps its ceiling at 25 Hz.
  - DOM gets a conditional class gate.

**Codes inside BPE / inside [0, vocab_slots):**
- +0.06 bits/byte on text in text-only phases;
- 5.9% non-code samples;
- 0.64 bits/byte more forgetting;
- 11-13% windows/s on every text window;
- a top-anchored block moves when vocab_slots widens;
- BPE longest-match and minting eat serialised codes.

**Split clock kinds per modality:** multiplies every cadence lever for no type-safety gain.

**Joint codec + LM training:** REPA-E, STE collapse, AQM.

**Flattened RVQ:** 4x the sequence length.

**Unmasked shared softmax as the default:** equal likelihood, 1.6x the grammar violations, and text ids inside clips.

**Learned probe as the only generation metric:** 2.3% on reconstructions before augmentation.

---

## 15. Literature

Evidence grades:
- [P] means the primary text was read.
- [S] means a search extract of the paper's own page.
- [C] means read in the official code repository.
The proxy blocked arxiv, so most entries are [S].

**Early-fusion unified token models**
- Chameleon (2024, arXiv 2405.09818) [S]: early fusion over discrete image tokens. Modality competition shows up as norm growth; fixed with QK-norm and z-loss. → LM_QK_NORM / LM_Z_LOSS.
- Unified-IO 2 (2312.17172) [S]: from-scratch any-to-any, including audio via a spectrogram VQ.
- Emu3 (2409.18869) [S], [C] README: next-token only; 4x8x8 video tokenizer. Emu3.5 (2510.26583) [S] weights vision tokens 0.5.
- VideoPoet (2312.14125) [S]: MAGVIT-v2 + SoundStream tokens; task prefixes; loss on the output segment.
- Gemini 1.0 [P]: continuous encoders in, discrete image tokens out.
- Shukor et al. 2025, scaling laws for native multimodal models (2504.07951) [S]: early fusion wins at low parameter counts; learned routing beat hard modality routing.
- Aghajanyan 2023 (2301.03728) [S]: modality competition and synergy.

**Understanding versus generation**
- Janus (2410.13848) [S]: split paths, semantic features in, VQ tokens out. → S8 continuous-insert arm.
- Flamingo [P]: zero-init tanh gates (−4.4% and instability without them); freezing beat replay.

**Continuous heads**
- Transfusion (2408.11039) [S].
- MAR / diffusion loss (2406.11838) [S].
- GIVT (2312.02116) [S].
- Fluid (2410.13863) [S].
- Diffusion Forcing (2407.01392) [S].

**Codecs and tokenizers**
- FSQ (Mentzer 2023, 2309.15505) [C].
- iFSQ (2601.17124) [S]: plain FSQ activation collapse, which matches the measured 3/5 collapses.
- LFQ / MAGVIT-v2 (2310.05737) [S]: entropy loss and causal 3-D conv.
- BSQ (2406.07548) [S].
- SoundStream (2107.03312) [S].
- EnCodec (2210.13438) [C].
- DAC (2306.06546) [C].
- Mimi / Moshi (2410.00037) [S], [C].
- WavTokenizer (2408.16532) [C]: a single codebook at 40-75 tokens/s.
- MusicGen delay pattern (2306.05284) [S].
- Cosmos tokenizer (2501.03575) [C].
- Vocos (2306.00814) [S].

**Codec training versus LM training**
- REPA-E (2504.10483) [S].
- AQM online continual compression (1911.08019) [S].

**Modality-sparse compute**
- MoMa (2407.21770) [S].
- Mixture-of-Transformers (2411.04996) [S].
- LIMoE (2206.02770) [S].
- BEiT-3 (2208.10442) [S].
- MoE-LLaVA upcycling (2401.15947) [S].

**Continual learning**
- LMFusion (2412.15188) [S].
- DeepSeek-VL, 30% text (2403.05525) [S].
- Ibrahim 2024, re-warm plus replay (2403.08763) [S].
- Deep Generative Replay (1705.08690) [S].
- PathWeave (2410.20178) [S].
- MERA (2503.07663) [S].
- Lopez-Paz GEM, ACC/BWT/FWT (1706.08840) [S].
- Hidden forgetting (2607.02020) [S].

**Synthetic data**
- dSprites; Moving MNIST (1502.04681); CLEVRER (1910.04744 / 1910.01442); CLEAR (1811.10561) [S].
- Klatt 1980 formant synthesis.

---

## 16. Open questions for the owner — each with the recommendation that gets built if unruled

| # | Question | Recommendation | Why |
|---|---|---|---|
| 1 | S0 rulings: M1 one Windows kind; the transport-id layout; R-CKPT absent-field rule; R-SIG bytes → typed widening; R-OPT fresh group and freeze shift stamp | Adopt all as written | Without R-CKPT and R-SIG, "add a modality to a text run" cannot be run as a resume, which is goal B's own test |
| 2 | 25 or 50 Hz | Build both behind one lever, default 25 | 25 Hz halves sequence length (throughput pays twice under sharing); its LM advantage was measured on a 109-code SEANet codec, not the 559-code spectral one, so it is re-measured at S5 and on GPU |
| 3 | Promote the continuous insert (LM.encode(media=)) from S8 to S5? | Yes, as an arm, default off | Discrete understanding reached 45-55% of a dedicated classifier; the continuous insert reached 0.94-0.98. Building it early costs one signature move; the default waits for grounding-per-FLOP |
| 4 | Composition near zero in every route | GPU width × data sweep on the combination split (Appendix B, S4/S5 d) | Unknown whether scale or variety; toy CPU runs cannot tell |
| 5 | Wire budget with VID: 21-23 of 25 | Stay inside 25; no multi-source ruling yet | R8 already saved one wire |
| 6 | Generator placement | Private functions in data/api.py | The rule is api.py + levers.py per package; a helper module needs its own ruling and buys nothing measurable |
| 7 | A from-scratch perceptual metric for real data later | Allowed for evaluation only, never as a training loss | Keeps "learned from scratch" and keeps pretrained weights out |
| 8 | MEM over media | Text-only first; MEM-over-media is an S8 arm | MEM's keys are text-shaped today; an arm measures it before it becomes a default |
| 9 | Text protection: rehearsal (DATA_TEXT_SHARE) vs lr-shield vs freeze | Rehearsal default 0.3; lr-shield built as an arm; freeze rejected | Freezing stops text improving, which is a downgrade; rehearsal was measured sufficient at 25-30% |
| 10 | Envelope-level audio (spectral codec + Griffin-Lim) acceptable for the first cut? | Yes; the 'wave' codec is built as an arm (S3 a) | Synthetic families are exactly recoverable at envelope level; perceptual quality matters with real data |
| 11 | Codec retraining on real data | Versioned codec handover (S8 i): new id block, nearest-row init | Frozen ids must never change meaning inside a run |
| 12 | R11 baselines owner | FAB | It is the heavier consumer; DOM gets it as an argument |

<details><summary>The judge's original list (kept as history)</summary>



1. The rulings in S0, especially R-CKPT (the absent-field rule) and R-SIG (bytes -> typed widening). Without them, goal B's "add a modality to a text run" cannot be run as a resume.
2. The 25 Hz LM advantage (Route 1) was measured with a SEANet codec using only 109 codes. With the spectral codec at 559 codes the LM's job is harder. 25 versus 50 Hz must be re-run in-tree at S5 and on GPU.
3. Discrete understanding sits at 45-55% of a dedicated code classifier, while Route 2's continuous insert reached 0.94 exact. Should the continuous insert path (an LM.encode signature move) be promoted from S8 to S5?
4. Composition is near zero in every route. Is it a scale or data-variety problem? It needs GPU width and data sweeps with the combination split.
5. Wire accounting for VID: 23/25, or a multi-source ruling.
6. Generator code placement: data/api.py private functions, or a ruled helper module.
7. Is a perceptual metric trained from scratch allowed for evaluation of real data later? Pretrained ones are excluded.
8. MEM over media: default after the S8 arm, or text-only permanently?
9. Rehearsal share: 0.3 by default. Is text protection by an lr-shield preferred over replay, given the "never downgrade" rule? Freezing stops text improving.

</details>

---

## Appendix A — Stage S1 as first drafted, and what §0 changes in it

**Read with §0; where they disagree, §0 wins.** The changes to this draft:
- **Step 0 (new, first):** capture the baseline fixture (R7).
- Generators: **aud/tones only** in S1 (R9); vowels and melody follow once their inverses measure 1.0 in scratch.
- Levers: drop `media_seconds` (R4) and `aud_sr` → `DATA_AUD_SR` is the only rate lever (R8); add `media_pool` (R2); the media amount is `DATA_TEXT_SHARE`.
- `Areas.media`, phase-name resolution over `bodies ∪ media`, and segments drawn inside draw_stream in final coordinates with placeholder layout (R1, R4). Captions are text and go into the text positions of their segment, not "inserted at at_byte afterwards".
- Clip seeds per clip and per RUN_SEED (R2); no per-epoch child.
- K12 reasons name arguments; every K13 population synced (R6). `data.media.*` counters on Stream (R14).

**STAGE S1** (with S0's spine pieces): SPINE CONVERSIONS AND SYNTHETIC AUDIO DATA, MEDIA OFF BIT-IDENTICAL.
Precondition: the S0 rulings are written into docs/04_CONTRACT.md §5 as Q-entries: M1 one Windows kind, the id layout, M4, M10, and M3 units never mixed. No AUD package, LM or TOK change yet.

FILES
1. src/spine/derive.py (new named functions):
   - MEDIA_ID_BASE = 1<<24; MEDIA_BLOCK = 1<<20; MODALITY_INDEX = {"aud": 0, "vid": 1, "img": 2}.
   - media_id(k, code) -> int. Refuses code >= MEDIA_BLOCK or k not in MODALITY_INDEX values.
   - media_code(i) -> (k, code). Refuses i < MEDIA_BASE.
   - is_media(i) -> bool.
   - media_rows(levels) -> prod(levels) + 2.
   - frames_per_second(sr, hop, stride) -> float. Refuses a non-integer frame rate.
   - media_seconds_per_window(ctx, fps) -> ctx / fps.
   - windows_per_media_second(ctx, fps) -> fps / ctx.
2. src/spine/units.py: unit LABELS HZ = 'Hz' and FRAMES = 'frames' (and CODES = 'codes'). NO new clock kind; CLOCK_KINDS is unchanged.
3. src/data/levers.py, new levers. Each declares a unit, a literal default and help text, and gets an "(amendment: NAME)" row in .rework/census.json.

| Lever | Default | Unit / note |
|---|---|---|
| media_areas | "" | |
| media_seconds | 600 | seconds per epoch |
| media_clip_s | 1.0 | |
| media_tasks | 't2a,a2t,a' | |
| pair_caption_first | 0.5 | |
| media_holdout | 0.1 | |
| media_hold_combos | 'auto' | |
| media_fresh | True | |
| aud_sr | 8000 | Hz |

   DATA_AUD_SR duplicates AUD_SR on purpose: DATA renders the waveforms, and the S3 startup refusal checks that the two agree. The alternative is making it a wire at S3.
4. src/data/api.py:
   (a) Private generators for aud/tones (kind tone/rise/fall/beeps x band low/mid/high x timbre pure/buzzy x count 2-4; 36 combinations), aud/vowels (formant a/i/u plus bursts), and aud/melody (order-2 Markov over 8 pitches x 3 timbres, grammar seeded per area). Each returns (wave float32 tensor, params tuple, caption bytes). Port these from results/multimodal_design_2026-09-25/prototypes/design-hybrid/synth.py and design-world/proto/synth.py.
   (b) MediaSegment(at_byte, modality, area, clip_ref, params, task, pair_id), and Stream.media: tuple, empty when media_areas == "".
   - Captions of paired tasks are inserted into Stream.bytes AT at_byte as ordinary text, and they carry the media area's label in Stream.labels. So with media on, the text stream changes only by those captions, and with media off it is byte-identical.
   - Clip payloads are never in Stream.bytes.
   (c) Per-epoch child streams data.synth.<label>.e<epoch> when media_fresh, otherwise data.synth.<label>. Holdout from data.holdout.<key>, with seed-disjoint draws. The combination holdout is drawn once from data.holdout.<key> and excluded from every training draw.
   (d) stream_state / restore_stream_state carry the media cursor and epoch.
   (e) NEW entry point DATA.recover(dat, area, wave) -> params | None. It is an analytic inverse: STFT energy runs (count and onsets), harmonic-sum pitch (band), log-pitch slope (kind), harmonic energy fraction (timbre), formant ratio (vowel), and per-note pitch (melody). It returns None for non-synthetic areas.
   (f) NEW entry point DATA.media_batch(dat, areas, *, n, crop_s, rng) -> (n, 1, crop_s*sr) float32. Random crops from media areas; its consumer is AUD at S3, so at S1 it is listed in DEFERRED_ENTRY_POINTS naming its missing consumer (AUD.loss_terms).
   Both entry points carry LEVERS READ / WIRES READ / DID IT FIRE. The counters are data.recover.calls, data.media_batch.calls, data.media.segments (PRESENT-0 when armed with media_areas empty is wrong; ABSENT with reason 'media_areas empty') and data.media.holdout_combos.
5. src/spine/compose.py:
   - RNG_SUBSYSTEMS: derived children data.synth.* and data.holdout.* for media areas.
   - An ASSEMBLY/LOOP note that Stream.media is produced by DATA.draw_stream.
   - DATA.recover in DEFERRED_ENTRY_POINTS until EVAL.grounding (S5) names its consumer.
6. docs/04_CONTRACT.md: §7 gains the two entry points; the count 137 -> 139 and every prose restatement (K13). Re-render docs/05_DEFAULTS.md (python3 tools/render_defaults.py).

TESTS
- tests/test_derive.py: known-answer tables.

| Call | Expected |
|---|---|
| media_id(0, 0) | 16777216 |
| media_id(0, 999) | 16778215 |
| media_id(1, 1001) | 17826793 |
| media_code(17826793) | (1, 1001) |
| media_id(0, 1<<20) | refuses |
| media_rows([8,5,5,5]) | 1002 |
| frames_per_second(8000, 160, 2) | 25.0 |
| frames_per_second(8000, 160, 1) | 50.0 |
| media_seconds_per_window(128, 25) | 5.12 |
| windows_per_media_second(128, 50) | 0.390625 |
| frames_per_second(8000, 150, 1) | refuses (53.33) |

- NEW tests/test_media_data.py:
  - DATA.recover exact accuracy is 1.0 on 360 ground-truth clips (10 per combination) for aud/tones, and 1.0 per attribute on 100 clips each of aud/vowels and aud/melody.
  - Determinism per child: the same seed gives byte-identical waves. Adding the area aud/vowels does not change aud/tones clips.
  - Holdout disjointness: no training draw across 5 epochs equals a holdout params-plus-seed; held-out combinations never appear in training draws (5 epochs x 600 s).
  - The caption equals render(params) for every segment.
  - Known answer: the spectral peak of a rendered 'mid pure tone' lies in 450-650 Hz.
  - The per-epoch fresh draw differs between epochs 0 and 1 when media_fresh=True and is identical when False.
- tests/test_determinism: `run.py --max-windows 80` with DATA_MEDIA_AREAS unset gives a loss-trace hash equal to the d97779d baseline.
- tests/test_resume: a resume with media on restores the media cursor bit-exactly (stream_state round trip).
- tests/test_contract K1 (both directions), K4/K5 (the docstring triple), K6/K12 (deferred reasons name AUD.loss_terms and EVAL.grounding), K13 (count 139); test_ownership O1-O15; test_census N2 (amendment rows); test_assemble A10 (docs/05 re-rendered).

ACCEPTANCE CHECKS
1. Full suite green.
2. With media off, the 80-window run.py trace is bit-identical to d97779d.
3. `DATA_MEDIA_AREAS=aud/tones,aud/melody run.py --max-windows 80` completes and prints media segment counts. The text trace differs only through the inserted caption bytes.
4. Generator throughput is at most 2 ms per 1 s clip on one thread (measured 0.4-1.3 ms).
5. DATA.recover is 100% on ground truth for every family.
6. No package imports another (O10); only spine/lever.py reads os.environ.

---

## Appendix B — GPU experiments per stage (the owner runs these)

All arms use 5 seeds and are paired where possible, like gpu_world.sh. Report per-area R-matrix readings, never pooled losses, and log windows/s for every arm under the 12-runs-per-card sharing.

S1 (data only): none. Optionally, time generator throughput on a GPU host CPU to confirm it is not a bottleneck at 12 concurrent runs.

S2 (text sampler): check sampler reproducibility and cost per 128-token sample for the GRU with state cache and the transformer with KV cache. Confirm that text bits/byte curves are unchanged over 20k windows (a regression check).

S3 (codec phase):
(a) AUD_ARCH spec against wave, where wave adds multi-scale STFT GAN + feature matching + quantizer dropout 0.5. Run 20k, 100k and 200k codec steps.
(b) 25 Hz against 50 Hz.
(c) Entropy bonus against the iFSQ 2σ(1.6x)-1 activation against plain FSQ (a collapse-rate census over 5 seeds).
(d) Levels 8,5,5,5 against 8,8,8,5,5,5.
Readings: mel, codes_used, perplexity, rms_ratio, and the DATA.recover ceiling on reconstructions per attribute (timbre is the weak one, 0.60).
Decision: the default arch and frame rate for S4.

S4/S5 (shared stream, goal B):
(a) 25 against 50 Hz at 20k windows: understanding and generation exact (train and held-out combinations), bits/code, bits/s, windows/s.
(b) LM_MEDIA_MASK on against off.
(c) Output-only loss against full loss.
(d) LM width 128 / 256 / 512, and media seconds per epoch 600 / 3,000 / 15,000 (fresh-data scaling; composition split).
(e) Phase protocol pure-add against rehearsed at DATA_TEXT_SHARE 0.1 / 0.3 / 0.5, and against an lr-shield of text rows. Schedule eng -> +aud/tones -> +aud/vowels -> +aud/melody -> eng. Report ACC/BWT/FWT for text bits/byte, audio grounding and WORLD MSE per area, plus a joint i.i.d. upper bound and a fine-tune lower bound.
(f) Throughput: windows/s at media shares of 0 / 30 / 70%, for the throughput-profiling agent.
(g) Transformer arm with LM_QK_NORM and LM_Z_LOSS on against off, with per-modality logit-norm gauges (Chameleon divergence check).
(h) The M2 purity measurement on the mixed stream, to decide whether the DOM class gate lands.

S6 (WORLD):
(a) WORLD_MEDIA_CTX none against gru, and WORLD_MEDIA_COND on against off; relative MSE at h1 and h5, per area.
(b) WORLD_FEEDBACK on against off on the forecast-caption task (captions describe notes 3-4 given only notes 1-2 of audio). 5 seeds, paired. This is the test Q-WORLD-10 left open for media.
(c) WORLD forgetting under pure-add against rehearsed.

S7 (video):
(a) VID codec 32x32 8x spatial against 64x64 16x spatial (both 32 tokens/s), then 64x64 8x (128 tokens/s) only if throughput allows.
(b) WORLD_LAT 32 against 64 for video (EXACT, so these are new runs).
(c) av/bounce cross-modal grounding in both directions.

S8 (arms), each judged on grounding per FLOP:
(a) The continuous insert of K=8 WORLD latents for understanding, against discrete-only.
(b) Factorised FSQ head against the joint 1000-way head.
(c) GIVT/MAR continuous head.
(d) WORLD-rollout generator with free-running loss plus a GMM or diffusion head (judged on legality and diversity against the grammar's 0.7/0.3).
(e) FAB_MOD_GROUPS against learned routing.
(f) Generative self-replay against data replay.
(g) MEM over media.
(h) Codec version handover (new block with nearest-row init) on a real-audio area.

Added by §0: a **bench arm before S3/S4 defaults** (R12) — `RUN_BENCH=1 RUN_PROFILE=1`, media off /
codec phase / media phase, at the owner's geometry under MPS, windows/s and peak memory per arm. And
a **throughput re-baseline** of the plain text run after 4feb65f, since every rate above predates it.

---

## Appendix C — The review, as delivered

The critic's full issue list, evidence and fixes are in
`results/multimodal_design_2026-09-25/workflow_result.json` under `critic`. Verdict: *sound with
fixes*; 2 blocking, 8 major, 3 minor; every one is answered in §0. Claims it verified in the tree:
the lm/api.py suffix dead mask, the ckpt missing-field refusal, WIRE_BUDGET=25 with 19 spent, the §7
count of 137, EVAL.generate and WORLD.manage deferred, data/api.py "holds nothing out", OPT refusing
groups other than base/encoder, `_base_parameters` only warning, and the S1 derive known-answer
arithmetic.
