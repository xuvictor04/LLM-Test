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
composed table (:1562, :3865) -- which is ISSUES P1-L51, and it is worse than the dead-weight
reading L13 gives it: not dead weight, two differently-trained decoders.

RECORD TYPES RETURNED (P4 defines them):
  LMGeometry   arch, width, layers (RESOLVED, never the sentinel), heads, ctx, pos_max,
               vocab_slots, compose, dropout, max_token_bytes, param_estimate
  MintReport   rows_initialised, arm_used, sig_rows_written, composer_rows, residual_ratio
  LoadReport   widened, refused, reason
"""
import dataclasses

from spine.lever import Config


class GeometryError(ValueError):
    """A shape decision that cannot produce a model, refused BY LEVER NAME before any allocation.

    NAMED RATHER THAN A BARE AssertionError, which is the whole repair. Verified by running it:
    nn.TransformerEncoderLayer(130, 8, ...) raises `AssertionError: embed_dim must be divisible by
    num_heads`, which names neither LM_WIDTH nor LM_HEADS, arrives on a warm device after the
    corpus has been pulled, and tells the operator nothing about which of the two numbers they
    typed to change.
    """


@dataclasses.dataclass(frozen=True)
class LMGeometry:
    """Every shape decision, RESOLVED, and the record the checkpoint gate compares against.

    `layers` IS THE RESOLVED DEPTH AND NEVER THE SENTINEL. The old tree read the depth at two sites
    with two different arm defaults -- `_i("LAYERS", 4)` and `_i("LAYERS", 1)` -- and wrote a third
    number at save time, so a reader of a checkpoint could not tell what depth the saved model was.
    _geometry_manifest raises if it is built before this record exists, for the same reason: a
    manifest recording 0 makes a run at LM_LAYERS=0 and one at LM_LAYERS=4 the same model under two
    values, which is a spurious EXACT mismatch refusing a resume that would have worked.
    """
    arch: str
    width: int
    layers: int
    heads: int
    ctx: int
    pos_max: int
    vocab_slots: int
    compose: bool
    dropout: float
    max_token_bytes: int
    param_estimate: int


# The depth each arm means by the 0 sentinel. NOT in spine.derive, and that is checked rather than
# assumed: there is no arm-to-depth function in that file, and inventing one would put a decision
# about THIS package's constructor in the shared arithmetic module. 0 layers is not a small model,
# it is a broken constructor, so the sentinel has to resolve to something and the arm is what knows.
_SENTINEL_DEPTH = {"gru": 1, "transformer": 4}


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
    pos_max, max_token_bytes = int(lm.d_pos_max), int(lm.d_max_token_bytes)

    arch, width, heads = str(lm.arch), int(lm.width), int(lm.heads)
    ctx, dropout = int(lm.ctx), float(lm.dropout)
    vocab_slots, compose = int(lm.vocab_slots), bool(lm.compose)
    declared_layers = int(lm.layers)

    # EVERY REFUSAL CARRIES BOTH NUMBERS AND THE ENVIRONMENT NAME. A Lever has no range facility and
    # `choices=` enumerates rather than bounds, so these cannot be declarations; what they must not
    # become is a bare exception from a constructor three frames down.
    bad = []
    if width < 1:
        bad.append(f"LM_WIDTH={width}: the model has no hidden dimension.")
    if heads < 1:
        bad.append(f"LM_HEADS={heads}: at least one attention head is required.")
    if ctx < 1:
        bad.append(f"LM_CTX={ctx}: a window of no tokens has nothing to predict.")
    if vocab_slots < 1:
        bad.append(f"LM_VOCAB_SLOTS={vocab_slots}: the embedding and output tables have no rows.")
    if declared_layers < 0:
        bad.append(f"LM_LAYERS={declared_layers}: negative depth. 0 is the sentinel meaning "
                   f"'this arm's default'; a negative number means nothing.")
    if not 0.0 <= dropout < 1.0:
        bad.append(f"LM_DROPOUT={dropout}: must be in [0.0, 1.0). At 1.0 every activation is "
                   f"dropped and the loss is constant.")
    if float(lm.anchor_uses) <= 0:
        # NAMES THE DROPPED LEVER, so a reader finds out here that the alternative went on purpose.
        bad.append(f"LM_ANCHOR_USES={float(lm.anchor_uses)}: there is no second release rule any "
                   f"more -- TOK_ANCHOR_TAU is dropped and the steps branch of anchor() went with "
                   f"it -- so 0 or less means 'hold every minted token at its composite forever', "
                   f"which no operator means to ask for.")
    if arch == "transformer" and width % heads != 0:
        # THE LOCAL COUPLING OVER TWO OF THIS PACKAGE'S OWN LEVERS, which is why it lives here and
        # not in either declaration: neither lever may read the other.
        bad.append(f"LM_WIDTH={width} is not divisible by LM_HEADS={heads} on the transformer arm. "
                   f"nn.TransformerEncoderLayer raises a bare 'embed_dim must be divisible by "
                   f"num_heads' naming neither knob, on a warm device, after the corpus is pulled.")
    if bad:
        raise GeometryError("LM.resolve refuses this geometry:\n  - " + "\n  - ".join(bad))

    layers = _SENTINEL_DEPTH.get(arch, 1) if declared_layers == 0 else declared_layers

    # ASSERTED SO IT STAYS UNREACHABLE. d_pos_max is today the local wire computed from ctx, so this
    # cannot fire; if that wire is ever re-sourced from somewhere else, a positional table shorter
    # than the window is an index error inside the forward pass rather than a refusal at startup.
    if ctx > pos_max:
        raise GeometryError(
            f"LM_CTX={ctx} exceeds the positional extent d_pos_max={pos_max}. This is unreachable "
            f"while d_pos_max is the intra-package coupling from ctx, and it is checked so that it "
            f"STAYS unreachable if that wire is ever re-sourced.")

    return LMGeometry(
        arch=arch, width=width, layers=layers, heads=heads, ctx=ctx, pos_max=pos_max,
        vocab_slots=vocab_slots, compose=compose, dropout=dropout,
        max_token_bytes=max_token_bytes,
        param_estimate=_param_estimate(arch, width, layers, ctx, vocab_slots, compose))


def _param_estimate(arch, width, layers, ctx, vocab_slots, compose):
    """A count for the banner and the manifest, computed from the SHAPES, not from a built module.

    AN ESTIMATE AND LABELLED ONE. The authoritative number is compose._n_params over the parameters
    the optimizer actually holds; this exists because the geometry gate runs BEFORE the first
    allocation and a refusal that cannot say how big the two models were is half a message. Under
    `compose` the token table is the ByteComposer's output and is TIED as input embedding and output
    head, so it is counted once and the ~6.3M dead parameters ISSUES P1-L13 counts do not exist.
    """
    tok_table = 0 if compose else vocab_slots * width       # tied: one table, or none under compose
    pos = ctx * width
    if arch == "transformer":
        # 4 * w^2 attention (q,k,v,o) + 8 * w^2 feed-forward at the usual 4x expansion, per layer.
        body = layers * (4 * width * width + 8 * width * width)
    else:
        # GRU: 3 gates, each over input and hidden, per layer.
        body = layers * (3 * (width * width + width * width))
    head = 0 if compose else vocab_slots * width
    return int(tok_table + pos + body + head)


def build_model(lm: Config, geom, *, device, seed):
    """Construct the network described by `geom` and return an nn.Module.

    ONE TOKEN TABLE, BOTH ARMS. When geom.compose is true the token vector table is the
    ByteComposer's output and is TIED as both the input embedding and the output head, ON THE
    TRANSFORMER ARM AS WELL. In the old tree TinyTransformer had no `compose` attribute at all
    (:1563-1594), so LM_COMPOSE=1 with LM_ARCH=transformer was a silent no-op while :6038 printed
    a coupling sentence about a mechanism that model did not have (ISSUES P1-M22). When compose is
    FALSE, emb and head are constructed; when TRUE they are NOT constructed at all, so the ~6.3M
    dead parameters ISSUES P1-L13 counts into every reported model size and every checkpoint do not
    exist.

    THE POSITIONAL TABLE IS d_pos_max ROWS TALL AND THERE IS NO CLAMP. :1586 did
    `p = torch.arange(L).clamp(max=s.maxlen - 1)` against a hardcoded MAXLEN=512, so every position
    past 511 shared ONE embedding with no error and no report line. encode() raises instead.

    DROPOUT REACHES BOTH ARMS, AND THE READOUT SITE IS IN decode(), NOT ON encode()'S RETURN.
    Q-LM-9 RESOLVED (b), 2026-09-02. The old gru arm had THREE dropout sites in two lines --
    `s.drop = nn.Dropout(DROPOUT)`; `h, _ = s.gru(s.drop(_e))`; `return s.drop(h)` (:1556-1558) --
    and the source's own comment on the third is `(B,L,D) hidden -- also the memory-key source`. It
    is: compose.py binds key_fn to LM.encode, so at dropout > 0 with the module in train mode EVERY
    memory key written during the loop is computed through a dropped-out hidden, while at eval the
    same function returns the undropped one. The store goal B is measured on would then be queried
    with keys drawn from a different distribution than the ones it holds, and FAB's router would see
    a different input in train and eval. The three sites this arm now has are: the embedding
    dropout, the inter-layer dropout at depth > 1, and the READOUT dropout, applied inside decode()
    before the head. Arithmetically that is the old `head(drop(h))` exactly -- nothing about the
    LM's own regularisation changes -- and it makes the key path train/eval consistent
    STRUCTURALLY rather than by convention, so ISSUES.md PART 1, M44 (holdout_bpb's finally block returning
    the model to TRAIN unconditionally) can no longer corrupt the store: the key path has no
    dropout left to leave switched on. On the transformer arm dropout is passed to
    nn.TransformerEncoderLayer(dropout=...), which the old tree HARDCODED to 0.0 at :1567, so
    LM_DROPOUT was 100% inert on MODEL=transformer while the report at :7990 told the operator to
    raise it -- and the readout site in decode() now reaches that arm too, which the old
    TinyTransformer (`forward`: `head(s.encode(x))`, no drop) did not have. Both are the same
    decision and the same P9 entry: this CHANGES numbers on the transformer arm the instant anyone
    sets dropout > 0, and at dropout > 0 on either arm FAB's routing input and MEM's keys change.
    AT THE 0.0 DEFAULT NOTHING MOVES AT ALL, on either arm.

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


