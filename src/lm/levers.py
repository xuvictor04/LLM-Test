"""LM -- the base language model: which network is built, how big it is, and what a new symbol costs it.

WHAT THIS PACKAGE OWNS. One network that maps a window of token ids to a distribution over the next one,
and every number that sets its SHAPE: which arm is built (a GRU or a transformer), how wide, how deep,
how many attention heads, how many context positions it is trained over, how many rows the softmax has,
and what happens to those rows when the tokenizer mints a new symbol into them. It owns no data, no
cadence, no optimizer setting and no instrument. Four of its twelve levers arrived here from three other
families in the old tree -- `tokenizer`, `data`, `optim` and `plumbing` -- and that is the whole point of
the census: the old file filed a knob by the subsystem whose NAME it wore, and this package is filed by
the tensors the knob actually sizes.

WHY THESE ARE THE LEVERS, against the two goals and nothing else.

  GOAL A IS LANGUAGE PRODUCTION, and the width is the root of the shape graph: memory keys, fabric expert
  bodies, the signature encoder and the world-model projection are all keyed off `width`, which is why
  self_organize.py:4678-4684 records that a checkpoint shape mismatch "can be failing on FAB_EMB_HID,
  SIG_D or D_MODEL and no prefix of it means anything". One owner holds it; everybody else receives it.
  The second largest number in the same family is `vocab_slots`: the census calls it the largest single
  quality lever in the whole record (0.141-0.205 b/B), and it is the one number that had two live values
  in one process -- the tokenizer targeted 4096 while ByteComposer sized its per-token tables from a
  SECOND os.environ read defaulting to 2048, so an unset VMAX indexed past the end of delta/dbias
  (registry note, self_organize.py:69-70, :1455-1456).

  "ROOM FOR ADDITIONAL MODALITIES" IS ALSO ARITHMETIC HERE, NOT ASPIRATION. A modality is a different
  alphabet. It needs rows in the embedding and the head before it needs anything else, and it needs them
  to arrive without a discontinuity -- which is exactly what `compose`, `anchor_w`, `anchor_uses` and
  `new_row_init` are for. Those four are the handover mechanism for a symbol that did not exist when
  training started, and PLAN section 3 item 7 protects two of them by name ("ByteComposer and the anchor
  stay").

  GOAL B IS CONTINUAL LEARNING WITHOUT CATASTROPHIC FORGETTING, and this package's own version of that
  failure is a row-level one: a freshly minted token id points at a randomly initialised embedding row
  and a randomly initialised head row, so the model must re-learn from scratch material it can already
  spell with the parents. The three measured arms of `new_row_init` are exactly that experiment --
  immediate post-mint loss over 6 pairs x 3 seeds = 18 trials, random 2.1699 (sd 0.120), mean 1.8222
  (sd 0.078), last/first 1.4822 (sd 0.011) (:7663-7673) -- and `mask_dead_rows` is the other end of it:
  rows nobody has minted yet must not take probability mass from rows somebody has.

CENSUS ACCOUNTING (.rework/census.json, filtered on new_owner == "LM"): 17 rows.
    10 rename + 2 keep             -> 12 levers declared below
     2 merge                       -> both fold into levers declared here: WARMSTART into `new_row_init`
                                      (the "random" value), D_MODEL_B into `width`
     2 drop                        -> not declared (TOK_ANCHOR_TAU, WARMSTART_OPT)
     1 promote-to-wire             -> not declared (MAXLEN -> d_pos_max); see THE WIRES below
   12 levers in total, from 17 rows. CENSUS.md:37 says "LM 17" because it counts ROWS assigned to this
   package, not declarations that survive them, and for a package with two merges and two drops in it
   those are different numbers. The five that do not become declarations are listed above rather than
   subtracted silently, because a reader who counts twelve against a table that says seventeen otherwise
   has to re-derive which five went where.

FOUR ROWS THAT LOOK LIKE ANOTHER PACKAGE'S AND ARE THIS ONE'S, listed because their OLD names all wear
somebody else's prefix and a reader will go looking in the wrong file:
    VMAX, TOK_COMPOSE, TOK_ANCHOR, TOK_ANCHOR_USES  (family `tokenizer`)  -> vocab_slots, compose,
                                                       anchor_w, anchor_uses. All four are model geometry
                                                       or model loss terms; the tokenizer never touches
                                                       the tensors they size. src/tok/levers.py records
                                                       the same four as deliberately absent from TOK.
    WIN                             (family `data`)   -> ctx. The stream is sliced by it, which is why it
                                                       was filed under data; it is the model's context
                                                       width, and DATA owns no window lever at all.
    DROPOUT                         (family `optim`)  -> dropout. Not an optimizer setting: it is a layer
                                                       in the model, constructed at :1550-1551.
    LOSS_MASK_DEAD              (family `tokenizer`)  -> mask_dead_rows. PLAN section 1's own example of
                                                       a tag drifting from an owner: tagged "# tokenizer"
                                                       while sitting inside the "--- domains ---" block
                                                       (:251), and its only reader is a logits mask.

THREE CENSUS DEFECTS REPAIRED WHILE READING IT. All three were checked against this package's 17 rows;
one was present in bulk, one required no change and the reason it required none is recorded, and one was
absent. The negatives are written down because "nothing to fix here" is only useful if a reader can see
that it was looked for rather than skipped.

  DEFECT 1 -- DOUBLED ENV NAMES. FOURTEEN of this package's rows name their target as PREFIX.PREFIX_FIELD
  -- `LM.LM_VOCAB_SLOTS`, `LM.LM_WIDTH`, `LM.LM_ARCH` and so on (CENSUS.md:305, 307, 313, 314, 315, 323,
  324, 344, 402, 412, 413, 414, 417, 418). lever.py:104-106 generates the environment name as
  PREFIX + "_" + FIELD.upper(), so `LM.LM_WIDTH` taken literally declares a field `LM_WIDTH` answering to
  LM_LM_WIDTH: a name no operator would ever type, that from_env() would never find, and that therefore
  leaves the lever pinned at its default forever while every static check reports it declared, owned and
  resolved. That is the silent-default class this rebuild exists to end, arriving through the document
  that is supposed to end it. The prefix is stripped from the FIELD in every case and THE ENV NAME IS
  UNCHANGED from what the census intended -- that invariance is the point of the correction, not a side
  effect of it. Twelve corrections landed on declarations: LM_VOCAB_SLOTS, LM_COMPOSE, LM_ANCHOR_W,
  LM_ANCHOR_USES, LM_NEW_ROW_INIT, LM_MASK_DEAD_ROWS, LM_CTX, LM_DROPOUT, LM_WIDTH, LM_HEADS, LM_LAYERS,
  LM_ARCH. The other two doubled rows are the merges -- WARMSTART -> `LM.LM_NEW_ROW_INIT` and D_MODEL_B
  -> `LM.LM_WIDTH` -- whose targets are fields already corrected above, so they mint nothing new. Fourteen
  doubled rows seen, twelve corrections landed. The remaining three rows carry no field at all: the two
  drops write `LM.` with an empty name, and the promote-to-wire writes `LM.d_pos_max`, which is correctly
  spelled because a wire is not prefixed.

  DEFECT 2 -- CLOCK KINDS. NO CORRECTION WAS NEEDED HERE AND THE REASON IS WORTH STATING, because "no
  clock levers" is a claim about this package that a later reader can check. Not one of the twelve levers
  is a cadence, a deadline or a horizon: every one is a SHAPE (arch, width, layers, heads, ctx,
  vocab_slots), a WEIGHT (anchor_w, dropout), a SWITCH (compose, mask_dead_rows), a NAMED ARM
  (new_row_init) or a per-token counter (anchor_uses). Nothing in this file is ever compared against
  `step`, and `step` is the thing whose kind the survey's 32 unit records are about (it advances once per
  WINDOW, :7708 `i += WIN; step += 1`, while the loop body runs once per FLUSH, :934). Two boundary cases
  were examined rather than waved through:
    * `ctx` is typed TOKENS and that is metadata, not a clock. It is a WIDTH -- how many positions are in
      one window -- and it is what MAKES `step` a window counter; it is never itself compared against
      one. Its real unit hazard is the other one the census names: it was spent as a BYTE length in three
      places (ISSUES:170, ISSUES:413, and _sigwidth()'s reconstruction of max(WIN, WIN*bpt)), which is a
      metadata mismatch that U.TOKENS makes visible and that the named conversion
      spine.derive.signature_width_bytes fixes at the one place it is used.
    * `anchor_uses` counts APPEARANCES of one token in trained-on material -- `_tok_seen` at :6307, which
      advances only when the token turns up in a training batch. That is a clock in every sense except
      that units.py has no kind for it: Steps, Flushes, Windows, Backwards, Epochs and Selections are the
      six that exist, Selections counts expert choices and none of the others counts token appearances.
      It is declared U.COUNT, which is what the census types it, and adding an Appearances kind is a
      SPINE edit that this file has no standing to make. The mismatch it exists to prevent is already
      prevented by subtraction: TOK_ANCHOR_TAU, the rival horizon typed in the census as Windows, is
      DROPPED, so there is no second unit for one quantity left to compare against.
  One row here IS clock-typed and it is the dropped one. TOK_ANCHOR_TAU is typed `Windows` in the census
  (CENSUS.md:297) while the source it quotes calls it steps -- the census applied the correction as it
  dropped the row, which is the right kind for a threshold compared against `step`, and it changes
  nothing here because a dropped row declares no lever.

  DEFECT 3 -- NO UNRESOLVED MERGE, AND IT WAS CHECKED. Both merges name a target that has a row of its
  own in the same census: WARMSTART -> LM_NEW_ROW_INIT is WARMSTART_MODE's row (verdict rename,
  CENSUS.md:324), and D_MODEL_B -> LM_WIDTH is D_MODEL's row (verdict rename, CENSUS.md:417). Nothing was
  invented, nothing is left standing on its own, and no lever below exists only because a merge pointed
  at it.

TWO CONFLICTS WITH THE SPINE, STATED RATHER THAN RESOLVED. Picking a side inside a declaration file is
how a knob acquires two meanings, so both are recorded here and neither is decided here.

  (a) OWNERSHIP OF THE SOFTMAX WIDTH. spine/assemble.py:722-724 declares
  `Coupling(src="TOK.vmax", dst="LM.d_softmax_width", compute=lambda r: int(r["TOK"].vmax))` -- it reads
  `vmax` off TOK's Config and hands the result to THIS package as a wire. The census says the opposite:
  VMAX is LM's (verdict rename -> LM_VOCAB_SLOTS, CENSUS.md:323) and "TOK receives it as the wire
  d_vocab_ceiling". src/tok/levers.py follows the census and does not declare `vmax`; this file follows
  the census and declares `vocab_slots` below. The consequence is a startup failure, not a silent one,
  and it is reproduced rather than predicted -- importing the seven packages and calling
  `assemble.build({})` today raises "TOKLevers has no lever 'vmax'. Declared: [...]. If this belongs to
  another package, it must arrive as a wire, not a read." That failure predates this file (TOK's
  declaration is what removed `vmax`), and it is the mechanism working: the read site names a lever
  nobody owns and startup stops. The repair is one edit in assemble.py -- reverse the edge to
  src="LM.vocab_slots", dst="TOK.d_vocab_ceiling" -- and it is assemble's, because the coupling's `why`
  argues for LM's side ("emb.weight and head.weight have exactly this many rows... this is one number
  named twice, not two numbers that happen to agree"). Declaring `vmax` here as well to keep assemble
  quiet would put the softmax width in two packages at once, which is the exact failure the ownership
  spine exists to prevent.

  (b) WHERE d_pos_max COMES FROM. MAXLEN is promote-to-wire (CENSUS.md:415) and its reason says the value
  "arrives d_-prefixed from DATA's window lever". DATA HAS NO WINDOW LEVER: WIN's own row moves the window
  to LM as LM_CTX (CENSUS.md:344), and no row in the whole census gives DATA a width. So the wire's source
  is this package's own `ctx`, which makes it a LOCAL coupling in assemble's sense -- one owner, no edge,
  no budget, still d_-prefixed -- rather than the cross-package wire the row describes. It is not declared
  here either way, because lever.py:83-87 refuses a d_-named lever precisely so a declaration cannot
  shadow the wire that writes it. What must not happen is that nobody writes it: at :1586 the transformer
  arm does `p = torch.arange(L).clamp(max=s.maxlen - 1)`, so a context wider than the positional table
  silently gives every position past the end ONE shared embedding -- no error, no report line, a model
  that cannot tell those positions apart. That clamp is why this quantity is a wire and not a free
  literal, and until the coupling exists the guarantee it buys does not.

THE WIRES: values this package uses or supplies that it must NOT declare. Written down because `grep d_`
is only complete in both directions if the receiving end says what it expects (O4 audits exactly this).
    INCOMING
      d_pos_max            positional rows, from this package's own `ctx`     (census promote-to-wire;
                                                                               NOT YET IN THE LEDGER)
      d_softmax_width      ENTRIES, from TOK.vmax                             (assemble.py:722, and see
                                                                               conflict (a) -- under the
                                                                               census this edge reverses)
      d_live_vocab         how many rows have actually been minted            (LOSS_MASK_DEAD's row;
      d_retired_ids        which minted rows were retired on probation         both NOT YET IN THE LEDGER)
      d_max_token_bytes    longest token in bytes, from TOK.max_bytes         (MAX_TOK's row, CENSUS.md:308;
                                                                               ByteComposer hardcodes
                                                                               maxb=16 today and does NOT
                                                                               follow the tokenizer, so a
                                                                               longer token is silently
                                                                               truncated to its first 16
                                                                               bytes. NOT IN THE LEDGER)
      d_device             cpu/cuda, from RUN                                 (DEVICE's row, CENSUS.md:416)
    OUTGOING
      d_vocab_ceiling      to TOK, from `vocab_slots`                         (VMAX's row; see (a))
      d_residual_ratio     to TOK, ||delta||/||composite|| from the composer   (TOK_PROBATION_MIN's row;
                                                                               TOK's probation "embed" arm
                                                                               has nothing to compare
                                                                               without it. NOT IN THE
                                                                               LEDGER)
      the new-row init also writes enc.emb -- SIG's tensor -- which must become a declared wire to SIG
      rather than the inline reach at :7702-7705.
Six of those nine are not in spine/assemble.COUPLINGS today. That is not this file's to fix, but a
missing wire that nobody has written down becomes a direct reach the first time somebody needs the value.

IMPORT STYLE. Absolute, `from spine.lever import ...`, matching fabric, sig, memory, domains, eval and
tok. Every entry point puts src/ itself on sys.path (tests/test_derive.py:33, tests/test_ownership.py's
SRC insert, and this file's own verification command), which makes `lm` a TOP-LEVEL package; a relative
`from ..spine.lever import ...` is then an ImportError ("attempted relative import beyond top-level
package"), not a fallback. Seven packages spelling one import one way is worth more than matching a
sketch.
"""
from spine.lever import Lever, LeverSet
from spine import units as U


