"""LM -- the frozen public surface. Signatures only; P4 writes the bodies.

LM is goal A's engine and nothing else: one network mapping a window of token ids to a
distribution over the next id, plus every number that fixes the shape of that network. The four
levers that decide what a newly minted symbol COSTS are where goal A's "room for additional
modalities" and goal B's row-level forgetting meet: a modality is a different alphabet, an
alphabet is rows in the embedding and the head, and compose / anchor_w / anchor_uses /
new_row_init are the whole mechanism by which those rows arrive as a HANDOVER rather than as a
discontinuity the optimizer must recover from (measured immediate post-mint loss, 6 pairs x 3
seeds: random 2.1699 sd 0.120, mean 1.8222 sd 0.078, last/first 1.4822 sd 0.011).
mask_dead_rows is the other end of the same goal-B statement: rows nobody has minted may not take
probability mass from rows somebody has.

ONE LOGITS PATH. `decode` is the only place logits are produced, on both arms, for training, for
eval and for the fabric (which receives it as a callable). The old tree had two -- training and
fab_logits through model.head (:6899, :4006) while model.forward and generate went through the
composed table (:1562, :3865) -- which is ISSUES L51, and it is worse than the dead-weight
reading L13 gives it: not dead weight, two differently-trained decoders.

RECORD TYPES RETURNED (P4 defines them):
  LMGeometry   arch, width, layers (RESOLVED, never the sentinel), heads, ctx, pos_max,
               vocab_slots, compose, dropout, max_token_bytes, param_estimate
  MintReport   rows_initialised, arm_used, sig_rows_written, composer_rows, residual_ratio
  LoadReport   widened, refused, reason
"""
from spine.lever import Config