def embed(lm: Config, model, x):
    """(B, L) token ids -> (B, L, width) TOKEN VECTORS. The lowest layer, and nothing else.

    ADDED 2026-09-02 (Q-LM-12 RESOLVED (b)). LOUD: THIS IS AN ADDITION TO THE FROZEN SIGNATURE SET,
    122 -> 123. The count lives in docs/04_CONTRACT.md section 7's header; the second addition this
    week, after LM.residual_ratios took it 121 -> 122 (Q-TOK-11).

    It is the token vector table applied to the ids: the ByteComposer's composed table under
    `lm.compose`, and `emb.weight` otherwise. It is NOT encode(): no GRU, no attention block, and --
    on the transformer arm -- NO POSITIONAL TERM. It carries no dropout.

    WHY IT HAD TO BE AN ENTRY POINT RATHER THAN AN ARGUMENT VALUE OR A ROOT-SIDE EXPRESSION.
    WORLD.loss_terms and WORLD.forecast both take `obs_emb`, documented as "LM's EMBEDDING of the
    batch ... the lowest layer, the point where a new sense plugs in", and nothing produced it.
    Three candidate producers were refused, each on evidence:
      * `encode(..., n_layers=0)`. Refused on BOTH arms. encode's own docstring says n_layers "runs
        only the first n blocks ON THE TRANSFORMER ARM ... on the gru arm it is accepted and
        ignored, and that is a DECLARED GATE" -- so on the shipped gru arm n_layers=0 returns the
        full GRU hidden, which is exactly what obs_emb must not be. And on the transformer arm zero
        blocks is `s.emb(x) + s.pos(p)` (:1587), embedding PLUS positional, which is not what the
        old world encoder received either: :6813 passes `model.emb(x)` alone.
      * The root reaching for `model.emb`. This is what ROW_ARGUMENTS_ELSEWHERE said until this
        edit, and it is an AttributeError on every run with `lm.compose = 1`: build_model above
        states that under compose `emb` and `head` "are NOT constructed at all". The old tree hid
        that -- MiniLM always built `s.emb` and merely used the composed table instead (:1549-1558)
        -- so `world_enc(model.emb(x))` did not crash at TOK_COMPOSE=1; it fed the world model an
        embedding table the LM was not training. TOK_COMPOSE defaulted to 0, so no recorded run hit
        it. It also puts an LM-internal attribute name in the composition root, which K7 cannot see
        because it checks Config reads and `model` is not a Config.
      * WORLD taking the hidden instead. That would falsify world/api.py's structural claim that
        "a second sense needs new rows in LM's embedding and nothing new here" -- goal A's room for
        more modalities -- and would make the world model predict the dynamics of a GRU state under
        the name of observations.
    Only LM knows which of the two tables is live, which is why this is LM's entry point and not an
    expression anywhere else.

    RECEIVES: x <- the flush's batch, cut from Segmentation.ids at _flush_bounds by the loop.
    RETURNS: (B, L, width) float tensor.

    LEVERS READ: compose (which table), width (the returned last dimension)
    WIRES READ: none
    DID IT FIRE: lm.embed.calls, lm.embed.from_composed_table (vs lm.embed.from_emb_weight --
                 exactly one is nonzero on a run, and which one is a fact the report must state
                 because it is the difference between the world model observing the table the LM
                 trains and observing one it does not)
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.embed: P4 (lm) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section LM.")


def encode(lm: Config, model, x, *, n_layers=None, extra=None):
    """(B, L) token ids -> (B, L, width) hidden, UNDROPPED. The memory-key source and the fabric's
    input.

    THE RETURN CARRIES NO DROPOUT, and that is the whole of Q-LM-9 (RESOLVED (b), 2026-09-02).
    `encode` returns the REPRESENTATION; `decode` performs the REGULARISED READOUT. Three packages
    consume this value -- MEM stores it as keys through key_fn, FAB routes on it, LM decodes it --
    and a value three packages consume must not carry one consumer's regulariser. The property that
    buys is that the memory keys are train/eval consistent by construction rather than by whoever
    last set the module's mode: `nn.Dropout` is identity in eval, so under the old shape the store
    held dropped-out keys and was queried with undropped ones at dropout > 0. There is no
    `for_key=` keyword and there must not be one -- a second path flag beside `n_layers`, which one
    arm already ignores, is how KEY_LAYERS became "silently inert twice over" (CENSUS.md:250).

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
    """(B, L, width) hidden -> (B, L, vocab_slots) logits. THE ONLY PLACE LOGITS ARE PRODUCED,
    AND THE ONLY PLACE THE READOUT DROPOUT IS APPLIED.

    THE READOUT DROPOUT LIVES HERE (Q-LM-9, 2026-09-02): `head(drop(h))`, which is arithmetically
    the old gru arm's `forward` (:1559-1561, where `encode` had already applied `s.drop` to its
    return and `forward` fed that to the head). It moved out of encode()'s return because that
    return is also the memory-key source and the fabric's input, and this function is already
    declared THE readout. On the transformer arm this site is new -- the old TinyTransformer's
    forward was `head(s.encode(x))` with no readout dropout at all -- which is the same P9 entry as
    the arm's other dropout sites: inert at the 0.0 default, a changed number the instant anyone
    raises it, and stated rather than discovered.

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

    LEVERS READ: mask_dead_rows, vocab_slots, compose -- NOT `dropout`. The readout dropout is the
                 nn.Dropout MODULE build_model constructed from geom; this function applies it, it
                 does not re-read the probability. A second read here would be a second declaration
                 of one number, which is what L1 exists to stop.
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
    bytes got IDENTICAL composites and identical starting vectors (ISSUES P1-M21).

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


def residual_ratios(lm: Config, model):
    """LM's JUDGEMENT-TIME read of how far each composed row has moved from its byte composite:
    ||delta[t]|| / ||composite[t]||, per live vocabulary slot. A PURE READ -- no grad, no side
    effect, no mutation of the composer -- returned as a (vocab_slots,) float vector, or None when
    lm.compose is False.

    WHY THIS ENTRY POINT EXISTS, AND IT IS A LOUD ONE: THE FROZEN SET GREW BY ONE HERE (121 -> 122,
    Q-TOK-11, ruled 2026-09-02). TOK.judge_probation's "embed" arm keeps a token iff `earned AND
    residual_ratio[t] >= tok.probation_residual`, and it used to source that vector from
    MintReport.residual_ratio -- produced by LM.on_mint AT THE MOMENT THE ROW IS CREATED, when the
    free residual starts at zero under every new_row_init arm. The comparison therefore fails for
    every candidate and the arm retires 100% of them: an arm that is wrong BY CONSTRUCTION rather
    than by tuning. The old tree gets this right and says why (self_organize.py:7600-7605): it
    recomputes from model.compose.table() and .delta at judgement time, because "the embedding test
    still requires the token to have been TRAINED -- a residual that is near zero because the token
    was never seen says nothing about the merge".

    IT IS NOT NEW MACHINERY, WHICH IS WHY IT IS CHEAP: LM.anchor_term already computes this exact
    quantity every flush ("holds a newly minted token's residual near its byte composite"). What was
    missing was an entry point that RETURNS the read. None of the other ten does -- counters()
    returns {name: int}, not a per-token float vector -- so the value had no producer at all.
    A wire is structurally impossible: it is read off a live tensor after build() freezes, which is
    the same ground that refuses EVAL.d_holdout_bytes and the SIG width. It reaches TOK as an
    ARGUMENT the composition root assembles, crossing no import -- the idiom MEM.write(key_fn=...)
    and DOM.rekey(encode=...) already use.

    THE GATE STAYS, ALONGSIDE, AND IS NOT AN ALTERNATIVE TO THIS CALL. At lm.compose = False there
    is no composer and no residual to read, so this returns None and TOK's Gate must print
    "unreachable (no residual_ratio supplied)" rather than silently running the "use" test -- which
    is ISSUES P1-M41, the record of the embed arm running the use test while the banner said embed.

    RETURNS: a (vocab_slots,) float vector indexed exactly as TOK's `appearances` is, or None.

    LEVERS READ: compose, vocab_slots
    WIRES READ: none
    DID IT FIRE: lm.residual_read (calls that returned a vector), lm.residual_rows (live slots read
                 -- 0 with a non-None return means the vocabulary has no composed rows yet, which is
                 a different statement from "compose is off"), Gate lm.residual_unreachable
                 (compose off -- printed with its predicate, never as silence)
    """
    lm = lm.owned_by("LM")
    raise NotImplementedError(
        "LM.residual_ratios: P4 (lm) fills this in. The contract is frozen here; see "
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
    torch error (ISSUES P1-M49). A COMPOSE FLIP IS REFUSED IN BOTH DIRECTIONS and named: under compose
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