class LMLevers(LeverSet):
    """The base language model's declared knobs: which network, how big, and what a new symbol costs.

    Read `cfg.width`, never an environment name. Every value here is resolved once by spine.assemble and
    frozen; a function receiving this Config should open with `lm.owned_by("LM")`, because a Config is an
    ordinary object and a foreign one handed in reads happily and wrongly -- `memory_prune(configs["FAB"])`
    returning 2048 is the reproduced case behind that method's existence.

    Grouped by the decision each group makes rather than alphabetically. The grouping is load-bearing for
    one of them: `arch` silently decides whether `heads` is read at all, whether `layers` means 4 or 1,
    and whether `compose` does anything -- and in the old tree those three facts were spread across
    :1598-1600, :89 and :1549 with nothing anywhere saying they were one decision.
    """

    PREFIX = "LM"

    # ==============================================================================================
    # 1. WHICH NETWORK IS BUILT, AND HOW BIG
    #
    # Five numbers and one name that fix every tensor shape in the run. They are declared first because
    # they are the root of the shape graph: :4678-4684 records a checkpoint load failing on a shape
    # mismatch where "it can be failing on FAB_EMB_HID, SIG_D or D_MODEL and no prefix of it means
    # anything", which is what a width owned by nobody costs at the moment it goes wrong.
    # ==============================================================================================

    arch = Lever("gru", "Which base language model is constructed: the GRU (MiniLM) or the transformer "
                        "(TinyTransformer).",
                 U.NAME, choices=("gru", "transformer"))
    # Census: MODEL -> LM_ARCH, verdict rename, default "gru". Field corrected from `LM_ARCH` to `arch`
    # (DEFECT 1); the env name is LM_ARCH either way, which is what the census meant.
    # THE RENAME IS NOT COSMETIC. `MODEL` is the most overloaded token in the old tree -- MODEL the arm
    # selector (:1416), WORLD_MODEL the world-model flag (:358), `model_type` in the checkpoint (:5340)
    # and `model` the live nn.Module, all in the same scopes -- and the config audit had to list MODEL by
    # hand in a `_plumb` allowlist at :5761-5762 to stop the typo net firing on its own knob. A name that
    # needs an allowlist entry to survive the audit that protects it is the wrong name.
    # choices= IS THE REPAIR, AND THIS IS ONE OF THE ELEVEN. ISSUES.md M24 (:361) names MODEL in the list
    # of knobs where "an unrecognised value falls into whichever branch is the else, rather than being
    # refused": build_lm is `if MODEL_TYPE == "transformer": TinyTransformer(...)` and everything else
    # returns MiniLM (:1598-1600), so MODEL=Transformer, MODEL=xformer and MODEL=grru all silently train
    # a GRU while the banner prints the string the operator typed. With choices= that is a startup
    # LeverError naming both legal values, before a single tensor is allocated.
    # IT GATES THREE OTHER LEVERS AND THAT MUST BE PRINTED, NOT INFERRED. `heads` is read only on the
    # transformer arm; `layers` means 4 there and 1 here; and `compose` is a no-op there because
    # TinyTransformer has no compose attribute at all and forwards through s.head unconditionally
    # (ISSUES.md M22, :351-353) while the coupling banner at :6038 prints a sentence describing a
    # mechanism that model does not have. Under G4 each of those is a declared Gate that prints its own
    # predicate; "set but inert" and "not set" are two different statements and the old tree made both
    # look like silence.

    width = Lever(128, "Hidden width of the base LM, and through it the width of every representation "
                       "keyed off it -- memory keys, expert bodies, the world-model projection.",
                  U.COUNT)
    # Census: D_MODEL -> LM_WIDTH, verdict rename, ABSORBING the D_MODEL_B row (verdict merge,
    # CENSUS.md:414). Field corrected from `LM_WIDTH` to `width` (DEFECT 1).
    # THE OLD DEFAULT READS AS COMPUTED AND IS NOT A WIRE. The census records it as "None (computed:
    # D_MODEL_B, i.e. 128)" and the source is `D = _i("D_MODEL", _i("D_MODEL_B", 128))` at :534. That
    # inner read is not a derivation from another QUANTITY -- it is an ALIAS, a second spelling of this
    # same number, and the census merges it in rather than wiring it. So the literal is 128, which is
    # what every run in the record actually used, and there is nothing here for spine.assemble to compute.
    # (Contrast `layers` below, whose old default really is a function of another lever.)
    # THE ALIAS COST TWO DOCUMENTED RUNS AND IT DIES WITH THE MERGE. (1) Before :534 accepted the second
    # name, nothing in self_organize.py read D_MODEL_B at all, so `D_MODEL_B=768 python3 self_organize.py`
    # silently ran at d=128 -- it mis-sized every direct-invocation run including the GPU bench, which
    # reported 4.3M/5.1M parameters instead of the intended 28.7M/53.9M, and including the pilot command
    # handed to the owner (ISSUES.md:2003). (2) The fix introduced the mirror image, ISSUES.md L26 at
    # :842-844: the nested `_i` reads D_MODEL_B EAGERLY and then discards it whenever D_MODEL is set,
    # while both land in _ENV_ASKED and _ENV_READ -- so the audit reported both as read and accounted for,
    # only one affected the run, and no OVERRIDE note was printed. Under the spine an alias is
    # structurally impossible: the env name is GENERATED from the field, so one field is one name.
    # Launchers that quote D_MODEL_B get a one-line edit; that is not a reason to keep a second door.
    # WHY THE NAME IS NOT `d_model`. Two reasons, both hard. A field starting with `d_` is a WIRE in this
    # tree and lever.py:83-87 refuses to declare one, so the old spelling is not available at all; and
    # "d_model" is transformer vocabulary applied to a default path that is a GRU, so it names the arm it
    # is not. LM_WIDTH is true on both arms.

    layers = Lever(0, "Depth of the base LM -- transformer blocks or GRU layers; 0 means take the "
                      "current arm's depth (4 for transformer, 1 for gru).", U.COUNT)
    # Census: LAYERS -> LM_LAYERS, verdict keep. Field corrected from `LM_LAYERS` to `layers` (DEFECT 1).
    # THIS DEFAULT REALLY IS COMPUTED FROM ANOTHER KNOB, AND THAT MAKES IT A DERIVATION. The old tree
    # recorded `_DERIVED["LAYERS"] = ("MODEL",)` at :89 with the comment "4 for transformer, 1 for gru",
    # and exempted the knob from its own default-mismatch refusal (:74) to make that legal. L1 does not
    # have that escape: a Lever default must be an ast.Constant, and lever.py:58-61 refuses anything else
    # at declaration time with the reason spelled out ("a value derived from another lever is a WIRE, not
    # a default"). The census's instruction is therefore to make the per-arm depth "a named function in
    # spine.derive keyed off LM_ARCH with the lever's own literal default meaning 'use the arm's'"
    # (CENSUS.md:413), and 0 is that literal. THE LITERALS THE RUNS ACTUALLY USED are 1 (the shipped
    # default, since the shipped arch is gru) and 4 (whenever anyone set LM_ARCH=transformer); both are
    # recorded here so whoever writes the derivation does not have to re-find them.
    # THE FUNCTION DOES NOT EXIST YET AND THAT IS A LIVE HAZARD, NOT A TODO. spine/derive.py has no
    # arm-to-depth function today, so `cfg.layers` reads 0 on a default run, and 0 layers is not a small
    # model, it is a broken constructor. Until `derive.layers_for_arm(arch, layers)` exists, whoever
    # builds the network must resolve the sentinel at the single place it is read, and the resolved value
    # is what goes in the checkpoint and the banner.
    # WHY A SENTINEL AND NOT TWO LEVERS. The same limit domains/levers.py:262 and tok/levers.py record:
    # `choices=` cannot express "0, or any positive int", and inventing a second lever to hold the "use
    # the arm's" state would be minting a knob the census never voted on. The sentinel stands, declared
    # in the help text where an operator will actually see it.
    # WHAT ONE DECLARATION ENDS. The depth was read at two sites with two different arm defaults (:1599
    # and :1600 building the model, :5340 writing the checkpoint), and the notes corpus states LAYERS=4
    # flatly while _SPEC says otherwise (ISSUES.md:637) -- so a reader could not tell what depth a saved
    # model was. DEPTH IS ALSO NOT FREE ELSEWHERE: :1582 records that at LAYERS=12 the memory-key path was
    # paying twelve layers of attention over an 8-token window, thousands of rows per step, which is what
    # made the transformer lose overall despite matching the GRU's LM step time. That is the KEY_LAYERS
    # coupling; it must arrive as a declared wire rather than be rediscovered by whoever profiles next.

    heads = Lever(8, "Attention heads per transformer block; read only when arch is transformer.",
                  U.COUNT)
    # Census: HEADS -> LM_HEADS, verdict keep. Field corrected from `LM_HEADS` to `heads` (DEFECT 1).
    # ARM-CONDITIONAL, WHICH MEANS IT IS SET-BUT-INERT ON THE DEFAULT RUN. It is read at :1599 inside the
    # transformer branch and persisted at :5340; on the gru arm nothing reads it. Under G4 that must show
    # as a declared Gate ("unreachable: lm.arch != transformer") rather than as silence, because
    # armed-but-inert is the single largest class in the survey (57 records) and every one of them looked
    # exactly like a knob that was working.
    # IT CARRIES A HARD CONSTRAINT THIS DECLARATION CANNOT EXPRESS. nn.TransformerEncoderLayer(d, heads,
    # ...) requires width % heads == 0. That holds by luck at the 128/8 defaults and fails on any width an
    # operator picks freely -- and it fails as a torch traceback forty seconds into a run, after the data
    # is loaded. `choices=` cannot state a relation between two levers; only something holding both can,
    # which is spine.assemble. The census asks for the refusal at parse time (CENSUS.md:412) and the
    # honest status is that it is NOT IMPLEMENTED HERE and cannot be: it belongs in a LOCAL coupling over
    # (LM.width, LM.heads) that fails at startup with both numbers in the message.

    ctx = Lever(128, "The model's context width -- how many tokens one training or eval window holds.",
                U.TOKENS)
    # Census: WIN -> LM_CTX, verdict rename. Field corrected from `LM_CTX` to `ctx` (DEFECT 1).
    # NOT A DATA KNOB, AND THE MISFILING IS WHAT MADE IT WRONG. It was filed under `data` because the
    # stream is sliced by it, and that is how it came to be spent as a BYTE length in three places: the
    # signature windows are read as ENC_SEQ[q:q+WIN] with q a TOKEN index into a BYTE stream, so under the
    # default ONLINE + SIG_SPACE=bytes every signature is drawn from the wrong place (ISSUES:170);
    # route_at labels only the first WIN bytes of a ~WIN*bpt-byte span, leaving 46-75% of the span at -1
    # (ISSUES:413); and _sigwidth() has to reconstruct max(WIN, WIN*bytes_per_token) to recover the byte
    # width it needed. The token width is the lever; the byte width is a NAMED derivation --
    # spine.derive.signature_width_bytes -- and it reaches SIG as a d_ wire so the conversion exists once,
    # with a name, instead of three times by hand.
    # ONE DECLARATION ALSO ENDS ISSUES M14. fetch_data.sh tells the operator to set WIN=256 while
    # run_full_unfrozen.sh re-assigns WIN=96 on its own env line, so an operator following the documented
    # command trains at 96 believing 256. Under L1 there is one declaration and the run banner prints the
    # resolved value, so the launcher and the run cannot disagree in silence.
    # IT SIZES THE POSITIONAL TABLE, WHICH IS d_pos_max AND NOT DECLARED HERE. See conflict (b) in the
    # header: raising this past the positional table's height silently collapses every position beyond it
    # onto one shared embedding at :1586.

    dropout = Lever(0.0, "Dropout probability on the token embedding, and between GRU layers when depth "
                         "is greater than one.", U.PROBABILITY)
    # Census: DROPOUT -> LM_DROPOUT, verdict rename, default 0.0. Field corrected from `LM_DROPOUT` to
    # `dropout` (DEFECT 1).
    # MISFILED UNDER optim, AND UNDER L2 THAT WOULD HAVE BEEN A FOREIGN READ. It is not an optimizer
    # setting; it is a layer in the model, read at :1417 and consumed only at :1550-1551 inside the model
    # constructor (`s.drop = nn.Dropout(DROPOUT)`, plus the GRU's inter-layer dropout). This package
    # constructs the network, so an OPT-owned DROPOUT would be a value LM has to reach across a boundary
    # for on every run.
    # DEFAULT 0.0 IS A STATEMENT ABOUT THE CORPUS, NOT ABOUT THE MECHANISM. The model is UNDERFIT at the
    # current corpus size, and the report tells the operator to raise this the moment the held-out gap
    # exceeds ~0.5 (:7990). It is kept rather than dropped precisely because that instruction exists.
    # THE COUPLING DEFECT CARRIES AS A FIXED BUG, NOT AS A KNOB. ISSUES.md:441 records that holdout_bpb's
    # finally block unconditionally returns the model to TRAIN mode, so RETENTION and every later eval
    # section run with dropout LIVE. At 0.0 that is inert, which is why nobody saw it; it becomes a wrong
    # number the instant anyone follows the report's own advice, and the numbers it would corrupt are the
    # forgetting numbers goal B is measured by. Under the instrument line an instrument may not leave the
    # model in a different mode than it found it (G7).
    # SECOND SILENT ZERO, WORTH KNOWING BEFORE SETTING IT: the GRU's inter-layer dropout applies only when
    # depth > 1 (`dropout=(DROPOUT if layers > 1 else 0.0)`, :1550), so on the shipped gru arm at depth 1
    # this knob reaches exactly one place -- the embedding -- and half of what its name suggests is
    # unreachable.

    # ==============================================================================================
    # 2. THE SOFTMAX, AND THE ROWS NOBODY HAS MINTED YET
    #
    # One number sets the height of emb.weight, head.weight and head.bias, and one switch decides
    # whether the rows nobody has minted are allowed to take probability mass. They are a pair: the
    # census says reserved headroom is only honest with the mask on (:686-688), because reserving 8192
    # rows and minting 2048 means 6144 rows sitting in the softmax denominator that index nothing.
    # ==============================================================================================

    vocab_slots = Lever(4096, "How many vocabulary rows the model preallocates -- emb.weight, "
                              "head.weight and head.bias are all this tall, and the tokenizer may not "
                              "mint past it.", U.SLOTS)
    # Census: VMAX -> LM_VOCAB_SLOTS, verdict rename, default 4096, unit slots. Field corrected from
    # `LM_VOCAB_SLOTS` to `vocab_slots` (DEFECT 1). SEE CONFLICT (a) IN THE HEADER: spine/assemble.py
    # still reads this quantity off TOK as `TOK.vmax`, and under the census there is no such lever.
    # REASSIGNED ON THE EVIDENCE, NOT THE TAG. The number is a tensor width -- `V = VMAX` at :1283, the
    # widen_prefix path at :4599-4634, ByteComposer's delta/dbias at :1455-1456 -- and the tokenizer
    # merely must not exceed it. TOK receives it as d_vocab_ceiling.
    # ONE DECLARATION KILLS THE REGISTRY'S OWN WORST-CASE EXAMPLE. self_organize.py:69-70 records that
    # "the tokenizer targeted 4096 while ByteComposer sized its per-token tables to 2048, so an unset
    # VMAX indexed past the end of delta/dbias" -- because :1455-1456 read os.environ a SECOND time with
    # a different literal. Under this spine there is one reader (lever.py:153-164) and one default, so
    # two tables cannot be sized from two answers to one question.
    # THE RESUME FAILURE THIS NUMBER OWNS IS A MISSING WIRE, AND GOAL B IS WHAT IT COST. At :1234-1241:
    # VMAX was doubled 2048 -> 4096 and emb/head were widened to match, but the saved tokenizer's own
    # vmax travelled with the json, so the run reported "ZERO tokenizer.mint 0 ARMED AND INERT" -- a new
    # area got new EXPERTS and could not get a single new TOKEN. Continual learning without the ability
    # to spell the new material is not continual learning, and the missing declaration is what made it
    # look like a tokenizer problem.
    # THE LARGEST SINGLE QUALITY LEVER IN THE RECORD (0.141-0.205 b/B), which is the census's own reason
    # for insisting there be exactly one of it.

    mask_dead_rows = Lever(False, "Take never-minted and retired vocabulary rows out of the distribution "
                                  "wherever logits become one.", U.FLAG)
    # Census: LOSS_MASK_DEAD -> LM_MASK_DEAD_ROWS, verdict rename, default 0. Field corrected from
    # `LM_MASK_DEAD_ROWS` to `mask_dead_rows` (DEFECT 1). Declared False rather than 0 so that
    # LM_MASK_DEAD_ROWS=off means off: Lever.coerce picks its branch from the DEFAULT's type
    # (lever.py:122), and an int default would raise on "off" while the bool default accepts it. The
    # bool branch's own hazard is stated in fabric/levers.py and applies here unchanged -- any string
    # outside ("0","","off","no","none","false") reads as True, so LM_MASK_DEAD_ROWS=flase is silently on.
    # PLAN SECTION 1'S OWN EXAMPLE OF A TAG DRIFTING FROM AN OWNER: tagged "# tokenizer" at :251 while
    # sitting inside the "--- domains ---" block, and its only reader is mask_dead over LOGITS at
    # :3970-3995. Nothing about it is tokenizer work except the two facts it needs, which arrive as wires
    # (d_live_vocab, d_retired_ids).
    # ITS HISTORY IS A PLACEMENT LESSON AND THE MEASUREMENT IS THE ARGUMENT. Masking at the LOSS ONLY is
    # WORSE than not masking at all: on a config with 86.7% of the width never minted, unmasked scored
    # 4.746 and masked-at-the-loss-only 6.100, because the model is never taught to push the dead rows
    # down and every eval path then scores it with those untrained rows still in the denominator. The
    # mask belongs wherever logits become a distribution, and under the instrument line the training and
    # eval paths share one logits path, so that particular split cannot recur.
    # ITS OLD REASON FOR DEFAULTING OFF DOES NOT CARRY OVER. "It changes every number in the log" is
    # true and is not a reason: P9 expects numbers to move and requires each move to be attributable. The
    # default stays False here only because that is what every existing record was measured under, and a
    # default that quietly differs from the measured one makes the whole record unattributable.

    # ==============================================================================================
    # 3. WHAT A NEWLY MINTED SYMBOL COSTS THE MODEL
    #
    # The tokenizer mints ids; this package owns the rows those ids point at. Four levers decide whether
    # a new symbol arrives as a handover or as a discontinuity the optimizer has to recover from, and
    # that is the mechanism goal A's "room for additional modalities" actually rests on -- a modality is
    # a different alphabet, and an alphabet is new rows in emb and head.
    # ==============================================================================================

    new_row_init = Lever("mean", "How a newly minted token's embedding and head rows are initialized "
                                 "from its two parent tokens.",
                         U.NAME, choices=("random", "mean", "last_first"))
    # Census: WARMSTART_MODE -> LM_NEW_ROW_INIT, verdict rename, ABSORBING the WARMSTART row (verdict
    # merge, CENSUS.md:305) as the "random" value. Field corrected from `LM_NEW_ROW_INIT` to
    # `new_row_init` (DEFECT 1).
    # REASSIGNED TO LM BECAUSE EVERY WRITE IS TO AN LM TENSOR: model.emb.weight, model.head.weight,
    # model.head.bias -- and enc.emb.weight, which is SIG's and must become a declared wire rather than
    # the inline reach it is at :7687-7705. The tokenizer supplies only the (nid, a, b) triple.
    # THE THREE VALUES ARE THE THREE ARMS THAT WERE ACTUALLY MEASURED, on immediate post-mint loss, 6
    # pairs x 3 seeds = 18 trials: random 2.1699 (sd 0.120), mean 1.8222 (sd 0.078), last/first 1.4822
    # (sd 0.011) (:7663-7673). THE HONEST OPEN QUESTION TRAVELS WITH THEM (:7676-7683): last/first wins
    # that measurement by 0.340 but LOST one short end-to-end toy, 5.214 against 5.100, which is well
    # inside the 0.066-0.131 b/B seed spread -- so under PLAN rule 8 neither result may be reported as a
    # verdict from n=1, and the default stays at "mean", which is what the record was taken under.
    # choices= CLOSES A SILENT ELSE, AND THIS IS ANOTHER OF THE ELEVEN ISSUES M24 (:361) NAMES. The
    # source is `if _wm == "mean": ... else: <last/first>` at :7688-7699, so WARMSTART_MODE=Mean,
    # =average or any typo runs last/first while the banner echoes what was typed -- the same class as
    # DATA_MODE=Real. With choices= it is a startup LeverError listing the three legal arms.
    # THE MERGE REMOVES A REAL TRAP, WHICH IS WHY "off" IS A VALUE HERE AND NOT A SECOND SWITCH. With
    # WARMSTART=0 and TOK_COMPOSE=1 the mint still happened but set_vocab was never called, so the
    # composer's byte table had no row for the new id -- an all-zero mask giving a composite IDENTICAL
    # for every token minted that way, "precisely the fresh-indistinguishable-row the ByteComposer exists
    # to abolish, reintroduced by an ablation flag about something else" -- and note_born went with it,
    # so the anchor held nothing either (:7624-7633). One lever with three named values cannot express
    # that state, because the correctness work stops living inside an ablation branch.
    # WHAT IT MEANS ON THE compose ARM: when `compose` is on there is nothing to initialise -- the new
    # token's vector is determined by its bytes and the composer is told about it unconditionally
    # (:7682-7686). So this lever is inert at compose=True, which is a Gate to declare (G4), not a
    # silence to leave.

    compose = Lever(False, "Build each token's vector from its bytes plus a learned residual, instead of "
                           "storing a free row per token.", U.FLAG)
    # Census: TOK_COMPOSE -> LM_COMPOSE, verdict rename, default 0. Field corrected from `LM_COMPOSE` to
    # `compose` (DEFECT 1). Declared False rather than 0 for the coercion reason given at
    # `mask_dead_rows` above.
    # KEPT BY PLAN SECTION 3 ITEM 7 ("ByteComposer and the anchor stay"), and the reason is goal A's
    # second half: a byte-grounded composer is the mechanism that makes a NEW SYMBOL SPACE attachable at
    # all, because a token that has never been seen still has bytes that have.
    # REASSIGNED TO LM ON THE EVIDENCE: ByteComposer is constructed inside MiniLM.__init__ (:1549,
    # `s.compose = ByteComposer(d) if TOK_COMPOSE else None`), its tables are LM parameters, and its
    # output is tied as both the input embedding and the output head. The tokenizer never touches it.
    # IT IS UNTRIPPABLE ON HALF THE MODEL SPACE AND THAT IS THE FIRST THING TO FIX WITH IT. TinyTransformer
    # (:1561) has no compose attribute at all, so LM_COMPOSE=1 with LM_ARCH=transformer is silently a
    # no-op while :6038 prints a coupling sentence describing a mechanism that model does not have
    # (ISSUES.md M22). That is the untrippable-guard class; only a declared Gate printing its own
    # arithmetic (G4) makes it visible, and it is a Gate over TWO of this package's own levers.
    # ITS TABLE MUST BE SIZED FROM `vocab_slots`, NOT FROM A SECOND ENVIRONMENT READ. :1455-1456 sized
    # delta/dbias from its own os.environ read defaulting to 2048 while the tokenizer targeted 4096 --
    # the registry's worst-case example, and an index past the end of a real tensor.

    anchor_w = Lever(0.05, "Weight of the loss term holding a newly minted token's residual near its "
                           "byte composite, so the mint is a handover rather than a jump.", U.FRACTION)
    # Census: TOK_ANCHOR -> LM_ANCHOR_W, verdict rename, default 0.05. Field corrected from `LM_ANCHOR_W`
    # to `anchor_w` (DEFECT 1). UNIT: it is a loss-term coefficient, not a fraction of anything;
    # U.FRACTION is the closest label units.py has, the census says so in as many words, and adding a
    # WEIGHT constant is a spine edit rather than a package edit.
    # A TEXTBOOK WRONG-MEASUREMENT CASE THAT THIS REBUILD MUST NOT REPRODUCE. TOK_ANCHOR=0.05 was printed
    # on the EFFECTIVE line of every run in this project's history while model.compose was None and the
    # term never once entered the loss (:38, :5802-5813, :6030-6037) -- it was simply missing from the
    # loss-weight list. Under G6 a weight that reaches no term may not be printed as if it did, and under
    # G4 the gate on `compose` prints its own state; the pair is why this lever is safe to keep at a
    # non-zero default.
    # WHAT IT BUYS WHEN IT DOES FIRE: anchor() is a method of ByteComposer over LM parameters
    # (:1507-1544) and its term is added to the LM loss at :7034. Without it a minted token's residual is
    # free from the first step and the composite it was handed over from stops predicting it.

    anchor_uses = Lever(400.0, "How many appearances in trained-on material a new token is held near its "
                               "composite for, before the anchor releases it.", U.COUNT)
    # Census: TOK_ANCHOR_USES -> LM_ANCHOR_USES, verdict rename, default 400.0. Field corrected from
    # `LM_ANCHOR_USES` to `anchor_uses` (DEFECT 1).
    # DECLARED 400.0 AND NOT 400. The old reader was `_f` (:982), so the value is a float; Lever.coerce
    # selects its branch from the default's TYPE, and an int default here would truncate
    # LM_ANCHOR_USES=250.5 to 250 without a word. The type is part of the declaration, not an accident of
    # how the number is written.
    # AND MAKE IT THE ONLY RELEASE RULE -- see DEFECT 2 in the header. The source argues the case against
    # its own alternative at :1516-1527: a token minted early appears constantly and is thoroughly
    # trained, while one minted late is rare BY CONSTRUCTION (that is WHY it was minted late), so a
    # shared wall-clock release is anti-correlated with how ready each token is. Counting appearances
    # also makes the anchor independent of re-segmentation by construction: `seen` (_tok_seen, :6307)
    # advances only when the token turns up in a training batch, so a retok cannot move it. This is the
    # shipped behaviour, not a new one -- the >0 default already selects this branch.
    # THE COUNTER IS THE TRAINING LOOP'S, AND IT ARRIVES AS AN ARGUMENT. _tok_seen was a global the loop
    # maintained and anchor() read; under L2 it is handed in explicitly, because a per-token counter
    # reached by name from inside a loss term is the shape of coupling the ledger cannot see.
    # ITS RIVAL IS DROPPED AND THAT IS WHAT KEEPS THIS UNIT HONEST. TOK_ANCHOR_TAU expressed the same
    # horizon in Windows (census unit; the source called it steps), so the two could not be compared
    # without a conversion nobody had written. With one horizon there is one unit and no conversion.

    # ==============================================================================================
    # WHAT IS DELIBERATELY ABSENT, one line each, because a reader who finds them missing will otherwise
    # go looking for a mistake. Full reasons are in the header.
    #
    #   d_pos_max          promote-to-wire (CENSUS.md:415). Positional rows. Would shadow the wire.
    #   d_softmax_width    assemble.py:722 writes it from TOK.vmax; conflict (a) -- the census reverses
    #                      that edge, and `vocab_slots` above is this package's side of it.
    #   d_live_vocab / d_retired_ids / d_max_token_bytes / d_device   incoming wires, not levers.
    #   TOK_ANCHOR_TAU     dropped (CENSUS.md:297): a second unit for `anchor_uses`'s one horizon, and
    #                      three couplings (OPT, DATA, TOK) bought for the privilege.
    #   WARMSTART_OPT      dropped (CENSUS.md:298): its motivation was checked and is false -- Adam's
    #                      step counter is per-TENSOR, so bias correction DAMPS a fresh row; measured, a
    #                      new row's first update was 5.4e-4 with v=0 and 1.0e-3 with inherited moments,
    #                      i.e. inheritance made the first step LARGER, the opposite of the argument. It
    #                      also reached into three packages' optimizer state from inside a tokenizer mint.
    #   MAX_TOK            TOK's lever (CENSUS.md:308); LM receives d_max_token_bytes and sizes the
    #                      composer's byte tables from it instead of the hardcoded maxb=16 at :1441.
    # ==============================================================================================