def resolve(lm: Config):
    """Resolve every shape decision ONCE, before a tensor is allocated, and refuse the illegal ones
    BY NAME. Returns an immutable LMGeometry.

    `layers` is the RESOLVED depth -- the lever's 0 sentinel replaced by 4 on the transformer arm
    and 1 on the gru arm -- because spine.derive has no arm-to-depth function (verified: no such
    definition in the file) and 0 layers is not a small model, it is a broken constructor. The
    RESOLVED number, not the sentinel, is what goes in the banner and in the checkpoint: the old
    tree read the depth at two sites with two different arm defaults (:1599 `_i("LAYERS", 4)` and
    :1600 `_i("LAYERS", 1)`) and wrote a third at :5340, so a reader could not tell what depth a
    saved model was.

    REFUSES AT STARTUP, each with both numbers in the message, because a Lever has no range
    facility and `choices=` enumerates rather than bounds:
      * arch == "transformer" and width % heads != 0 -- verified by running it:
        nn.TransformerEncoderLayer(130, 8, ...) raises a bare
        `AssertionError: embed_dim must be divisible by num_heads` naming neither LM_WIDTH nor
        LM_HEADS. This is the LOCAL coupling over (LM.width, LM.heads) that belongs to something
        holding both.
      * dropout outside [0.0, 1.0); vocab_slots < 1; ctx < 1; layers < 0; width < 1; heads < 1.
      * anchor_uses <= 0 -- there is no second release rule any more. TOK_ANCHOR_TAU is dropped
        and the steps branch of anchor() goes with it, so 0 would mean "hold every minted token at
        its composite forever", which no operator means to ask for. The refusal NAMES the dropped
        lever, so that is also where a reader finds out the alternative went on purpose.
      * ctx > d_pos_max -- unreachable while d_pos_max is the local wire from ctx, and ASSERTED so
        that it STAYS unreachable if the wire is ever re-sourced.

    LEVERS READ: arch, width, layers, heads, ctx, dropout, vocab_slots, compose, anchor_uses
    WIRES READ: d_pos_max, d_max_token_bytes
    DID IT FIRE: lm.resolve.calls (must be exactly 1 per process),
                 lm.resolve.layers_from_sentinel (1 when cfg.layers == 0 -- proves which number
                 the run actually used)
    """
    lm = lm.owned_by("LM")
    _ = (lm.d_pos_max, lm.d_max_token_bytes)     # WIRES READ HERE -- both are geometry
    raise NotImplementedError(
        "LM.resolve: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def build_model(lm: Config, geom, *, device, seed):
    """Construct the network described by `geom` and return an nn.Module.

    ONE TOKEN TABLE, BOTH ARMS. When geom.compose is true the token vector table is the
    ByteComposer's output and is TIED as both the input embedding and the output head, ON THE
    TRANSFORMER ARM AS WELL. In the old tree TinyTransformer had no `compose` attribute at all
    (:1563-1594), so LM_COMPOSE=1 with LM_ARCH=transformer was a silent no-op while :6038 printed
    a coupling sentence about a mechanism that model did not have (ISSUES M22). When compose is
    FALSE, emb and head are constructed; when TRUE they are NOT constructed at all, so the ~6.3M
    dead parameters ISSUES L13 counts into every reported model size and every checkpoint do not
    exist.

    THE POSITIONAL TABLE IS d_pos_max ROWS TALL AND THERE IS NO CLAMP. :1586 did
    `p = torch.arange(L).clamp(max=s.maxlen - 1)` against a hardcoded MAXLEN=512, so every position
    past 511 shared ONE embedding with no error and no report line. encode() raises instead.

    DROPOUT REACHES BOTH ARMS. On the gru arm it is the embedding dropout, the inter-layer dropout
    at depth > 1, AND the dropout on the returned hidden state (:1556-1558 -- three sites, of which
    the lever's help text names two, and the third is the memory-key source). On the transformer
    arm it is passed to nn.TransformerEncoderLayer(dropout=...), which the old tree HARDCODED to
    0.0 at :1567, so LM_DROPOUT was 100% inert on MODEL=transformer while the report at :7990 told
    the operator to raise it. This CHANGES numbers on the transformer arm the instant anyone sets
    dropout > 0; at the 0.0 default nothing moves, and it belongs on P9's list.

    Seeding: calls spine.rng.rng_for("lm", seed) and initialises every tensor from that one stream,
    so LM's initialisation cannot be reordered by another package's draws.

    RECEIVES: device <- RUN.device, seed <- RUN.seed, geom <- resolve().
    RETURNS: nn.Module.

    LEVERS READ: none directly -- everything comes off `geom`, which is why resolve() is a separate
                 entry point: the refusals happen before allocation and the banner prints the same
                 object the constructor consumed.
    WIRES READ: none (through geom)
    DID IT FIRE: lm.build.arm_gru / lm.build.arm_transformer (exactly one is 1),
                 lm.build.compose_on, lm.build.heads_used (0 on gru -- the armed-but-inert
                 statement), lm.build.emb_head_allocated (must be 0 under compose -- kills L13),
                 rng.issued()["lm"]
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.build_model: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def encode(lm: Config, model, x, *, n_layers=None, extra=None):
    """(B, L) token ids -> (B, L, width) hidden. The memory-key source and the fabric's input.

    RAISES, DOES NOT CLAMP, when L > d_pos_max, naming LM_CTX and the actual L. That refusal is the
    whole point of the d_pos_max wire: `grep -rn d_ src/` finds the height and lever.py will not
    let anyone declare a lever that shadows it, but until something REFUSES the overflow the
    guarantee the wire buys is not paid for.

    n_layers runs only the first n blocks on the transformer arm, for the memory-key path
    (:1580-1593: at LAYERS=12 the key path was paying twelve layers of attention over an 8-token
    window, thousands of rows per step). It arrives as an ARGUMENT from MEM.key_depth; LM does not
    import MEM. On the gru arm it is accepted and ignored, and that is a DECLARED GATE, not a
    silence -- CENSUS.md:250 records KEY_LAYERS as "silently inert twice over".

    `extra` is an optional additive term on the hidden state, (B, L, width) or None. It exists so
    WORLD's forecast can condition the LM as a PARAMETER rather than by rebinding model.encode:
    the monkey-patch at :4158-4169 let a timing probe's stale module enumeration put 29 world-model
    parameters into the training loop holding gradients computed from RANDOM TOKENS, so PROBE=1 and
    PROBE=0 split at the second logged step (6.1199 vs 6.1125) and never rejoined. A timing probe
    decided the run.

    LEVERS READ: none directly
    WIRES READ: d_pos_max
    DID IT FIRE: lm.encode.calls, lm.encode.key_path_truncated (n_layers actually reduced the
                 stack), lm.encode.pos_overflow_refused (MUST BE 0 -- a nonzero value is the 512
                 clamp reaching the new tree), lm.encode.extra_applied
    """
    lm = lm.owned_by("LM")
    _ = lm.d_pos_max                             # WIRE READ HERE -- the refusal, not a clamp
    raise NotImplementedError(
        "LM.encode: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def decode(lm: Config, model, h, *, live_vocab, retired_ids):
    """(B, L, width) hidden -> (B, L, vocab_slots) logits. THE ONLY PLACE LOGITS ARE PRODUCED.

    Under compose it is `h @ table.t() + bias` from the tied composed table; otherwise the head
    Linear. Then mask_dead_rows is applied HERE, once, so training and every eval path share one
    masked distribution. Masking at the LOSS only was measurably WORSE than not masking at all
    (86.7% dead width: unmasked 4.746, masked-at-the-loss-only 6.100, :3971-3979), because the
    model is never taught to push the dead rows down and every eval path then scores it with those
    untrained rows still in the denominator.

    This function is what the spine hands to FAB as a plain callable so the fabric can decode its
    expert outputs without importing lm. O10 refuses the import; a callable another package
    returned is not an import.

    live_vocab and retired_ids arrive from TOK. Never-minted rows are [live_vocab:]; RETIRED ROWS
    ARE BELOW live_vocab AND ARE NOT A SUFFIX (probation pops from seq2id while leaving id2bytes
    intact so ids stay positional -- on the probation arms 217 and 224 of 256 minted tokens were
    retired and sailed straight through a suffix-only mask, :3982-3987). The mask is cached on
    (live_vocab, len(retired_ids)); both only ever grow.

    LEVERS READ: mask_dead_rows, vocab_slots, compose
    WIRES READ: none
    DID IT FIRE: lm.decode.calls, lm.mask.applied, lm.mask.rows_masked (the count, so the dead
                 fraction is a number the report prints rather than infers), lm.mask.armed_no_rows
                 (mask on, nothing dead -- reported SEPARATELY from "off")
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.decode: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def lm_loss(lm: Config, logits, y):
    """Cross-entropy over the masked logits. Returns (per_window: (B,), mean: scalar).

    reduction='none' then mean(-1) then mean(), arithmetically identical to F.cross_entropy's own
    reduction but leaving the PER-WINDOW numbers available -- competence attribution, the domain
    EMA and the marginal-contribution counterfactual all read them (:6899-6902) and none of them
    can be tracked without them.

    This is the ONLY term LM contributes to the objective besides anchor_term. Auxiliary weights
    (ponder, balance, chain-supervision, diversity, independence) belong to whoever composes the
    loss; LM must not be able to add terms to it, which is the rule that put RECON_W in OPT and
    then dropped it.

    LEVERS READ: vocab_slots
    WIRES READ: none
    DID IT FIRE: lm.loss.calls
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.lm_loss: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def anchor_term(lm: Config, model, *, token_seen):
    """The loss term that holds a newly minted token's residual near its byte composite, ALREADY
    MULTIPLIED BY anchor_w. Returns None when there is nothing young enough to hold.

    RETURNING THE WEIGHTED TERM IS DELIBERATE: TOK_ANCHOR=0.05 was printed on the EFFECTIVE line of
    every run in this project's history while model.compose was None and the term never once
    entered the loss, because it was simply missing from the loss-weight list at :5802-5813. A
    weight read in one package and applied in another is how that happens; here the number and the
    tensor never separate.

    token_seen is a (vocab_slots,) float tensor of APPEARANCES in trained-on material, owned and
    incremented by the training loop from the batch the model is about to be trained on
    (:6804 `_tok_seen.index_add_(0, x.reshape(-1), ...)`). It arrives as an ARGUMENT rather than as
    a global the loss term reaches for by name (:6307), because a per-token counter reached by name
    from inside a loss term is the shape of coupling the ledger cannot see. Counting APPEARANCES
    rather than steps is also what makes the anchor independent of re-segmentation by construction:
    `seen` only advances when the token turns up in a training batch, so a retok cannot move it.

    Never-minted rows have born = -1e9 and are masked out of the mean, so they dilute nothing.

    LEVERS READ: anchor_w, anchor_uses, compose
    WIRES READ: none
    DID IT FIRE: lm.anchor.fired (a non-None term entered the loss), lm.anchor.none_young (compose
                 on, anchor_w > 0, nothing under the release horizon -- armed but 0),
                 lm.anchor.unreachable (compose off -- the declared Gate, printed with its
                 predicate, never as silence)
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.anchor_term: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def on_mint(lm: Config, model, mints, id2bytes, *, at_window, sig_emb=None):
    """Everything that happens to LM's tensors when the tokenizer mints ids. Returns a MintReport.

    `mints` is TOK's list of Mint records; `id2bytes` is the WHOLE table after the mint. Three
    things happen, IN THIS ORDER, UNCONDITIONALLY:
      1. the composer is told the vocabulary grew (set_vocab) and the birth window is stamped
         (note_born). This is CORRECTNESS, not warm-starting, and in the old tree it sat inside the
         WARMSTART block (:7624-7633) -- see TOK.mint_burst for what that cost.
      2. when compose is FALSE, the new emb/head/head.bias rows are initialised per new_row_init:
         "random" leaves the constructor's initialisation, "mean" writes 0.5*(a+b) into all three,
         "last_first" writes emb[nid]=emb[b] and head[nid]=head[a] -- THE TWO SIDES ARE NOT
         SYMMETRIC: head scores "next is ab" from the state BEFORE consuming a, emb is what the
         recurrence consumes AFTER. When compose is TRUE this step is skipped and that is a
         declared Gate.
      3. when sig_emb is given (SIG's nn.Embedding, handed in by the spine, never imported), the
         same rule writes enc.emb.weight[nid]. This replaces the inline reach at :7702-7705. A
         domain centroid is a mean of encodings, so one freshly-random token id inside a window
         perturbs every signature containing it and the assembler reads that as a domain shift --
         SIG needs this MORE than the LM does.

    The composer's byte tables are sized to geom.max_token_bytes (the d_max_token_bytes wire), not
    to a hardcoded 16 (:1441): with MAX_TOK > 16 two distinct long tokens sharing their first 16
    bytes got IDENTICAL composites and identical starting vectors (ISSUES M21).

    MintReport.residual_ratio (||delta[nid]|| / ||composite[nid]||) is the value TOK's probation
    "embed" arm has nothing to compare without.

    LEVERS READ: new_row_init, compose, vocab_slots
    WIRES READ: none (max_token_bytes arrives through geom)
    DID IT FIRE: lm.mint.rows_init_random / _mean / _last_first (exactly one accumulates),
                 lm.mint.compose_skip, lm.mint.sig_rows (0 when sig_emb was not supplied --
                 distinguishes "SIG is in token space and got its rows" from "SIG is in byte space
                 and needs none" from "nobody passed it"), lm.mint.set_vocab_calls (must equal the
                 number of MINT EVENTS, not the number of mints), lm.compose.table_calls
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.on_mint: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def state_dict(lm: Config, model, geom):
    """The tensors plus the resolved LMGeometry, so a resume can refuse a mismatch BY KNOB NAME.

    The old checkpoint recorded model_type and layers at :5340 and nothing about maxlen, heads,
    compose or max_token_bytes, so a shape mismatch surfaced as "it can be failing on FAB_EMB_HID,
    SIG_D or D_MODEL and no prefix of it means anything" (:4678-4684).

    IN THE CHECKPOINT: the module; the composer's `born` tensor (without it a resume releases every
    token's anchor immediately or holds every token forever); the counters; the geometry. NOT in
    it: the composer's derived byte-index tensors (_idx/_msk/_len/_v -- rebuilt on load, so a
    resume with a re-segmented vocabulary cannot come back with a stale table) and the dead-row
    mask cache.

    LEVERS READ: none (everything comes off geom)
    WIRES READ: none
    DID IT FIRE: lm.ckpt.saved
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.state_dict: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def load_state(lm: Config, model, geom, saved):
    """Fit a saved checkpoint into the live model, or refuse. Returns a LoadReport.

    WIDENS on vocab_slots only, BY PREFIX: slot i is still slot i and token id i is still token
    id i (:846-877). A resume that cannot widen the softmax cannot add capacity for the area it is
    adding: the run that motivated widen_prefix had the vocabulary full at 2048/2048, so a new
    language got ZERO tokens of its own and was segmented entirely with the previous one's merges.

    REFUSES, by name and with both numbers: any NARROWING of vocab_slots; any change to width,
    arch, resolved layers, heads, ctx/pos_max or compose; a missing key the live model has. The old
    tree used strict=True on the model while the fabric loaded strict=False for exactly this
    reason, so adding one parameter to the LM made every existing checkpoint unresumable with a raw
    torch error (ISSUES M49). A COMPOSE FLIP IS REFUSED IN BOTH DIRECTIONS and named: under compose
    emb/head do not exist, so the two are not resume-compatible either way, and a resume across it
    would index a trained head by a vocabulary that means something different.

    Cross-checks the d_vocab_ceiling consequence: LM refuses when saved.vocab_slots >
    geom.vocab_slots and SAYS WHICH FILE TO LOOK AT -- a tokenizer file carrying its own larger
    vmax is the ZERO-mint failure at :1231-1241.

    LEVERS READ: vocab_slots (via geom)
    WIRES READ: none
    DID IT FIRE: lm.ckpt.loaded, lm.ckpt.rows_widened (the count, per tensor), lm.ckpt.refused
                 (with the reason string, so a refusal is a Reading and not a traceback)
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.load_state: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def counters(lm: Config, model):
    """The DID IT FIRE ledger for this package: {name: int}. No torch, no side effects.

    Every gated mechanism above appears here in the three-state form G4 requires -- `fired N`,
    `armed but 0`, `unreachable (<predicate with its arithmetic>)` -- so that "set but inert" and
    "not set" are two different statements. The old tree made both look like silence.

    LEVERS READ: arch, compose, mask_dead_rows, anchor_w, new_row_init, heads, layers, width, ctx,
                 dropout, anchor_uses, vocab_slots (to render each gate's predicate with the
                 numbers that made it true or false)
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.counters: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")
