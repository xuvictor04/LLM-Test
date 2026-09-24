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
               vocab_slots, compose, dropout, max_token_bytes, param_estimate,
               layers_from_sentinel
  MintReport   rows_initialised, arm_used, sig_rows_written, composer_rows, residual_ratio
  LoadReport   widened, refused, reason
"""
import dataclasses
import math

import torch
from torch import nn
from torch.nn import functional as F

from spine.lever import Config
from spine import rng as _rng
from spine.gate import Gate, NotBuilt
from spine.init import is_scale as _is_scale


# PROCESS-LIFETIME DID-IT-FIRE TALLY. `counters()` below is documented to return {name: int} for
# every gate this package declares, and it is STILL a P4 stub (raises NotImplementedError, and it
# is not one of the eleven items this pass was asked to repair) -- so until that body exists there
# is nowhere else for "N calls" or "N rows masked" to accumulate. This dict is what it will read.
# A plain dict rather than collections.Counter so `.get(name, 0)` stays the one lookup: a name
# absent from it is "never touched this process" and a name present with 0 is "touched, fired
# zero times" -- the same armed-vs-untouched distinction spine/rng.py's Rng.draws makes for random
# streams, kept here for the same reason (G4's three states start at whether a mechanism was even
# reached).
_COUNTS = {}


def _bump(name, n=1):
    _COUNTS[name] = _COUNTS.get(name, 0) + n


def _set(name, value):
    # A GAUGE, NOT A TALLY -- for a quantity like "how many rows are dead right now", summing
    # across calls (`_bump`) would make lm.mask.rows_masked grow with every decode() call instead
    # of reporting the vocabulary's actual dead fraction, which only grows with the vocabulary
    # itself. The LATEST value is the informative one; counters() reads this the same dict as
    # `_bump`'s, the two just disagree about whether repetition should accumulate.
    _COUNTS[name] = value


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

    `layers_from_sentinel` IS A SEPARATE FACT FROM `layers`. Before this field existed, a run at
    LM_ARCH=transformer LM_LAYERS=0 and one at LM_LAYERS=4 produced an IDENTICAL LMGeometry (both
    resolve to layers=4), so nothing in the returned record -- and nothing in the report built from
    it -- could say which of the two numbers the operator actually typed. That is exactly the
    confusion the docstring above cites for `layers` itself, one level up: not "what depth did the
    run use" (answered) but "did the operator ask for that depth by name, or get it by omission".
    resolve()'s own DID IT FIRE line already promised `lm.resolve.layers_from_sentinel`; this field
    is what lets that promise be kept from a value carried on the record, not a global counted only
    by whoever happened to call resolve() last.
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
    layers_from_sentinel: bool


# The depth each arm means by the 0 sentinel. NOT in spine.derive, and that is checked rather than
# assumed: there is no arm-to-depth function in that file, and inventing one would put a decision
# about THIS package's constructor in the shared arithmetic module. 0 layers is not a small model,
# it is a broken constructor, so the sentinel has to resolve to something and the arm is what knows.
_SENTINEL_DEPTH = {"gru": 1, "transformer": 4}


class _LM(nn.Module):
    """The network `geom` describes. ONE TOKEN TABLE, BOTH ARMS, and it is TIED under compose.

    UNDER compose THE emb AND head LINEARS ARE NOT CONSTRUCTED AT ALL -- not built and unused, not
    built and zeroed: absent. The old TinyTransformer had no `compose` attribute, so LM_COMPOSE=1
    with LM_ARCH=transformer was a silent no-op while the banner printed a coupling sentence about
    a mechanism that model did not have (ISSUES P1-M22), and the ~6.3M dead parameters ISSUES P1-L13
    counts into every reported size and every checkpoint were real on the other arm. Here they do
    not exist, so `n_params` and the checkpoint both shrink and neither has to explain why.

    THE POSITIONAL TABLE IS pos_max ROWS TALL AND THERE IS NO CLAMP anywhere in this class. The old
    `p = torch.arange(L).clamp(max=s.maxlen - 1)` against a hardcoded 512 gave every position past
    511 ONE shared embedding, with no error and no report line. encode() raises instead.

    THREE DROPOUT SITES ON THE GRU ARM AND THE READOUT IS NOT ONE OF encode()'s (Q-LM-9 (b)). The
    embedding dropout and the inter-layer dropout live here; the readout dropout is applied in
    decode(), before the head. Arithmetically that is the old `head(drop(h))` exactly. What it buys
    is that encode()'s return -- which MEM stores as keys and FAB routes on -- carries no
    regulariser, so the store is not written with dropped-out keys and queried with undropped ones.
    """

    def __init__(self, geom):
        super().__init__()
        self.geom = geom
        w, v = geom.width, geom.vocab_slots
        self.compose = geom.compose
        self.pos = nn.Embedding(geom.pos_max, w)
        self.drop = nn.Dropout(geom.dropout)
        if not geom.compose:
            self.emb = nn.Embedding(v, w)
            self.head = nn.Linear(w, v)
        else:
            # THE COMPOSE ARM'S OUTPUT BIAS. decode()'s docstring promises the composed readout is
            # `h @ table.t() + bias`, and until this line nothing built a `bias` for that arm to
            # add: LM_COMPOSE=1 would have produced a strictly bias-free softmax the moment
            # composed_table() became buildable (it still raises NotBuilt -- the ByteComposer is a
            # separate, still-stubbed TOK-side piece, so this arm cannot be exercised end-to-end
            # yet), while the banner and the checkpoint went on describing a decoder with a
            # per-row bias -- every logit and every reported bits/byte would have shifted relative
            # to the non-compose arm the numbers are compared against, silently. NOT part of the
            # tied table (that is exactly (vocab_slots, width); this is a second, (vocab_slots,)
            # parameter beside it) and NOT the ~6.3M dead parameters ISSUES P1-L13 counts -- L13 is
            # emb/head existing AND UNUSED, and this exists only under compose and is added on
            # every compose decode.
            self.compose_bias = nn.Parameter(torch.zeros(v))
        if geom.arch == "transformer":
            layer = nn.TransformerEncoderLayer(
                d_model=w, nhead=geom.heads, dim_feedforward=4 * w,
                # PASSED, NOT HARDCODED. The old tree wrote dropout=0.0 into this constructor, so
                # LM_DROPOUT was 100% inert on the transformer arm while the report told the
                # operator to raise it.
                dropout=geom.dropout, batch_first=True, norm_first=True)
            self.body = nn.TransformerEncoder(layer, num_layers=geom.layers)
        else:
            self.body = nn.GRU(w, w, num_layers=geom.layers, batch_first=True,
                               dropout=geom.dropout if geom.layers > 1 else 0.0)
        # decode()'s dead-row mask cache, keyed on (live_vocab, len(retired_ids)) -- see decode()'s
        # docstring. A plain python attribute (a tuple containing a tensor, not a bare Parameter or
        # Module), so nn.Module.__setattr__ does not register it as a parameter or buffer: it must
        # not appear in state_dict() or move with a bare .to(device) the way a real buffer would,
        # because decode() re-checks the tensor's device against `logits.device` on every lookup
        # and rebuilds on a mismatch rather than trusting a stale cross-device cache.
        self._dead_mask_cache = None

    def token_table(self):
        """The (vocab_slots, width) table, whichever arm built it. Under compose it is the
        ByteComposer's output, TIED as both the input embedding and the output head."""
        return self.composed_table() if self.compose else self.emb.weight

    def composed_table(self):
        raise NotBuilt(
            "LM.compose: the ByteComposer is P4's TOK-side row and lands with LM.mint_rows. The "
            "compose arm is reachable (LM_COMPOSE=1 resolves and this module refuses to build a "
            "dead emb/head for it) and its table is not built yet.")


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
    _bump("lm.resolve.calls")
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

    # RECORDED ON THE GEOMETRY, NOT JUST COUNTED: LM_LAYERS=0 and LM_LAYERS=4 on the transformer
    # arm both resolve `layers` to 4, so the resolved field alone cannot say which one the operator
    # typed -- and this is the exact confusion `layers` itself was made RESOLVED to end, one level
    # up. Measured before this field existed: two LMGeometry values built from those two lever
    # settings compared dataclasses.asdict()-equal on every field.
    layers_from_sentinel = declared_layers == 0
    if layers_from_sentinel:
        _bump("lm.resolve.layers_from_sentinel")
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
        param_estimate=_param_estimate(arch, width, layers, ctx, vocab_slots, compose),
        layers_from_sentinel=layers_from_sentinel)


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

    Seeding: calls spine.rng.rng_for("lm.init", seed) -- A CHILD OF THE "lm" STREAM RUN.streams
    MINTS AT STEP 0, NOT "lm" ITSELF -- and initialises every tensor from that one stream, so LM's
    initialisation cannot be reordered by another package's draws. THIS SENTENCE SAID "lm" UNTIL
    2026-09-03 and the code beneath it had already stopped touching that name: RUN.streams mints
    "lm" into spine.rng's register unconditionally at step 0 (compose.RNG_SUBSYSTEMS), so asking for
    it again here -- even under `again=True` -- would produce a second live Rng replaying the
    identical sequence while the object the root holds kept reporting zero draws forever, which is
    the P1-H55 / P1-H56 collision shape. The repair drew from a child stream instead and left "lm"
    declared and untouched by design; what it did not do was update this paragraph or the DID IT
    FIRE row below to say so, so a reader following THIS docstring to check "did build_model seed
    itself" would grep rng.issued() for "lm" and find it present in every process regardless of
    whether build_model ever ran -- RUN.streams put it there either way -- and read that as proof
    of firing. It is not: "lm" reporting zero draws forever is the CORRECT state, and "lm.init" is
    where a reader must look instead.

    RECEIVES: device <- RUN.device, seed <- RUN.seed, geom <- resolve().
    RETURNS: nn.Module.

    LEVERS READ: none (nothing off `lm` directly -- everything comes off `geom`, which is why
                 resolve() is a separate entry point: the refusals happen before allocation and the
                 banner prints the same object the constructor consumed)
    WIRES READ: none (through geom)
    DID IT FIRE: lm.build.arm_gru / lm.build.arm_transformer (exactly one is 1),
                 lm.build.compose_on, lm.build.heads_used (0 on gru -- the armed-but-inert
                 statement), lm.build.emb_head_allocated (1 on the emb/head arm; it would be 0
                 under compose -- the L13 kill -- and that arm is refused below before anything is
                 allocated, so on a built model compose_on reads 0 and emb_head_allocated 1),
                 rng.issued()["lm.init"] (NOT "lm" -- "lm" is expected to report ZERO draws
                 forever; that is the declared parent staying declared, not a mechanism failing to
                 fire). THE FIVE lm.build.* GAUGES WERE DECLARED HERE AND WRITTEN NOWHERE UNTIL
                 2026-09-24 -- no string literal for any of them existed in src/, so on both
                 LM_ARCH arms all five were ABSENT, which G4 reads as the build being UNREACHABLE.
                 They are written through _set at the end of this body, into the tally counters()
                 reads (the model has no `counters` attribute).

    LM_COMPOSE=1 IS REFUSED HERE, AT STARTUP, WITH spine/gate.py::NotBuilt (2026-09-24). The
    compose arm resolves, and until this date it built a model with no emb/head and composed on
    ... nothing: _LM.composed_table raises NotBuilt because the ByteComposer is not built in this
    tree, so compose() returned with 0 refusals, ran the whole SIG warm-up, and the run died at
    its FIRST FLUSH with that exception (driven: LM_COMPOSE=1 at DATA_STREAM_BYTES=60000). The
    refusal now fires before the first allocation, and run.py prints it as a REFUSED line and
    exits 2, the way it prints FAB_HOP_MODE=transition's.
    """
    lm = lm.owned_by("LM")
    if bool(geom.compose):
        raise NotBuilt(
            f"LM_COMPOSE=1: {_COMPOSER_UNBUILT}. Refused at LM.build_model, before any tensor is "
            f"allocated, rather than at the first flush where _LM.composed_table would raise. Run at "
            f"LM_COMPOSE=0, where the emb/head rows exist.")
    # A CHILD OF THE DECLARED PARENT, NOT A SECOND "lm". RUN.streams mints "lm" into the register
    # at step 0; asking for that same name again -- even with again=True, which is documented for a
    # checkpoint rebuild -- produces a SECOND live Rng replaying the identical sequence, so the
    # object the root holds reports zero draws forever while this function quietly consumed the
    # values it would have handed out. That is the P1-H55 / P1-H56 shape a third time, and the
    # repair is the one already ruled twice: the parent stays declared and this package draws from
    # a child.
    stream = _rng.rng_for("lm.init", int(seed))
    # ON THE TARGET DEVICE. torch's in-place random ops require the generator and the tensor to
    # share a device, so a cpu Generator filling parameters already moved to cuda raises on every
    # GPU run while every CPU test passes.
    gen = torch.Generator(device=device)
    gen.manual_seed(stream.randint(0, 2 ** 31 - 1))

    model = _LM(geom).to(device)
    for name, t in model.named_parameters():
        with torch.no_grad():
            if t.dim() >= 2:
                # Xavier-uniform by fan, computed here rather than through nn.init so every tensor
                # draws from the ONE generator above and the order is this loop's, not torch's.
                fan_in, fan_out = t.shape[-1], t.shape[0]
                bound = math.sqrt(6.0 / (fan_in + fan_out))
                t.uniform_(-bound, bound, generator=gen)
            elif _is_scale(name):
                # A 1-D PARAMETER IS NOT ALWAYS ADDITIVE, and the first draft of this loop assumed
                # it was. `t.zero_()` on every 1-D tensor zeroes each LayerNorm's WEIGHT, which
                # MULTIPLIES the normalised activation -- so every residual branch in the
                # transformer output zero, half its tensors got no gradient, and the loss still
                # came out at exactly ln(vocab_slots) because a uniform distribution is what a dead
                # network produces. A plausible number from a broken model is this project's whole
                # subject; it was caught by counting which tensors received a gradient, not by
                # reading the loss.
                t.fill_(1.0)
            else:
                t.zero_()
    # THE GATES ARE DECLARED WHERE THE ARM IS DECIDED, WHICH IS HERE. counters() has been printing
    # "gate:lm.none_declared" -- "the obligation is on whoever ports those arms: declare the Gate
    # where the arm is decided, at build, with the numbers that made it true or false" -- and these
    # two are that obligation kept for the two arms whose bodies landed with them. Recomputing
    # reachability inside anchor_term or residual_ratios would give this package two answers to
    # "could it fire", which is the defect the Gate record was introduced to end.
    #
    # BOTH ARE reachable=False TODAY AND ON BOTH ARMS OF compose, for two different reasons, and
    # the reason string carries which. At compose off there is no composer by configuration; at
    # compose on the ByteComposer is not built in this tree (_LM.composed_table raises NotBuilt,
    # and LM.on_mint -- which HAS A BODY since 2026-09-21, where this line used to call it a stub --
    # raises NotBuilt at LM_COMPOSE=1 for the same missing composer), so the mechanism cannot run
    # either way. THE CONCLUSION IS UNCHANGED AND ONLY ITS REASON MOVED: what is absent is TOK's
    # ByteComposer, not a body in this file. Declaring them reachable at
    # compose=1 would put "armed, did not fire" -- the words Gate.line reserves for a mechanism
    # that RAN -- on a mechanism that has no body to run.
    # THE COMPOSE-ON REASON IS NOW REACHED ONLY BY A MODEL NOT BUILT HERE (2026-09-24): this body
    # refuses LM_COMPOSE=1 with NotBuilt at its first line, so a model this function returns always
    # carries the `_off` reason. The branch stays, so the day the ByteComposer lands and the refusal
    # goes, the gates already say the right thing on both arms.
    # THE UNBUILT SENTENCE IS THE ONE _composer_books HANDS BACK, not a second copy of it: the gate
    # and the entry points that take the same arm say the same thing because they read the same
    # string, which is the only way two sentences about one mechanism cannot drift apart.
    _off = ("the LM_COMPOSE arm is off, so the token table is emb.weight and a row has no byte "
            "composite to be held near or measured against")
    model.gates = (
        Gate(name="lm.anchor.unreachable", fired=False,
             value=geom.compose, threshold=True, reachable=False,
             reason=(_COMPOSER_UNBUILT if geom.compose else _off)),
        Gate(name="lm.residual_unreachable", fired=False,
             value=geom.compose, threshold=True, reachable=False,
             reason=(_COMPOSER_UNBUILT if geom.compose else _off)),
    )
    # THE FIVE BUILD GAUGES, through the tally counters() reads (see DID IT FIRE above).
    _set("lm.build.arm_gru", int(geom.arch == "gru"))
    _set("lm.build.arm_transformer", int(geom.arch == "transformer"))
    _set("lm.build.compose_on", int(bool(geom.compose)))
    _set("lm.build.heads_used", int(geom.heads) if geom.arch == "transformer" else 0)
    _set("lm.build.emb_head_allocated",
         int(getattr(model, "emb", None) is not None or getattr(model, "head", None) is not None))
    return model


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
    _bump("lm.embed.calls")
    # THE TABLE COMES FROM model.token_table(), WHICH IS THE ONE PLACE THAT KNOWS WHICH ARM BUILT
    # IT. Writing `model.emb.weight` here would be the second of the three producers this
    # docstring refuses, and it is an AttributeError on every run with lm.compose set, because
    # build_model does not construct `emb` at all on that arm. token_table() is also what decode()
    # reads, so the vectors the world model observes and the vectors the head scores against are
    # the same tensor by construction rather than by two call sites agreeing.
    table = model.token_table()
    # WHICH ARM ANSWERED IS COUNTED, because the docstring makes it a reporting obligation: it is
    # "the difference between the world model observing the table the LM trains and observing one
    # it does not". Exactly one of these two is nonzero on a run. The flag is read off `model`
    # rather than off `lm.compose` so the count reports the table that was actually returned.
    _bump("lm.embed.from_composed_table" if model.compose else "lm.embed.from_emb_weight")
    # EMBEDDING, AND NOTHING ELSE. No positional term (the transformer arm adds one inside encode),
    # no dropout (decode owns the regulariser), no block. F.embedding rather than `table[x]` because
    # the two differ on a non-contiguous index tensor and this one is the documented spelling for a
    # table that may be a composed intermediate carrying grad.
    return F.embedding(x, table)


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

    LEVERS READ: ctx (ONLY on the pos-overflow refusal path, to print LM_CTX beside the actual
                 window length in the raised message -- the read is the `int(lm.ctx)` in the raised
                 message below. Every other line in this function reads nothing off `lm` directly:
                 the shapes and arm come off `model`/`model.geom`, which is why WIRES READ carries
                 d_pos_max instead of a second read of `ctx` for the boundary check itself --
                 resolve() already asserts ctx == d_pos_max's source, so a second lever read here
                 would be a second declaration of the one number it checks against)
    WIRES READ: d_pos_max
    DID IT FIRE: lm.encode.calls, lm.encode.key_path_truncated (n_layers actually reduced the
                 stack), lm.encode.pos_overflow_refused (MUST BE 0 -- a nonzero value is the 512
                 clamp reaching the new tree), lm.encode.extra_applied; and two FLOAT GAUGES
                 written on the same arm, lm.encode.extra_ratio (the latest RMS(extra)/RMS(h),
                 h before the add) and lm.encode.extra_ratio_max (its running max) -- all three
                 ABSENT when no `extra` is ever passed
    """
    lm = lm.owned_by("LM")
    _bump("lm.encode.calls")
    pos_max = int(lm.d_pos_max)                  # WIRE READ HERE -- the refusal, not a clamp
    L = int(x.shape[1])
    if L > pos_max:
        # RAISES, DOES NOT CLAMP, and names both numbers. The old clamp gave every position past
        # the table's height ONE shared embedding, silently. That refusal is what the d_pos_max
        # wire is FOR: grep finds the height and lever.py refuses a lever that shadows it, but
        # until something refuses the overflow the guarantee is not paid for.
        _bump("lm.encode.pos_overflow_refused")
        raise ValueError(
            f"LM.encode was handed a window of {L} token(s) against a positional table of "
            f"{pos_max} row(s) (LM_CTX={int(lm.ctx)} through the d_pos_max wire). Refused rather "
            f"than clamped: a clamp gives every position past the height one shared embedding, "
            f"with no error and nothing in the report.")

    e = model.token_table()[x] if model.compose else model.emb(x)
    h = model.drop(e + model.pos.weight[:L].unsqueeze(0))
    if model.geom.arch == "transformer":
        # CAUSAL, because this is a language model: a window that can see its own future scores a
        # loss no autoregressive decode can reproduce.
        mask = torch.triu(torch.full((L, L), float("-inf"), device=h.device), diagonal=1)
        # n_layers RUNS ONLY THE FIRST n BLOCKS, BY A MANUAL LOOP OVER model.body.layers RATHER
        # THAN nn.TransformerEncoder's OWN forward. nn.TransformerEncoder has no depth argument --
        # slicing .layers is the only way to stop early -- and looping by hand is also what buys
        # the dropout fix immediately below: whichever layer's output IS this call's return, full
        # stack or truncated key path alike, needs different treatment than the layers before it.
        # This loop reproduces nn.TransformerEncoder.forward's own per-layer call exactly
        # (src_mask=mask, is_causal=True) and that module's internal fast/nested-tensor path never
        # engages on the plain forward either, because that path requires src_key_padding_mask,
        # which this function never passes -- so a full-depth call through this loop is numerically
        # identical to the old `model.body(h, mask=mask, is_causal=True)` (verified: max|dh|=0.0
        # between the two on a built model, both arms, several seeds).
        n_run = model.geom.layers if n_layers is None else int(n_layers)
        if n_layers is not None:
            # MEM.key_depth's cut. Before this branch existed, n_layers reached this function and
            # nothing here read it: model.body(h, ...) always ran the FULL stack regardless of what
            # the caller asked for, so at LM_LAYERS=12 the key path paid twelve layers of attention
            # over an 8-token window on every step -- thousands of rows per training step -- and
            # the declared counter below could never be nonzero. Measured before this fix:
            # encode(..., n_layers=1) against the full-depth call differed by max|dh|=0.0.
            _bump("lm.encode.key_path_truncated")
        for i, layer in enumerate(model.body.layers[:n_run]):
            if i == n_run - 1:
                # THE LAST LAYER ACTUALLY RUN -- full stack or truncated key path alike -- computed
                # WITHOUT ITS OWN INTERNAL DROPOUT: the attention-probability dropout inside
                # self_attn, and the two residual dropouts (dropout1, dropout2), by toggling
                # eval() for this one call and restoring the layer's prior mode after. nn.GRU
                # already gives this for free -- torch documents its `dropout=` as applied "to the
                # output of each GRU layer EXCEPT THE LAST", so the gru arm's `h, _ =
                # model.body(h)` below was already clean -- but nn.TransformerEncoder has no such
                # carve-out: every layer it owns drops, INCLUDING the one whose output is this
                # function's return, and that is a fourth dropout site nobody chose. Measured
                # before this fix: built at LM_DROPOUT=0.2, arch=transformer, set model.drop.p=0.0
                # (silencing ONLY the embedding-dropout site) and called encode() twice in train
                # mode on one input under no_grad -- the two returns still differed; in eval mode
                # two calls agreed with each other and disagreed with the train-mode value, which
                # is what proves the leak lived inside TransformerEncoderLayer's own dropout sites
                # and not in `model.drop`. LayerNorm is unaffected by .eval()/.train(), so toggling
                # the layer's mode for one call changes nothing but its dropout sites.
                was_training = layer.training
                layer.eval()
                try:
                    h = layer(h, src_mask=mask, is_causal=True)
                finally:
                    layer.train(was_training)
            else:
                h = layer(h, src_mask=mask, is_causal=True)
    else:
        h, _ = model.body(h)
        # n_layers IS ACCEPTED AND IGNORED HERE, ON PURPOSE -- a DECLARED GATE, not a silence.
        # nn.GRU is one fused recurrence over its whole depth, not a ModuleList this function can
        # slice the way the transformer arm's stack allows, so "run only the first n blocks" has no
        # meaning on this arm. CENSUS.md:250 records the old KEY_LAYERS knob as "silently inert
        # twice over" because nothing anywhere said this arm could not honour it; this comment, and
        # the "DECLARED GATE" framing in the docstring above, are what keep the inertness a stated
        # fact instead of a second occurrence of that same defect.

    if extra is not None:
        # THE ADDITIVE CONDITIONING TERM, ON THE FINAL HIDDEN STATE -- not fed into the stack as a
        # second input, added to what the stack produced, because it exists to condition what MEM
        # and FAB see, not to change how the transformer/GRU itself computes (WORLD.forecast's own
        # docstring: "the forecast the LM's hidden state IS CONDITIONED ON"). Shape- and
        # device-checked rather than silently broadcast or moved: a caller passing (B, width) would
        # otherwise broadcast into (B, L, width) and condition every position with a
        # batch-mean-shaped typo, and a caller building `extra` on a stale device is a bug this
        # function should not paper over with a .to() nobody asked for.
        if extra.shape != h.shape:
            raise ValueError(
                f"LM.encode: extra has shape {tuple(extra.shape)}, hidden has shape "
                f"{tuple(h.shape)}. extra must be exactly (B, L, width) or None.")
        if extra.device != h.device:
            raise ValueError(
                f"LM.encode: extra is on device {extra.device}, hidden is on {h.device}. Refused "
                f"rather than silently moved.")
        # THE OTHER HALF OF world.forecast_rms, WHICH WORLD CANNOT FORM: only this function holds
        # both the hidden state and the term added to it, so only here is the forecast's size
        # RELATIVE to h a reading rather than a guess. RMS(extra)/RMS(h), h taken BEFORE the add,
        # both reduced in one stack so the pair costs ONE device sync. The latest value and the
        # running max, as gauges: nothing bounds the forecast's magnitude (Q-WORLD-10, "Open for
        # the owner"), and on CPU at 300 windows, seeds 0-4, the latest read 0.41-1.87 and the max
        # 0.74-3.08, so the max is the number that says whether the forecast has started to
        # dominate the readout. Both ABSENT
        # when no `extra` ever arrives (WORLD_FEEDBACK=0, the null world).
        with torch.no_grad():
            _ms = torch.stack([extra.detach().float().pow(2).mean(),
                               h.detach().float().pow(2).mean()]).sqrt().tolist()
        _ratio = _ms[0] / max(_ms[1], 1e-12)
        _set("lm.encode.extra_ratio", round(_ratio, 6))
        _set("lm.encode.extra_ratio_max",
             round(max(_ratio, float(_COUNTS.get("lm.encode.extra_ratio_max", 0.0))), 6))
        h = h + extra
        _bump("lm.encode.extra_applied")

    # UNDROPPED ON THE WAY OUT. Three packages consume this -- MEM as keys, FAB as routing input,
    # LM as the readout source -- and a value three packages consume must not carry one consumer's
    # regulariser. There is no `for_key=` keyword and there must not be one.
    return h


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

    Under compose it is `h @ table.t() + bias` from the tied composed table (`model.compose_bias`,
    a second (vocab_slots,) parameter beside the tied table -- NOT part of it, and NOT the ~6.3M
    dead parameters ISSUES P1-L13 counts, which is emb/head existing AND UNUSED); otherwise the
    head Linear, whose own bias is already inside `model.head`. Then mask_dead_rows is applied
    HERE, once, so training and every eval path share one masked distribution. Masking at the LOSS
    only was measurably WORSE than not masking at all (86.7% dead width: unmasked 4.746,
    masked-at-the-loss-only 6.100, :3971-3979), because the model is never taught to push the dead
    rows down and every eval path then scores it with those untrained rows still in the
    denominator.

    This function is what the spine hands to FAB as a plain callable so the fabric can decode its
    expert outputs without importing lm. O10 refuses the import; a callable another package
    returned is not an import.

    live_vocab and retired_ids arrive from TOK. Never-minted rows are [live_vocab:]; RETIRED ROWS
    ARE BELOW live_vocab AND ARE NOT A SUFFIX (probation pops from seq2id while leaving id2bytes
    intact so ids stay positional -- on the probation arms 217 and 224 of 256 minted tokens were
    retired and sailed straight through a suffix-only mask, :3982-3987). The mask is cached on
    (live_vocab, len(retired_ids)); both only ever grow.

    `live_vocab` IS `Vocabulary.size()` AND NOT `live_size` -- the positional BOUNDARY where
    never-minted rows begin, not a count of the rows that are live. The two differ by exactly the
    retired count, and since retired ids sit BELOW the boundary (the paragraph above), passing
    `live_size` moves the boundary down and masks that many LIVE rows to -inf. Written into this
    docstring on 2026-09-03 and not left in a comment in the body, because the contract is the
    docstring: two independently worded rows in `spine/compose.py` had both named `live_size`, and
    the refusal being invisible to a check is what let them. tests/test_contract.py's K14 reads this
    sentence now.

    LEVERS READ: mask_dead_rows (NOT `vocab_slots` or `compose`, which the body takes off
                 `logits.shape[-1]`, already resolved when the table/head was built, and
                 `model.compose`, the module's own flag set once in the constructor, rather than
                 re-reading either off the Config. NOT `dropout` either: the readout dropout is the
                 nn.Dropout MODULE build_model constructed from geom; this function applies it, it
                 does not re-read the probability. A second read of any of the three here would be
                 a second declaration of a number that already has an owner, which is what L1
                 exists to stop. Those negatives sit INSIDE this parenthesis rather than after a
                 dash because tests/test_contract.py::_split_items cuts this line at top-level
                 commas and keeps an item only when it is a bare identifier: unparenthesised prose
                 swallows the name standing in front of it, and that is how `mask_dead_rows` came
                 to be dropped from its own declaration while counters() -- a stub that has never
                 read it -- carried the package's only surviving K4 credit for it)
    WIRES READ: none
    DID IT FIRE: lm.decode.calls, lm.mask.applied, lm.mask.rows_masked (the count, so the dead
                 fraction is a number the report prints rather than infers), lm.mask.armed_no_rows
                 (mask on, nothing dead -- reported SEPARATELY from "off")
    """
    lm = lm.owned_by("LM")
    _bump("lm.decode.calls")
    # THE REGULARISED READOUT, and this is the only site. Arithmetically identical to the old
    # `head(drop(h))`; what moved is that encode()'s return no longer carries it.
    h = model.drop(h)
    if model.compose:
        table = model.token_table()
        logits = h @ table.t() + model.compose_bias
    else:
        logits = model.head(h)

    if bool(lm.mask_dead_rows):
        # MASKED HERE, ONCE, so training and every eval path share ONE distribution. Masking at the
        # LOSS only was measurably WORSE than not masking at all -- 86.7% dead width scored 4.746
        # unmasked against 6.100 masked-at-the-loss-only -- because the model is never taught to
        # push the dead rows down and every eval path then scores it with those untrained rows
        # still in the denominator.
        _bump("lm.mask.applied")
        # CACHED ON THE MODEL, KEYED ON (live_vocab, len(retired_ids)) -- THE DOCSTRING'S OWN KEY,
        # AND BOTH HALVES ONLY EVER GROW. Before this cache existed, every single decode() call
        # allocated a fresh `vocab_slots`-length bool tensor and, whenever anything was retired, a
        # fresh sorted index tensor from a Python set -- once per window, on the hot path, at
        # LM_VOCAB_SLOTS=16384 with hundreds of retired ids on the probation arms -- which is pure
        # waste the docstring's own cache key already ruled out. A cache MISS still costs exactly
        # what the old unconditional build cost; a HIT costs one tuple comparison.
        key = (int(live_vocab), len(retired_ids))
        cached = model._dead_mask_cache
        if cached is not None and cached[0] == key and cached[1].device == logits.device:
            dead = cached[1]
        else:
            dead = torch.zeros(logits.shape[-1], dtype=torch.bool, device=logits.device)
            # `live_vocab` IS THE COUNT OF MINTED ROWS, AND IT IS ALSO WHERE THEY END, because ids
            # are positional and minting is append-only: rows [0, live_vocab) exist and
            # [live_vocab, slots) never did. THE TWO ARE ONLY THE SAME NUMBER WHEN NOTHING IS
            # RETIRED, and the caller passes Vocabulary.size() -- the full id count -- rather than
            # live_size(), precisely so that this boundary does not move when a row is retired.
            # Retired ids are handled BELOW, by id, for the same reason: retire() pops from the
            # match table and leaves id2bytes intact so ids stay positional, so retired rows are
            # scattered below the boundary and are not a suffix.
            dead[int(live_vocab):] = True
            if retired_ids:
                # RETIRED ROWS ARE BELOW live_vocab AND ARE NOT A SUFFIX. Probation pops from
                # seq2id while leaving id2bytes intact so ids stay positional, so a suffix rule
                # would mask the wrong rows -- and on the probation arms most minted tokens were
                # retired.
                idx = torch.tensor(sorted(retired_ids), dtype=torch.long, device=logits.device)
                dead[idx] = True
            model._dead_mask_cache = (key, dead)
        n_dead = int(dead.sum().item())
        _set("lm.mask.rows_masked", n_dead)          # a gauge: dead rows AS OF THIS CALL
        if not n_dead:
            _bump("lm.mask.armed_no_rows")            # a tally: how many calls found nothing dead
        logits = logits.masked_fill(dead, float("-inf"))
    return logits


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
    _bump("lm.loss.calls")
    # THE LAST DIMENSION IS CHECKED AGAINST THE LEVER, WHICH IS THE ONLY THING vocab_slots IS READ
    # FOR HERE. logits arrive from decode(), which builds them from a (vocab_slots, width) table,
    # so a mismatch means the logits and the model disagree about how many rows exist -- and
    # cross_entropy would happily score them anyway, against class ids it silently reinterprets.
    slots = int(lm.vocab_slots)
    if logits.shape[-1] != slots:
        raise ValueError(
            f"LM.lm_loss: logits have {logits.shape[-1]} classes and LM_VOCAB_SLOTS is {slots}. "
            f"Cross-entropy does not check this, so a run would score every window against the "
            f"wrong class ids and report a loss that means nothing.")
    # reduction='none' THEN mean(-1) THEN mean(). Arithmetically identical to cross_entropy's own
    # 'mean' ONLY when every window has the same length, which is the case here because the batch is
    # cut at a fixed L -- and the difference that matters is not the number, it is that the
    # PER-WINDOW vector survives. Competence attribution, the domain EMA and the marginal-
    # contribution counterfactual all read it (:6899-6902) and not one of them can be tracked from
    # a scalar. Taking the reduction and then trying to recover the parts is what this returns
    # instead of.
    flat = F.cross_entropy(logits.reshape(-1, slots), y.reshape(-1), reduction="none")
    per_window = flat.view(y.shape).mean(-1)
    return per_window, per_window.mean()


# THE COMPOSER'S TWO PER-TOKEN BOOKS, AND THE SENTENCE FOR WHEN THEY ARE NOT THERE.
_COMPOSER_UNBUILT = (
    "the ByteComposer is not built in this tree: _LM.composed_table raises NotBuilt, and LM.on_mint "
    "-- which HAS A BODY, and whose step 1 is the composer's set_vocab/note_born -- raises NotBuilt "
    "at LM_COMPOSE=1 rather than running, so no token has a free residual (`delta`) or a birth "
    "stamp (`born`) yet. This string said 'LM.on_mint is a P4 stub' until 2026-09-22; the state it "
    "describes is the same and the reason for it is not")


def _composer_books(model):
    """(delta, born, reason) -- the composer's per-token residual table and birth stamps, or
    (None, None, why-not).

    THE NAMES ARE THE ONES THIS MODULE ALREADY COMMITTED TO. LM.state_dict reads
    `getattr(model, "born", None)` and saves it under "born" with a written absence reason, so
    `born` is where the birth stamps live on this module whether or not anything builds them yet;
    `delta` is the other half of the same record -- world_model-era ByteComposer keeps the two
    beside each other (self_organize.py:1455-1457) and both are per-token tables of the vocabulary's
    width. Whoever builds the composer lands them here, and the two readers below then fire without
    another edit.

    THIS IS NOT THE `hasattr(...) else <unchanged>` DEFECT, and the difference is what happens on the
    absent arm. That shape is refused because it turns a wrong assumption into a SILENT NO-OP: the
    caller proceeds with a stale value and the report describes a mechanism that did not run. Here
    the absent arm returns a distinguished answer with a reason attached, every caller counts it
    under its own name, and NOTHING proceeds as if the books were there.
    """
    delta = getattr(model, "delta", None)
    born = getattr(model, "born", None)
    if delta is None or born is None:
        return None, None, _COMPOSER_UNBUILT
    return delta, born, ""


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
    _bump("lm.anchor.calls")
    if not model.compose:
        # THE DECLARED GATE'S ARM, AND IT IS NOT SILENCE. build_model declares
        # Gate("lm.anchor.unreachable") with this same predicate and its numbers, so counters()
        # renders "UNREACHABLE" with the arithmetic beside it rather than a 0 that reads like a
        # measurement. There is no composer at lm.compose=False -- emb/head are the token table and
        # a row has no residual to be held near a composite it does not have -- so this is
        # unreachable, not armed-and-inert.
        _bump("lm.anchor.unreachable")
        return None
    weight = float(lm.anchor_w)
    if weight == 0.0:
        # ARMED AND PRICED AT ZERO. Returning `0.0 * term` here would put an exact zero into the
        # objective and let the report count a fire, which is the thing this entry point's
        # docstring exists to prevent from the other direction: LM_ANCHOR_W=0.05 was printed on the
        # EFFECTIVE line of every run in this project's history while the term never entered the
        # loss. A term nobody weights did not fire, and this counter says which of the three states
        # that is.
        _bump("lm.anchor.weight_zero")
        return None
    delta, born, _why = _composer_books(model)
    if delta is None:
        # THE COMPOSER IS NOT BUILT IN THIS TREE. Not fabricated, not stubbed around: the residual
        # table the anchor penalises does not exist, so there is nothing to hold and the counter
        # says exactly that. This is a THIRD state and it is neither "compose is off" (the gate
        # above) nor "nothing is young enough" (the measurement below); collapsing it into either
        # would make the report answer a question nobody asked.
        _bump("lm.anchor.no_composer")
        return None
    if token_seen is None:
        # THE COUNTER LIVES IN THE TRAINING LOOP, NOT HERE (self_organize.py:1530 takes the same
        # branch), and `anchor_uses` is now the ONLY release rule -- TOK_ANCHOR_TAU, the steps-side
        # rival, is dropped by the census, so there is no second schedule to fall back to. Counted
        # rather than substituted: a zero counter would hold every row at full weight for ever,
        # which is not "no anchor" but "the strongest possible anchor", and a caller who forgot the
        # argument would get the opposite of what the omission looks like.
        _bump("lm.anchor.no_counter")
        return None

    # THE WIDTHS ARE CHECKED, NOT MINIMISED. lm_loss refuses a logits width that disagrees with the
    # lever for the same reason: taking min() of three tables would anchor a PREFIX of the
    # vocabulary and report a full anchor, and the rows it dropped are the recently minted ones --
    # exactly the cohort the anchor exists for.
    rows = int(delta.shape[0])
    if int(born.numel()) != rows or int(token_seen.shape[0]) != rows:
        raise ValueError(
            f"LM.anchor_term: the composer's residual table has {rows} row(s), its birth stamps "
            f"{int(born.numel())} and the appearance counter {int(token_seen.shape[0])}. These "
            f"three index ONE vocabulary, so a disagreement is a mint that reached some of them "
            f"and not the others -- anchoring the overlap would hold a prefix and report a whole "
            f"vocabulary.")
    uses = float(lm.anchor_uses)
    seen = token_seen.detach().to(delta.dtype)
    # APPEARANCES, NOT STEPS, AND THE FLOOR IS THE SOURCE'S OWN. A token minted early appears
    # constantly and is thoroughly trained; one minted late is rare BY CONSTRUCTION -- that is WHY
    # it was minted late -- so a shared wall-clock release is anti-correlated with how ready each
    # token is. max(1.0, uses) keeps the exponential defined at LM_ANCHOR_USES=0; it is not the
    # `max(1, ...)` coercion this tree refuses elsewhere, because that one rewrote a lever the
    # banner then printed unchanged, and this one is a division guard on a value the report reads
    # from the Config either way.
    w = torch.exp(-seen / max(1.0, uses))
    # NEVER-MINTED ROWS ARE NOT YOUNG, THEY ARE ABSENT. born is -1e9 for an id that has never been
    # minted, and the appearances rule cannot tell "minted, not yet seen" from "does not exist" --
    # both sit at seen=0 and would be held at FULL weight. Their delta is zeros and stays zeros, so
    # the term they contribute is 0 either way; masking them keeps the reported MAGNITUDE
    # comparable between vocabularies of different fullness, which is what a per-row mean destroys.
    minted = born > -10 ** 8
    w = w * minted.to(w.dtype)
    _set("lm.anchor.rows_minted", int(minted.sum()))
    if float(w.max()) < 1e-3:
        # ARMED, AND NOTHING IS YOUNG ENOUGH. The measurement state: the mechanism ran, every
        # minted row has been seen enough times for its weight to have decayed past the floor, and
        # the anchor has released them all. Distinct from every branch above it.
        _bump("lm.anchor.none_young")
        return None
    term = (w[:, None] * delta.pow(2)).sum(-1).mean()
    _bump("lm.anchor.fired")
    # ALREADY MULTIPLIED, WHICH IS THE WHOLE POINT OF RETURNING THE TERM RATHER THAN THE NUMBER.
    # LM_ANCHOR_W was read in one package and applied in another, and the application was simply
    # missing from the loss-weight list at :5802-5813 while the weight went on being printed. Here
    # the number and the tensor never separate.
    return weight * term


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
    arm, compose_on = str(lm.new_row_init), bool(lm.compose)
    slots = int(lm.vocab_slots)
    # `id2bytes` IS READ BY STEP 1 AND BY NOTHING ELSE, so off the compose arm it is unused HERE
    # and that is the contract rather than a loose end: it is the composer's input -- the whole
    # table after the mint, sized to geom.max_token_bytes so two long tokens sharing their first 16
    # bytes cannot get identical composites (P1-M21) -- and step 1 is the branch that raises
    # NotBuilt below. It stays in the signature because the signature is frozen and because the day
    # the ByteComposer lands it is what set_vocab takes.
    _ = id2bytes

    # SEEDED BEFORE ANY BRANCH DECIDES, so ABSENT never masquerades as ZERO -- the rule
    # fabric/api.py::grow_check states and the one sig/api.py broke for a whole run. All six are
    # reachable on some arm of this call, so all six are present from the first mint event onward.
    for _k in ("lm.mint.rows_init_random", "lm.mint.rows_init_mean", "lm.mint.rows_init_last_first",
               "lm.mint.compose_skip", "lm.mint.sig_rows", "lm.compose.table_calls"):
        _bump(_k, 0)
    # ONE PER MINT EVENT AND NOT ONE PER MINT, which is the docstring's own requirement
    # ("must equal the number of MINT EVENTS, not the number of mints"). A burst of six tokens is
    # ONE call and therefore one set_vocab, and a counter that counted tokens would read six on a
    # tree where the composer was told once.
    _bump("lm.mint.set_vocab_calls")

    if compose_on:
        # 1. THE COMPOSER IS TOLD THE VOCABULARY GREW -- AND THERE IS NO COMPOSER TO TELL.
        # NotBuilt AND NOT NotImplementedError, and the distinction is the tree's: NotImplementedError
        # is the P4 stub marker tests/test_census.py counts, and this body is not a stub. The
        # ByteComposer is a separate, still-unbuilt TOK-side piece -- LMModel.composed_table() raises
        # NotBuilt in as many words -- so `set_vocab` and `note_born` have no object to be called on,
        # and steps 2 and 3 below cannot substitute for them: step 2 is explicitly skipped under
        # compose (the rows are the composer's output, not parameters), so returning a report here
        # would claim a mint event that left the vocabulary's new ids pointing at nothing.
        raise NotBuilt(
            "LM.on_mint at LM_COMPOSE=1: step 1 of this entry point is `composer.set_vocab` plus "
            "`note_born`, and the ByteComposer is DECLARED AND NOT BUILT in this tree -- "
            "LMModel.composed_table() says so and raises the same exception. It is not a stub and "
            "this is not NotImplementedError: what is missing is TOK's composer, not this body. "
            "Under compose the new rows are the composer's OUTPUT and step 2 is skipped by "
            "contract, so there is nothing this call could do instead that would leave the minted "
            "ids pointing at a trained vector. Run at LM_COMPOSE=0, where the emb/head rows exist "
            "and new_row_init writes them.")

    # 2. THE NEW ROWS, UNDER THE ARM new_row_init NAMES. THIS IS GOAL B's ROW-LEVEL CASE and
    # lm/levers.py says so: "a freshly minted token id points at a randomly initialised embedding
    # row and a randomly initialised head row, so the model must re-learn from scratch material it
    # can already spell with the parents". The three arms ARE that experiment.
    # THE TWO SIDES ARE NOT SYMMETRIC, which is why "last_first" is not a typo for "first_first":
    # `head` scores "the next token is ab" from the state BEFORE a has been consumed, so it takes
    # a's row; `emb` is what the recurrence consumes AFTER the token, so it takes b's.
    written = 0
    with torch.no_grad():
        emb_w = model.emb.weight
        head_w, head_b = model.head.weight, model.head.bias
        for m in mints:
            nid, a, b = int(m.new_id), int(m.left_id), int(m.right_id)
            if not (0 <= a < slots and 0 <= b < slots and 0 <= nid < slots):
                # REFUSED BY NAME RATHER THAN CLAMPED OR SKIPPED. An id at or above vocab_slots is a
                # token the embedding table has no row for, and writing it would be an IndexError at
                # best and a silent wrap at worst; TOK.mint_burst refuses to mint past
                # d_vocab_ceiling for the same reason and from the same number, so a pair arriving
                # here out of range means the two ceilings have come apart (DEFECT D-T1).
                raise GeometryError(
                    f"LM.on_mint: Mint(new_id={nid}, left_id={a}, right_id={b}) against "
                    f"LM_VOCAB_SLOTS={slots}. Every one of the three must be a row this model has. "
                    f"d_vocab_ceiling is this same number and TOK.mint_burst refuses to mint past "
                    f"it, so an id out of range here means the vocabulary's ceiling and the model's "
                    f"row count have come apart -- which is DEFECT D-T1, a saved ceiling outliving "
                    f"the wire.")
            if arm == "mean":
                emb_w[nid] = 0.5 * (emb_w[a] + emb_w[b])
                head_w[nid] = 0.5 * (head_w[a] + head_w[b])
                # ALL THREE, which the docstring says of this arm and only of this arm.
                head_b[nid] = 0.5 * (head_b[a] + head_b[b])
                written += 1
            elif arm == "last_first":
                emb_w[nid] = emb_w[b]
                head_w[nid] = head_w[a]
                # THE BIAS IS LEFT AT THE CONSTRUCTOR'S VALUE ON THIS ARM, deliberately and
                # literally: the contract writes "mean" as "0.5*(a+b) into all three" and
                # "last_first" as "emb[nid]=emb[b] and head[nid]=head[a]" -- two tensors, named.
                # Copying the bias as well would be a fourth write nobody measured, on the arm whose
                # 1.4822 (sd 0.011) is the number every later comparison is against.
                written += 1
            # "random" IS AN ARM THAT RUNS AND WRITES NOTHING. The constructor's initialisation IS
            # the arm -- lm/levers.py records WARMSTART folding into this lever as its "random"
            # value -- so there is no branch here, and the counter below is what says it ran.
    # EXACTLY ONE OF THE THREE ACCUMULATES, which is the docstring's requirement, and the "random"
    # row counts the rows that TOOK that arm rather than the rows it wrote -- it writes none, and a
    # 0 there would be indistinguishable from an arm that never ran. `written` is the other two's,
    # and it is what MintReport.rows_initialised reports, so the record and the ledger answer the
    # same question with the same number on the arms where a row was written.
    _bump({"random": "lm.mint.rows_init_random", "mean": "lm.mint.rows_init_mean",
           "last_first": "lm.mint.rows_init_last_first"}[arm],
          len(mints) if arm == "random" else written)

    # 3. SIG'S OWN ROW FOR THE SAME TOKEN, under the same rule. SIG NEEDS THIS MORE THAN THE LM
    # DOES: a domain centroid is a MEAN of encodings, so one freshly-random token id inside a window
    # perturbs every signature containing it and the assembler reads that as a domain shift -- a
    # spurious shift caused by the tokenizer, arriving at the mechanism whose whole job is to notice
    # real ones. The table is handed in by the spine as an nn.Embedding; this package never imports
    # sig.
    sig_rows = 0
    if sig_emb is not None:
        with torch.no_grad():
            sw = sig_emb.weight
            n_rows = int(sw.shape[0])
            for m in mints:
                nid, a, b = int(m.new_id), int(m.left_id), int(m.right_id)
                if not (nid < n_rows and a < n_rows and b < n_rows):
                    # SKIPPED AND COUNTED, NOT RAISED, AND THE ASYMMETRY WITH STEP 2 IS THE POINT:
                    # SIG's encoder may legitimately be in BYTE space, where it has 256 rows and no
                    # row for a token id at all. That is not a broken ceiling, it is a different
                    # alphabet, and the counter's declared job is to tell "SIG is in token space and
                    # got its rows" from "SIG is in byte space and needs none" from "nobody passed
                    # it" -- three states, of which this is the second.
                    continue
                if arm == "mean":
                    sw[nid] = 0.5 * (sw[a] + sw[b])
                elif arm == "last_first":
                    sw[nid] = sw[b]
                sig_rows += 1
        _bump("lm.mint.sig_rows", sig_rows)

    # `at_window` IS RECORDED AND NOT COMPARED. Under compose it would be note_born's stamp; off
    # compose there is no composer to hold a birth table and TOK's `prov` already carries the birth
    # window (("online", born)), which is the table that survives a checkpoint. A second home for
    # the same number is what DEFECT D-T3 is about, so this gauge is a READING of the last mint
    # event and never a source anything reads back.
    _set("lm.mint.last_window", int(at_window))
    # lm.mint.compose_skip IS SEEDED AND CAN NEVER INCREMENT ON THIS TREE, and saying so is cheaper
    # than leaving a reader to wonder. It counts step 2 being skipped because the rows are the
    # composer's output -- a state only reachable at LM_COMPOSE=1, where this body raises NotBuilt
    # at step 1 and never reaches step 2 at all. The key is present-and-0 rather than absent
    # because the mechanism IS declared and the arm IS legal; what is missing is the composer.
    return MintReport(rows_initialised=written, arm_used=arm, sig_rows_written=sig_rows,
                      composer_rows=0, residual_ratio=None)


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
    _bump("lm.residual.calls")
    if not model.compose:
        # THE GATE'S ARM, AND M41'S REPAIR. At lm.compose = False there is no composer and no
        # residual to read, so this returns None and TOK's Gate prints "unreachable (no
        # residual_ratio supplied)" rather than silently running the "use" test -- which is ISSUES
        # P1-M41, the record of the embed arm running the use test while the banner said embed.
        _bump("lm.residual_unreachable")
        return None
    delta, born, _why = _composer_books(model)
    if delta is None:
        # DECLARED AND NOT BUILT. Counted apart from the compose arm above because the two say
        # different things to TOK: "this run has no composer by configuration" and "this tree has
        # no composer yet". Both return None, and a consumer that cannot tell them apart would read
        # the second as the first and stop asking.
        _bump("lm.residual.no_composer")
        return None
    try:
        table = model.composed_table()
    except NotBuilt:
        # NotBuilt IS CAUGHT BY NAME AND NOTHING ELSE IS. spine/gate.py::NotBuilt exists for exactly
        # this -- "a mechanism that is DECLARED and deliberately NOT BUILT, refused at the point of
        # use" -- and it deliberately does not subclass NotImplementedError, so catching it cannot
        # swallow a P4 stub marker. A bare `except` here would also catch the shape and device
        # errors a real composer can raise, and would report "no composer" for a composer that is
        # there and broken.
        _bump("lm.residual.table_unbuilt")
        return None
    slots = int(lm.vocab_slots)
    if int(table.shape[0]) != slots or int(delta.shape[0]) != slots:
        # THE RETURN IS PROMISED AS (vocab_slots,) AND INDEXED EXACTLY AS TOK'S `appearances` IS.
        # A narrower vector would be read by id and would answer about the wrong token, which is
        # the class of defect that makes a probation decision look like a measurement.
        raise ValueError(
            f"LM.residual_ratios: the composed table has {int(table.shape[0])} row(s), the "
            f"residual table {int(delta.shape[0])} and LM_VOCAB_SLOTS is {slots}. This vector is "
            f"indexed by token id by its consumer, so a width that is not the vocabulary's is a "
            f"vector whose rows mean something other than what TOK will read them as.")
    with torch.no_grad():
        # A PURE READ: no grad, no side effect, no mutation of the composer. It is called on the
        # probation cadence from a judgement path, and an instrument that leaves a graph behind on
        # a path nobody backwards through is a leak with no symptom.
        composite = table - delta
        # ||delta[t]|| / ||composite[t]||, RECOMPUTED AT JUDGEMENT TIME AND NOT READ OFF THE MINT.
        # That is the whole reason this entry point exists (Q-TOK-11): MintReport.residual_ratio is
        # produced at the moment the row is created, when the free residual starts at zero under
        # every new_row_init arm, so the "embed" arm's `residual_ratio[t] >= probation_residual`
        # test failed for every candidate and retired 100% of them -- an arm wrong BY CONSTRUCTION
        # rather than by tuning.
        ratios = delta.norm(dim=-1) / composite.norm(dim=-1).clamp_min(1e-12)
        # LIVE ROWS ARE THE MINTED ONES, and the count is the reading that separates "the
        # vocabulary has no composed rows yet" (0 with a non-None return) from "compose is off"
        # (None). born is -1e9 for an id that was never minted, the same mask anchor_term applies.
        _set("lm.residual_rows", int((born > -10 ** 8).sum()))
        _bump("lm.residual_read")
        return ratios.detach().to(torch.float32)


@dataclasses.dataclass(frozen=True)
class MintReport:
    """What ONE mint event did to this package's tensors. FIELDS ONLY, NO METHODS, for LoadReport's
    reason: a public method on a public class in an api.py IS an entry point (K1/K6), and
    `Caps.headroom` was the 133rd the day it landed.

    `rows_initialised` IS ROWS AND `arm_used` IS WHICH RULE WROTE THEM, and the pair is why this is
    a record rather than an int. lm/levers.py::LMLevers.new_row_init records the three arms as a measured
    experiment -- immediate post-mint loss over 6 pairs x 3 seeds, random 2.1699 (sd 0.120), mean
    1.8222 (sd 0.078), last/first 1.4822 (sd 0.011) -- so a report that says how many rows were
    written without saying under which rule cannot be compared against that table.
    `rows_initialised` IS 0 ON THE "random" ARM AND THAT IS NOT AN OMISSION: the arm's whole content
    is leaving the constructor's initialisation in place, so nothing is written and the honest count
    of rows this call wrote is zero. `arm_used` is what says the arm ran.

    `residual_ratio` IS THE MINT-TIME READ AND IS NOT THE PROBATION TEST'S INPUT (Q-TOK-11, ruled
    2026-09-02). It is ||delta|| / ||composite|| at the moment the row is CREATED, when the free
    residual is zero by construction under every arm -- so TOK's `embed` arm sourcing it from here
    would retire 100% of candidates, an arm wrong BY CONSTRUCTION rather than by tuning. The number
    the probation test wants is LM.residual_ratios(lm, model), read at judgement time. This field
    is still the right number FOR THE MINT and is kept for that; it is None off the compose arm,
    where there is no composite to be a residual from.
    """
    rows_initialised: int = 0
    arm_used: str = ""
    sig_rows_written: int = 0
    composer_rows: int = 0
    residual_ratio: object = None


@dataclasses.dataclass(frozen=True)
class LoadReport:
    """What a resume DID to the saved tensors, or why it would not.

    FIELDS ONLY, NO METHODS, and that is deliberate rather than minimal: a public method on a
    public class in an api.py IS an entry point -- tests/test_contract.py's K1 and K6 both say so,
    and `Caps.headroom` was the 133rd the day it landed. A record that answers with its fields
    costs the contract nothing.

    `refused` and `reason` TRAVEL TOGETHER because a refusal that cannot be read is a traceback.
    The counters are ints (counters() is declared {name: int}), so the SENTENCE has to live here --
    `lm.ckpt.refused` says one happened and this says which knob and both numbers.
    """
    widened: int
    refused: bool
    reason: str


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
    out = {
        "module": model.state_dict(),
        # THE RESOLVED GEOMETRY, FIELD BY FIELD, so a resume can refuse a mismatch BY KNOB NAME.
        # The old checkpoint recorded model_type and layers at :5340 and nothing about maxlen,
        # heads, compose or max_token_bytes, so a mismatch surfaced as "it can be failing on
        # FAB_EMB_HID, SIG_D or D_MODEL and no prefix of it means anything". Stored as a plain dict
        # rather than the dataclass: a payload crosses processes, and unpickling a record type that
        # has since gained a field is how a resume dies reading its own provenance.
        "geometry": dataclasses.asdict(geom),
        "counters": dict(_COUNTS),
    }
    # THE COMPOSER'S `born` TENSOR IF THERE IS ONE, AND A DECLARED ABSENCE IF THERE IS NOT.
    # Without it a resume releases every token's anchor immediately or holds every token forever,
    # because anchor_term masks on `born`. It is read with getattr because THE COMPOSER IS NOT
    # BUILT IN THIS TREE YET: model.composed_table() raises NotBuilt, and LM.on_mint -- which has
    # a body since 2026-09-21, where this line called it a stub -- raises NotBuilt at LM_COMPOSE=1
    # because step 1 of it IS the composer's set_vocab/note_born. So under compose there is still
    # no composer and therefore no born; what changed is which file the absence is in. Saving `None` and saying so
    # beats omitting the key -- a missing key on load is indistinguishable from an old checkpoint,
    # and this one has to be distinguishable, because a resume that silently finds no born is a
    # resume that silently releases every anchor.
    born = getattr(model, "born", None)
    out["born"] = None if born is None else born.detach().cpu().clone()
    out["born_unbuilt_reason"] = None if born is not None else (
        "the ByteComposer is not built in this tree (LM.composed_table raises NotBuilt, and "
        "LM.on_mint has a body but raises NotBuilt at LM_COMPOSE=1 because its step 1 IS the "
        "composer), so no token has a birth step to anchor against")
    # NOT IN IT: the composer's derived byte-index tensors (_idx/_msk/_len/_v) and the dead-row
    # mask cache. Both are REBUILT on load, so a resume with a re-segmented vocabulary cannot come
    # back with a stale table -- which is the point, and is why they are named here rather than
    # simply absent.
    _bump("lm.ckpt.saved")
    return out


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
                 (with the reason string, so a refusal is a Reading and not a traceback). On a
                 load that is not refused, the parent's whole ledger (state_dict's "counters")
                 comes back first, except lm.resolve.* and lm.build.*, which are this process's
                 own.
    """
    lm = lm.owned_by("LM")

    def _refuse(reason):
        # A REFUSAL IS A READING, NOT A TRACEBACK. The count says one happened; the sentence says
        # which knob and both numbers, because "it can be failing on FAB_EMB_HID, SIG_D or D_MODEL"
        # is the report this package exists to stop printing.
        _bump("lm.ckpt.refused")
        return LoadReport(widened=0, refused=True, reason=reason)

    saved_geom = saved.get("geometry") or {}
    # EVERY GEOMETRY FIELD THAT MAY NOT MOVE, CHECKED BY NAME AND REPORTED WITH BOTH NUMBERS.
    # `compose` is in this list and is refused IN BOTH DIRECTIONS: under compose emb/head are not
    # constructed at all, so the two arms are not resume-compatible either way, and a resume across
    # the flip would index a trained head by a vocabulary that means something different.
    # THE NAME IS THE KNOB AN OPERATOR CAN MOVE, not the field's name upper-cased. Two of these are
    # WIRES and not levers: max_token_bytes is LM.d_max_token_bytes, wired from TOK_MAX_BYTES, and
    # pos_max is LM.d_pos_max, wired from LM_CTX -- so "LM_MAX_TOKEN_BYTES" named an environment
    # variable that does not exist (driven 2026-09-24: a TOK_MAX_BYTES=12 child of a parent written
    # at 16 was refused as LM_MAX_TOKEN_BYTES, the first time this refusal ever reached a reader).
    knob = {"max_token_bytes": "TOK_MAX_BYTES (LM.d_max_token_bytes)",
            "pos_max": "LM_CTX (LM.d_pos_max)"}
    for field in ("arch", "width", "layers", "heads", "ctx", "pos_max", "compose",
                  "max_token_bytes"):
        if field in saved_geom and saved_geom[field] != getattr(geom, field):
            return _refuse(
                f"{knob.get(field, 'LM_' + field.upper())}: the checkpoint was written at "
                f"{saved_geom[field]!r} and this "
                f"run resolves {getattr(geom, field)!r}. The tensors do not fit and no prefix of "
                f"them means anything. Resume with the saved value, or start a new run.")
    saved_slots = int(saved_geom.get("vocab_slots", geom.vocab_slots))
    live_slots = int(geom.vocab_slots)
    if saved_slots > live_slots:
        # THE d_vocab_ceiling CONSEQUENCE, AND IT SAYS WHICH FILE TO OPEN. A tokenizer file
        # carrying its own larger vmax is the ZERO-mint failure at :1231-1241: the vocabulary is
        # full on arrival, nothing can be minted, and a new area is segmented entirely with the
        # previous one's merges.
        return _refuse(
            f"LM_VOCAB_SLOTS: the checkpoint has {saved_slots} rows and this run resolves "
            f"{live_slots}. NARROWING IS REFUSED -- slot i must stay slot i, and dropping rows "
            f"would silently retire trained tokens. If the larger number came from a tokenizer "
            f"file rather than from LM_VOCAB_SLOTS, that file is the one to look at.")

    module = saved.get("module") or {}
    live = model.state_dict()
    missing = [k for k in live if k not in module]
    if missing:
        # strict=True ON THE MODULE IS WHAT MADE EVERY EXISTING CHECKPOINT UNRESUMABLE the day one
        # parameter was added to the LM (P1-M49), with a raw torch error and no name in it. This is
        # the same refusal with the names in it.
        return _refuse(
            f"the checkpoint is missing {len(missing)} tensor(s) the live model has, first "
            f"{missing[:3]}. That is a model this checkpoint was not written from.")

    # WIDENS ON vocab_slots ONLY, AND BY PREFIX. Slot i is still slot i and token id i is still
    # token id i (:846-877). A resume that cannot widen the softmax cannot add capacity for the
    # area it is adding: the run that motivated this had the vocabulary full at 2048/2048, so a new
    # language got ZERO tokens of its own.
    widened = 0
    fitted = {}
    for k, want in live.items():
        got = module[k]
        if tuple(got.shape) == tuple(want.shape):
            fitted[k] = got
            continue
        if (got.dim() == want.dim() and got.shape[0] == saved_slots
                and want.shape[0] == live_slots and live_slots > saved_slots
                and tuple(got.shape[1:]) == tuple(want.shape[1:])):
            grown = want.clone()
            grown[:saved_slots] = got            # THE PREFIX. Everything above it keeps its init.
            fitted[k] = grown
            widened += 1
            continue
        return _refuse(
            f"tensor {k!r} is {tuple(got.shape)} in the checkpoint and {tuple(want.shape)} live, "
            f"and the difference is not a vocabulary widening ({saved_slots} -> {live_slots}). "
            f"Only the leading vocabulary dimension may grow.")
    model.load_state_dict(fitted, strict=True)

    born = saved.get("born")
    if born is not None and hasattr(model, "born"):
        n = min(int(born.shape[0]), int(model.born.shape[0]))
        model.born[:n] = born[:n].to(model.born.device)
    # THE DERIVED TABLES ARE DROPPED ON PURPOSE, which is the other half of what state_dict does
    # not save: a resume with a re-segmented vocabulary must not come back with a stale byte-index
    # table or a stale dead-row mask.
    model._dead_mask_cache = None

    # THE COUNTERS COME BACK, WHICH state_dict ALWAYS WROTE AND NOTHING READ. `"counters":
    # dict(_COUNTS)` has been in the payload since state_dict was written, and until 2026-09-24 this
    # function never looked at it, so every LM tally restarted at the resume boundary -- driven on a
    # 160-window parent: lm.embed.calls 160, lm.encode.calls 485, lm.anchor.unreachable 160 and
    # lm.ckpt.saved 3 in the blob, and none of them in the child. The same repair MEM's open_store
    # and OPT.load_state carry, and with the same exception: lm.resolve.* describes THIS process's
    # geometry resolution, which has already run and must not be overwritten by the parent's.
    # Restored BEFORE the two bumps below so this process's load is counted on top of any the
    # parent's ledger carried, the way opt.ckpt.loaded accumulates.
    # lm.build.* IS EXCLUDED FOR THE SAME REASON (2026-09-24): build_model has already run in this
    # process and its five gauges describe the model THIS process built.
    for key, value in dict(saved.get("counters") or {}).items():
        if not str(key).startswith(("lm.resolve.", "lm.build.")):
            _COUNTS[key] = value

    _bump("lm.ckpt.loaded")
    _bump("lm.ckpt.rows_widened", widened)
    return LoadReport(widened=widened, refused=False,
                      reason=(f"{widened} tensor(s) widened by prefix, {saved_slots} -> "
                              f"{live_slots} rows" if widened else "fitted exactly, nothing widened"))



def _three_state(gates, ledger):
    """{name: (state, count, arithmetic)} for every DECLARED gate, in G4's three states.

    RENDERED FROM THE Gate OBJECTS THE PACKAGE ALREADY CARRIES, never from a second inspection of
    the levers. spine/gate.py::Gate is where `fired`, `reachable`, `value`, `threshold` and
    `reason` were decided, at build, with the numbers that made them true or false; recomputing any
    of that here would give this package two answers to "did it fire" and let the report quote
    whichever it reached first. That is the defect the Gate record was introduced to end.

    THE THIRD STATE IS THE ONE THAT COSTS, which is Gate's own sentence. `fired=False,
    reachable=True` is a MEASUREMENT -- the mechanism ran and its condition was not met.
    `reachable=False` is not a measurement at all, and a report that prints them the same way says
    "0" for both. The count comes from the ledger when the ledger has a key of that name, so a
    gate that fired N times says N rather than merely "fired".
    """
    # BOTH CONTAINERS, BECAUSE THE TREE USES BOTH. SIG carries `gates` as a dict {name: Gate}
    # while FAB, MEM and CAP carry a tuple of Gate. Neither is wrong and this is not the place to
    # unify them -- a renderer that accepted only one would silently report zero gates for the
    # packages using the other, which is the "0 fires nobody can read" state in the very function
    # written to prevent it. Measured 2026-09-15: sig.gates is a dict of 2, fabric.gates a tuple
    # of 2, store.gates a tuple of 1, valve.gates a tuple of 3.
    if isinstance(gates, dict):
        gates = tuple(gates.values())
    out = {}
    for g in (gates or ()):
        n = int(ledger.get(g.name, ledger.get(g.name + ".count", 0)) or 0)
        arith = f"{g.value!r} vs {g.threshold!r}"
        if not g.reachable:
            out[g.name] = ("unreachable", n, f"{arith} -- {g.reason}")
        elif g.fired:
            out[g.name] = ("fired", n, arith)
        else:
            # ARMED AND IT DID NOT HAPPEN. The reason rides along when the gate carried one,
            # because "armed but 0" with the arithmetic beside it is what lets a reader tell a
            # threshold that was nearly met from one that was never approached.
            out[g.name] = ("armed-but-zero", n, arith + (f" -- {g.reason}" if g.reason else ""))
    return out


def counters(lm: Config, model):
    """The DID IT FIRE ledger for this package: {name: int}, plus the few float gauges a body
    declares as such (lm.encode.extra_ratio / extra_ratio_max). No torch, no side effects.

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
    # NO TORCH AND NO SIDE EFFECTS, which the docstring requires and which is why this reads the
    # process tally and the model's declared gates rather than touching a tensor. A DID IT FIRE
    # surface that allocates is one nobody can call from a report path.
    out = dict(_COUNTS)
    gates = getattr(model, "gates", None)
    out.update({f"gate:{k}": v for k, v in _three_state(gates or (), _COUNTS).items()})
    if not gates:
        # NO Gate OBJECTS ON THIS MODEL, AND THE DOCSTRING ABOVE ASSUMES THERE ARE SOME. It says
        # "Every gated mechanism above appears here in the three-state form G4 requires", and LM
        # really does have gated arms -- mask_dead_rows, compose, the anchor, new_row_init.
        # BUILD_MODEL NOW DECLARES TWO OF THEM (lm.anchor.unreachable and lm.residual_unreachable,
        # 2026-09-17, with the two bodies that read those arms), so a model this package built
        # never takes this branch: measured, `getattr(model, "gates", None)` is a tuple of 2 on a
        # freshly built model and was None before that edit. What still takes it is a model from a
        # source that is not build_model -- a stand-in in a test, an object rebuilt from a
        # checkpoint by hand -- and the remaining arms (mask_dead_rows, new_row_init) are still
        # decided inline and declare no Gate at all.
        # REPORTED RATHER THAN LEFT AS SILENCE, because a ledger with no gate rows in it looks
        # exactly like a package whose gates all read zero -- which is the two-states-printed-as-one
        # collapse G4 exists to refuse, arriving inside the surface built to prevent it. The
        # obligation on the two arms that remain is unchanged: declare the Gate where the arm is
        # decided, at build, with the numbers that made it true or false.
        out["gate:lm.none_declared"] = (
            "unreachable", 0,
            "this model carries no Gate objects, so it has no three-state surface -- "
            "LM.build_model declares the anchor and residual gates, and a model that has none "
            "did not come from it; the arms decided inline (mask_dead_rows, new_row_init) declare "
            "none either way and report only through the tallies above")
    return out
