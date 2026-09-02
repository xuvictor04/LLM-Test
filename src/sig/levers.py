"""SIG -- the signature encoder: the one description of a window that every router reads.

WHAT THIS PACKAGE OWNS. One function from a window of the stream to a unit vector of width SIG_D, and
the online contrastive objective that trains it. Nothing else in the tree decides what a window IS.
The domain assembler's centroids, the fabric's routing keys, the boundary test, the separability
instruments and every "which expert served this material" number are all statements about the space
this package produces. That is why it is small -- 18 levers against the fabric's 82 -- and why it is
load-bearing out of all proportion to its size: an encoder that collapses makes every downstream
partition number technically valid and meaningless. Measured, on a single corpus: separation ran
0.16 -> 0.05, the run found 0 boundaries and 1 live domain, and every report line still printed.

HOW IT SERVES THE TWO GOALS. Goal A (language production) is served indirectly but not weakly: the
signature is the router's input, so an encoder that maps everything to one point routes every window
to the same experts and the mixture the head decodes stops depending on the material. Goal B
(continual learning without catastrophic forgetting) is served directly -- "do not overwrite what the
old material needs" first requires knowing that the new material IS different, and the boundary test
that says so is a distance in this space. The project's third standing requirement, room for other
modalities later, is why `space` survives as a real arm rather than as an assumption: the alphabet
the signature is built over is a lever, and a byte encoder and a token encoder are already two
different answers to "what is a window made of".

THE ONE WIDTH IS NOT DECLARED HERE, AND THAT IS THE WHOLE ARCHITECTURE. How many bytes a signature is
taken over is `spine.derive.signature_width_bytes(win_tokens, bytes_per_token)`, computed once from
the loop stride and the MEASURED compression, and it reaches this package as the wired field
`d_signature_width_bytes`. It is not a lever because the old SIG_WIN was one knob with one zero that
meant two different things: self_organize.py:5676 resolved 0 to max(WIN, int(WIN*bpt)) = 614 bytes
for training, and :3919 sliced [-max(1, SIG_WIN):] = ONE BYTE for every eval-path signature. Every
held-out, retention, routing, specialization and composition number in every report was therefore
produced by a router routing on one byte, and nothing failed, because every window still produced A
signature. Declaring a `win` lever here would put that back.

-------------------------------------------------------------------------------------------------
WHAT WAS EMITTED, AND WHAT WAS NOT
-------------------------------------------------------------------------------------------------
The census (.rework/census.json) files 24 of its 328 rows under new_owner SIG. This file emits 18:

    15  rows with verdict rename
  +  3  rows with verdict keep (SIG_D, SIG_MODE, SIG_SPACE)
  -------
    18  Lever declarations, all reachable as SIG_<FIELD>

Not emitted, six rows, by verdict:

  3 DROP. ENC_FUSE (the fused anchor/positive encoder pass becomes the only path: +9.5% GPU
    throughput, identical maths, agreement to ~1e-5 float32 rounding rather than bit-for-bit -- and
    a lever whose only effect is to change a reduction order manufactures exactly the diffs
    tests/test_lever_isolation.py exists to interpret). SIG_BATCH (the lookahead batching toggle;
    the batched path becomes the only path and its frozen-encoder precondition becomes an asserted
    invariant). SIG_PROJ_BPT (a manual override on a number whose only job was to judge another
    number -- it pinned projected coverage at 100% while three 18-epoch runs actually ended at 82%,
    70% and 61% of the loop window).

  2 PROMOTE-TO-WIRE, declared nowhere in this file. SIG_WIN is `d_signature_width_bytes`, above.
    EVAL_GIST is `d_eval_gist` -- it was never a lever, it was a switch between two constructions of
    a value SIG owns, and both branches were wrong (a one-byte real signature, or an all-zero gist
    that ranks the population identically for every window).

  1 MERGE. SIG_LOOK folds into SIG_TRAIN_EVERY_IDLE, whose row this file does emit, so nothing had
    to be invented -- see census defect 3 below and the declaration of `train_every_idle`.

NEITHER WIRE EXISTS YET, AND SAYING SO IS PART OF THE HAND-OFF. spine/assemble.py declares ten
couplings and not one of them has a SIG destination (grep `dst=`), so a SIG Config built today has
18 levers and zero wired fields. Reading `cfg.d_signature_width_bytes` raises. The width is listed in
assemble.py's NOT_WIRES on purpose -- bytes_per_token is MEASURED after Config freezes, so it is a
derive-and-keep rather than a build-time wire -- but the three fields this file's comments name
(`d_signature_width_bytes`, `d_positive_radius_bytes`, `d_last_boundary`) are the port's remaining
work, and they are named at the declarations that need them.
THERE WAS A FOURTH IN THIS LIST AND IT WAS ILLEGAL (Q-SIG-1, corrected 2026-09-02).
`d_prototype_reservoir` CANNOT EXIST IN ANY FORM: a Coupling.compute sees only frozen Configs, and a
reservoir is a list of stream windows the loop assigned at RUNTIME -- the same class the
`("encoder","SIG_WIN")` departure refuses `d_signature_width_bytes` for, one step further out.
docs/04_CONTRACT.md's refused-wires table has said so; this file went on naming it as owed work, and
the contract calls `grep -rn d_ src/` a complete coupling index, so two comments were putting a
non-coupling into it. They survived because O4 and K5 are AST checks over code and a `d_` name in a
comment is invisible to both. The reservoir's supplier, if one ever lands, is a DOM ENTRY POINT
returning pairs on the per-window call path -- an argument, not a wire.

-------------------------------------------------------------------------------------------------
THE THREE CENSUS DEFECTS REPAIRED HERE
-------------------------------------------------------------------------------------------------
1. DOUBLED ENVIRONMENT NAMES -- 18 rows corrected, silently, because the correction is mechanical
   and every emitted row needed it. The census records a row's target as `SIG.SIG_TEMP`: the prefix
   in one column and the prefix REPEATED inside the name in the next. spine/lever.py generates the
   environment name as f"{PREFIX}_{FIELD.upper()}", so taking those rows literally declares a field
   named `SIG_TEMP` answering to SIG_SIG_TEMP -- a name no operator has ever typed, on a lever that
   would then run at its default forever while registry.unread_env() reported the operator's real
   SIG_TEMP as a typo with SIG_SIG_D as its nearest match. Every row is read as PREFIX + FIELD: the
   field is `temp` and the environment name is SIG_TEMP. Unlike the fabric family, SIG has no row
   that already named a bare field, so all 18 are corrected and none is left as evidence; the
   evidence that this is clerical rather than intended is in the sibling packages, where the same
   census does it both ways. The promote-to-wire row for SIG_WIN doubles it twice over
   (`SIG.SIG.d_signature_width_bytes`) and is not emitted at all.

2. CLOCK KINDS -- 5 emitted rows carry a clock unit, all 5 filed correctly, 0 conflicts with
   spine/assemble.py. This is worth stating rather than passing over in silence, because the
   opposite finding is the project's most repeated defect and a reader is entitled to know the
   check was run rather than assumed:
     * WINDOWS x3 (train_every, train_every_idle, dense_window). All three are compared against
       `step` -- `_enc_cad = ENC_EVERY if (step - _last_boundary) < ENC_SHIFT_WIN else
       ENC_EVERY_IDLE` at self_organize.py:6647, fired by `step % _enc_cad == 0` at :6648 -- and
       `step` advances once per WINDOW in that loop (one `w = stream[i:i+WIN+1]` per iteration).
       Windows, not Steps, and the census says so in its own reasons.
     * STEPS x2 (warmup, warmup_probe_every). These are NOT the training loop's step counter and
       must not be re-typed as Windows by analogy with the three above. They count iterations of the
       pre-loop warmup at :5023-5035, each of which calls contrastive_step, which calls opt.step()
       on the encoder optimizer. That is an optimizer step, which is what units.Steps means.
     * NO CONFLICT TO REPORT. spine/assemble.py wraps FAB and TRAIN fields in Steps(...) at :686,
       :698 and :711 and could easily have taken a different view of a SIG cadence, but it names no
       SIG lever anywhere; its only SIG entry is the NOT_WIRES row for the width. If a later
       coupling wraps `train_every` in Steps() it will be contradicting this file, and the
       disagreement is the finding, not the wrapper.
   The hazard that remains after correct typing, and the reason `warmup` and `train_every` are
   declared far apart below: both read as "the encoder cadence" in English and they count different
   events. One contrastive_step fires per firing in both places, so the two numbers coincide only at
   train_every=1, which is the default -- exactly the arrangement in which a units mistake is
   invisible until somebody changes a knob.

3. UNRESOLVED MERGES -- none. SIG has one merge row and its surviving target has a row of its own:
   SIG_LOOK folds into SIG_TRAIN_EVERY_IDLE, which the ENC_EVERY_IDLE row creates. Nothing was
   invented and nothing is emitted that the census intended to fold away. The merge is recorded at
   `train_every_idle` rather than only here, because that is where a reader wondering what happened
   to the lookahead cap will look.

-------------------------------------------------------------------------------------------------
FOUR DECLARATION CHOICES THAT ARE NOT THE CENSUS'S
-------------------------------------------------------------------------------------------------
THREE COMPUTED DEFAULTS BECAME LITERALS, AND EACH ONE LEAVES A COUPLING BEHIND. spine/lever.py
refuses a non-literal default by construction, so where the old tree derived a default from another
knob this file states the literal the run of record actually used and names the relation that has to
be declared somewhere visible instead:
    train_every_idle          old `max(ENC_EVERY*6, 12)` -> literal 12   (relation: SIG.d_idle_cadence)
    positive_radius_windows   old `2 * WIN` = 256 bytes  -> literal 2.0  (relation: SIG.d_positive_radius_bytes, from DATA.win)
    warmup_min_frac           old absolute 200           -> literal 0.25 (= 200/800, and no longer a coupling at all)
A default that reads another knob is not a small sin here: it reads that knob EAGERLY, which is how
MAX_DOMAINS = _i("MAX_DOMAINS", _i("FAB_NMAX", 4096)) put FAB_NMAX into the "this run read it" audit
on every run whether or not it mattered.

TWO LEVERS CARRY choices=, AND THEY ARE NOT THE SAME CASE. `mode` is one of the eleven knobs the
survey found falling silently into a default branch on an unrecognised value, and it is the worst of
them because the fallthrough is not even a default: sig_of ends at
`return F.normalize(FROZEN[t].mean(0), dim=0)` (:3259) while the module defines only `_FROZEN` and
`_frozen_tbl` (:3170-3173), so SIG_MODE=frozen is a guaranteed NameError -- and sweep_domain_report
will happily print SIG_MODE=frozen into a "reproduce it" block. `space` is the opposite case: it
already refused unknown values with an explicit sys.exit at :3135. Its choices= is not a new refusal
but the SAME refusal moved into the declaration, so there is one enumeration of the legal alphabets
instead of two that can drift.

THE FIELD IS `d`, NOT `sig_d` AND NOT `dim`. spine/lever.py reserves the `d_` namespace for wires and
refuses any field whose name STARTS WITH "d_"; a bare `d` is not in that namespace and is accepted.
The census asks for the environment name SIG_D unchanged, and field `d` under PREFIX SIG generates
exactly that. It sits one line away from `d_signature_width_bytes` in every reader, which is
uncomfortable and is the price of not renaming a checkpoint-geometry field.

TWO CENSUS UNIT LABELS ARE KEPT DESPITE BEING WRONG IN PRINCIPLE, following the rule the fabric
package set: a label the DEFAULT ITSELF falsifies is worse than no label and gets replaced, but a
label that merely COULD be exceeded is a judgement call this file does not relitigate. `temp` (0.1)
keeps U.FRACTION although a softmax temperature above 1.0 is legal and would then print
"fraction 0..1" beside 2.0; `var_weight` (5.0) and `cov_weight` (0.0) keep the census's U.COUNT
although they are loss weights and not counts of anything. units.py has no TEMPERATURE and no WEIGHT
constant, and adding one is a spine edit, not an encoder edit.
"""
# ABSOLUTE, NOT `from ..spine.lever import ...`, and this is not a style preference. The tree is
# imported with `src` itself on sys.path -- tests/test_derive.py::<module> does it, and so does this file's
# own verification command -- which makes `sig` a TOP-LEVEL package, and a relative import one level
# above a top-level package is an ImportError ("attempted relative import beyond top-level package"),
# not a fallback. The sibling packages src/fabric/levers.py and src/memory/levers.py spell it this
# way for the same reason; two packages that spell one import two ways is the kind of difference that
# decides which of them a runner can load.
from spine.lever import Lever, LeverSet
from spine import units as U


class SIGLevers(LeverSet):
    """The signature encoder's declared knobs: which signature, what it is trained on, when it trains.

    Grouped by mechanism rather than alphabetically, because the levers that break a run together are
    the ones that steer one mechanism. The anti-collapse pair is the clearest case: `var_weight` and
    `cov_weight` are two terms of one regulariser and reading either without the other tells you
    nothing about whether the encoder can collapse.
    """

    PREFIX = "SIG"

    # ==============================================================================================
    # 1. WHICH SIGNATURE FUNCTION, OVER WHICH ALPHABET, AT WHICH WIDTH
    #
    # These four decide what the vector IS before anything decides how it is trained. Three of them
    # are also checkpoint geometry: a resume that disagrees with the sidecar about the alphabet or
    # the width does not fail, it produces a differently-shaped space and keeps going.
    # ==============================================================================================

    mode = Lever("learned", "Which signature function the run uses: the online contrastive encoder, "
                            "or the frozen hashed-bigram control.", U.NAME,
                 choices=("learned", "bigram"))
    # Census: SIG_MODE -> SIG_MODE, verdict keep, and the generated name is unchanged from field
    # `mode`. THE ARM IS NOT OPTIONAL: this is the encoder's own null, the control that answers
    # whether a learned encoder beats a trivial featurizer at all, and probe_signature.py's headline
    # question is exactly that -- if a bigram histogram separates the corpora and the learned encoder
    # does not, the encoder is the problem and not the material.
    # choices= IS THE REPAIR. Branched on at :3253/:3256/:3285 (sig_of, sig_of_batch), :5011
    # (warmup), :6648/:6652 (the step), :6689 (rekey), :8771, :9091 and :9712, with no enumeration
    # anywhere and no else-branch that means anything: the function's last line is
    # `return F.normalize(FROZEN[t].mean(0), dim=0)` against a module that defines `_FROZEN` and
    # `_frozen_tbl` and no `FROZEN`, so any third value is a NameError raised nine call sites away
    # from the mistake (ISSUES H42). With choices= the same typo is a startup LeverError naming both
    # legal values.
    # ONE DEFECT DOES NOT TRAVEL WITH THIS LEVER AND MUST NOT BE FIXED HERE: the run-completion
    # marker was built by .format(SIG_MODE) at :9855, so a bigram arm never matched '_done', was
    # re-run forever by the grid and was reported by equiv.sh as "did not reach the report" despite
    # finishing cleanly (ISSUES L4). That is a rule about run markers -- a marker may not be derived
    # from a lever value -- and it belongs to the harness, not to this declaration.

    space = Lever("bytes", "Alphabet the signature is built over: raw bytes, or the LM's token "
                           "stream.", U.NAME,
                  choices=("bytes", "tokens"))
    # Census: SIG_SPACE -> SIG_SPACE, verdict keep. BOTH SIDES CARRY A STATED REASON, which is what
    # makes this a real arm and not a leftover. bytes is a STABILITY choice: domain centroids persist
    # for the whole run while _retok re-segments the stream underneath them, so a byte signature is
    # the one that stays comparable with itself. tokens lets the signature space grow with the
    # vocabulary and inherits structure the tokenizer already found ('th' + 'e' -> 'the') instead of
    # relearning it -- which is the mechanism behind this project's "room for other modalities"
    # requirement, since a modality is exactly a different alphabet.
    # DO NOT READ ITS DEFECT RECORD AS A REASON TO DROP THE TOKEN ARM. SIG_SPACE=tokens crashed the
    # first time a smoke arm exercised it (E7.14); the per-position expert labels go token-length
    # against a byte index (ISSUES:413); and all three checkpoint consumers feed a token-alphabet
    # encoder raw bytes with no check (ISSUES:677). Those are plumbing and instrument defects on a
    # path that has barely been run, which is the exact case the owner ruled must not be counted as
    # evidence against a mechanism. The sidecar already stores sig_space and enc_v so the mismatch is
    # detectable rather than silent.
    # choices= REPLACES A REFUSAL RATHER THAN ADDING ONE: :3134-3135 already did
    # `if SIG_SPACE not in ("bytes", "tokens"): sys.exit(...)`. Two places that both enumerate the
    # legal alphabets are two places that can disagree; this is now the only one.

    d = Lever(64, "Dimension of the signature vector -- the space domain centroids, fabric routing "
                  "keys and every separability instrument live in.", U.COUNT)
    # Census: SIG_D -> SIG_D, verdict keep. Read at :541 and used at :3373 (the sqrt(SIG_D) VICReg
    # rescale), :3436 (the centroid matrix), :4139 (SigEncoder construction), :4173 (Fabric key
    # width), :5355/:5447 (the checkpoint sidecar) and :8797/:9105 (the random-vector null and the
    # effective-dimension reading).
    # IT IS CHECKPOINT GEOMETRY, so a resume must read it from the SIDECAR and not from this run's
    # environment. :4678-4684 records tensors failing shape checks with no way to tell whether
    # FAB_EMB_HID, SIG_D or D_MODEL was to blame -- three widths, one error message. A Config field
    # cannot enforce that by itself; what it can do is be the single declared width so the sidecar
    # and the run have one name to disagree about.
    # AND ITS NULL IS WRONG IN THE OLD TREE, called out in the file itself: the 1.0 +/- 1/sqrt(SIG_D)
    # null at :8789 is not the null for the statistic it is printed beside. Under P5 that becomes a
    # declared null on the Reading rather than a constant sitting next to a print.

    bigram_dim = Lever(512, "Width of the hashed bigram feature vector used by the frozen-statistic "
                            "control; inert unless mode='bigram'.", U.COUNT)
    # Census: SIG_DIM -> SIG_BIGRAM_DIM. THE RENAME IS THE ENTIRE ROW. SIG_DIM sat one name away from
    # SIG_D and had nothing to do with it: it is consumed at exactly one site, :3257, inside
    # `if SIG_MODE == "bigram"`, as the modulus of the bigram hash. The survey's own record for it
    # ("width of the frozen random projection / signature feature space") shows the confusion already
    # in circulation. Keeping the control means keeping its width configurable: the baseline is only
    # a fair comparison if it can be given a fair capacity.

    # ==============================================================================================
    # 2. WHAT THE CONTRASTIVE OBJECTIVE IS ACTUALLY ASKED TO LEARN
    #
    # InfoNCE learns whatever its positives say are the same thing. The single most consequential
    # fact about this encoder is in the file's own comment at :3315-3322: the positive radius
    # (64-256 bytes at the shipped default) is SHORTER than a splice segment (SEG_MIN=700), so the
    # encoder is explicitly taught that two distant windows of the SAME corpus differ -- and
    # therefore MORE encoder training makes domain identity WORSE, not better. Every lever in this
    # group is a handle on that sentence.
    # ==============================================================================================

    contrastive_batch = Lever(48, "Anchor/positive pairs drawn per InfoNCE step; also fixes the "
                                  "collapse reference ln(B) and the K-floor ln(1+(B-1)/K).", U.COUNT)
    # Census: ENC_BATCH -> SIG_CONTRASTIVE_BATCH. Used at :3313 (anchor-range viability), :3323 (the
    # pair draw), :3343 (prototype-pair cap), :3353 (the fused split), :3357 (cross_entropy targets)
    # and :3399 (the loss floor). B IS PART OF THE DIAGNOSTIC, NOT A THROUGHPUT SETTING: encoder
    # collapse was diagnosed at all because the single-corpus loss plateaued at 3.83 against
    # ln(48) = 3.871, which is the loss of a model that has learned nothing. Change B and that
    # reference number moves with it.
    # SPELLED OUT RATHER THAN SHORTENED, and this is the G12 hazard, not fussiness: the field `batch`
    # under PREFIX SIG generates SIG_BATCH, which in the old tree was the signature-lookahead
    # batching toggle -- a dropped lever whose name an operator may still have in a run script.
    # Re-using a retired name for a new meaning turns a dead setting into a live wrong one.

    temp = Lever(0.1, "InfoNCE softmax temperature: the divisor on the cosine logits that decides "
                      "how sharply a near-miss counts as a negative.", U.FRACTION)
    # Census: TEMP -> SIG_TEMP. One reader, `logits = za @ zp.t() / TEMP` at :3356. THE BARE NAME WAS
    # THE PROBLEM: this tree also has GEN_TEMP (sampling temperature) and ROUTE_T (routing
    # sharpness), and an unprefixed TEMP filed under `misc` beside them is how a reader attributes a
    # generation result to the encoder. The generated name says which temperature it is.
    # UNIT CAVEAT, carried from the census rather than resolved: a divisor of cosine logits is not a
    # fraction in principle and may legitimately exceed 1.0. The default satisfies the label, so the
    # label is kept (see the module header); units.py has no TEMPERATURE constant and adding one is
    # a spine edit.

    positive_radius_windows = Lever(2.0, "Furthest offset at which the InfoNCE positive is drawn "
                                         "from its anchor, as a MULTIPLE of the loop window -- i.e. "
                                         "what the encoder is taught to be invariant to.", U.COUNT)
    # Census: ENC_POS_MAX -> SIG_POSITIVE_RADIUS_WINDOWS. Resolved at :3311, used at :3312 (the
    # anchor bound) and :3323 (the offset draw). This is the single most consequential encoder knob
    # in the file's own account -- see the group header above.
    # THE OLD DEFAULT WAS A WIRE, NOT A DEFAULT: `2 * WIN` = 256 bytes reads DATA's window width, and
    # spine/lever.py refuses that by construction. The lever is now the MULTIPLIER (literal 2.0, the
    # multiple the run of record used) and the byte radius is `SIG.d_positive_radius_bytes`,
    # computed in spine/assemble.py from DATA.win. That coupling is not declared yet -- see the
    # module header's hand-off list. probe_signature.py's PROBE_POSMAX already expresses this in
    # multiples of WIN, so the new unit matches the only tool that has ever swept it.
    # U.COUNT, NOT U.Windows, DELIBERATELY. Windows is a CLOCK KIND, and this is a ratio, not a count
    # of window events. Typing it as a clock would make `positive_radius_windows` comparable against
    # `train_every` -- two numbers that are both "about windows" and mean nothing to each other --
    # which is the confusion units.py exists to prevent rather than to enable.
    # THE PORT OWES A REFUSAL HERE (ISSUES L15). The old clamp was
    # `_pmax = max(2*WIN, _i("ENC_POS_MAX", ...))`, so ENC_POS_MAX=64 at WIN=128 ran at 256 with no
    # message: the knob could only ever WIDEN the radius, while the comment three lines above it told
    # the operator that narrowing it was the fix for the defect the comment describes. A silent
    # floor under a lever whose documented use is to go below that floor is worse than no lever.

    prototype_frac = Lever(0.0, "Fraction of the InfoNCE batch replaced by pairs drawn from ONE "
                                "domain's reservoir, so the encoder is trained on kind-invariance "
                                "and not only on locality.", U.FRACTION)
    # Census: ENC_PROTO -> SIG_PROTOTYPE_FRAC. Read at :3340, applied at :3341-3350, and named at
    # :5056 as one of the two remedies the collapse warning tells the operator to reach for.
    # OFF BY DEFAULT FOR A STATED HAZARD, NOT BY NEGLECT, and the distinction decides whether it is
    # allowed to survive: the assembler's partition would be training the encoder that produces the
    # partition, which is a feedback loop, bounded here by only using a fraction of the batch. This
    # is the ONE encoder lever that reads DOM state (asm.cent / asm.wins).
    # HOW THAT STATE ARRIVES IS SETTLED AND IT IS NOT A WIRE (Q-SIG-1, RESOLVED 2026-09-02). This
    # comment used to say "under L2 the reservoir arrives as `d_prototype_reservoir`". It cannot: a
    # reservoir is runtime state and a coupling's compute sees only frozen Configs. It arrives as
    # SIG.train_step's `reservoir` ARGUMENT, whose default is None -- which is why the frozen
    # signature already permits a supplier to land later at zero cost to SIG.
    # AND THERE IS NO SUPPLIER TODAY, SO THE ARM IS UNREACHABLE AND SAYS SO. DOM has ten entry
    # points and not one returns reservoir windows (DOM.census returns radii, counts, comp_glob,
    # collapsed_at and the rest); the LOOP_ORDER row for train_step supplies stream, seen_units and
    # opt and nothing else, so `reservoir` is None on every call the root makes. sig.prototype_pairs
    # therefore reads `unreachable (no DOM supplier)` with prototype_frac > 0, NEVER "armed but 0".
    # The two routes that were refused, and why, so neither is re-proposed: carrying the reservoir
    # on DOM.census puts a PER-WINDOW training input on the 100-Windows management cadence, where
    # pairs up to 100 windows stale still look like pairs and the arm would report as FIRING while
    # training the encoder on a partition that has since moved; and the root slicing `part.reservoir`
    # itself is refused by O10, with the precedent written one question over for FAB.contribution's
    # `candidates` ("no entry point exports it and O10 forbids the root reaching into pop").
    # WHAT WOULD SUPPLY IT: DOM.reservoir_pairs(dom, part, *, did, n, rng), a new frozen entry point
    # drawing from DOM'S OWN named stream -- domains/api.py records that two draws in that package
    # leaked to the global `random`, which makes draw order a coupling channel no wire declares.
    # DO NOT DROP IT AS INERT. It is the only declared answer to the defect the group header
    # describes -- locality invariance where the assembler is asking a kind question -- so dropping
    # it would leave the file's own diagnosis with no remedy attached.

    floor_kinds = Lever(8, "Assumed number of distinct kinds of material in the stream; sets the "
                           "InfoNCE loss floor ln(1+(B-1)/K) below which the encoder step is "
                           "skipped.", U.DOMAINS)
    # Census: ENC_FLOOR_K -> SIG_FLOOR_KINDS. Read at :3398, gates the optimizer step at :3399-3400.
    # U.DOMAINS AND NOT U.COUNT is the point of the rename: K is a count of KINDS, and the whole
    # derivation only makes sense if K tracks how many kinds are actually in the stream. A bare
    # "count" label invites setting it as a strength.
    # THE LARGEST SINGLE LEVER ON DOMAIN IDENTITY IN THE RECORD, from the in-file measured table at
    # :3386-3396 (real text, 60 kB, 4 corpora): floor K=8 alone moved live domains 50 -> 23, boundary
    # precision 0.61 -> 0.78 and V 0.42 -> 0.49, while K=4 (the true number of processes) landed
    # closest to truth but cost recall 0.59 and homogeneity 0.56. CAVEAT CARRIED VERBATIM BECAUSE IT
    # IS THE WHOLE VALUE OF THE NUMBERS: one run per arm, one stream length, one seed. A signal, not
    # a fact.

    # ==============================================================================================
    # 3. THE ANTI-COLLAPSE PAIR
    #
    # Two terms of one VICReg-style regulariser, weighted independently. They are declared together
    # because reading either alone tells you nothing about whether the encoder can collapse, and
    # collapse is not a hypothetical here: on ONE large corpus InfoNCE has no cross-kind negatives
    # and the file describes collapse as a certainty rather than a risk.
    # ==============================================================================================

    var_weight = Lever(5.0, "Weight on the variance hinge that stops the encoder collapsing to a "
                            "single point.", U.COUNT)
    # Census: ENC_VREG -> SIG_VAR_WEIGHT, renamed only to say what it weights. Read once at MODULE
    # level at :1418 -- deliberately, so the banner and the loss cannot disagree about what
    # regularisation actually ran -- and applied at :3371-3373 after scaling by sqrt(SIG_D), the
    # correction that makes the hinge reachable at all for L2-normalised outputs.
    # LOAD-BEARING FOR GOAL A'S REALISTIC TARGET, because the realistic target is one large corpus:
    # measured, the single-corpus loss plateaued at 3.83 against ln(48) = 3.871 with separation
    # falling 0.16 -> 0.05 and zero boundaries found. 5.0 is the value that restored separation to
    # 0.97 where 1.0 left it at 0.44; the cost on mixed material is small and real (V 0.56 -> 0.52).
    # THE sqrt(SIG_D) RESCALE BECOMES A NAMED derive FUNCTION rather than an inline expression, so
    # the weight and its scaling cannot drift apart -- they are one quantity written in two places
    # today, which is the shape of the SIG_WIN defect.
    # U.COUNT is the census's label and it is wrong in principle (this is a loss weight); see the
    # module header for why it is kept rather than invented around.

    cov_weight = Lever(0.0, "Weight on the covariance (decorrelation) term of the same "
                            "anti-collapse regulariser.", U.COUNT)
    # Census: ENC_CREG -> SIG_COV_WEIGHT. Read at :1418, applied at :3371-3373 through the same
    # _var_cov call as var_weight, printed in the report's not-on audit at :6223 and named at :9110
    # as a candidate explanation for concentrated routing.
    # NOT A DUPLICATE OFF-SWITCH, which is the test a drop would have to pass: VICReg weights
    # variance and covariance independently, and folding them into one number would pin a ratio
    # nobody has measured. Variance stops the representation shrinking to a point; covariance stops
    # it collapsing onto a lower-dimensional subspace, which the effective-dimension reading at
    # :9105 exists to detect and which var_weight alone cannot prevent.
    # OFF BY DEFAULT BECAUSE NOBODY HAS SWEPT IT, NOT BECAUSE IT WAS TRIED AND FAILED. The owner's
    # rule for this census was explicit: a mechanism never observed to fire is not thereby proven
    # useless, and several were inert because the instrument was broken.

    # ==============================================================================================
    # 4. WHEN THE ENCODER TRAINS: THE SHIFT GATE
    #
    # The encoder was profiled at ~87% of loop wall clock at ENC_EVERY=1 (:3294), so the cadence is
    # not a detail. The gate's whole idea is that the cost only has to be paid when the stream is
    # actually moving: dense right after a boundary, throttled once it has been stable.
    #
    # ALL THREE ARE WINDOWS. See census defect 2 in the module header for why, and for why the
    # warmup clocks in group 5 are Steps despite reading like the same kind of number.
    #
    # THE GATE'S INPUT IS NOT OURS. `_last_boundary` is written by the domain assembler at :6686 and
    # read here as an ambient local; under L2 it must arrive as `d_last_boundary`. Until that
    # coupling is declared, this group's three levers describe a gate with no trigger.
    # ==============================================================================================

    train_every = Lever(1, "Encoder training cadence while the stream is near a detected boundary "
                           "-- the dense arm of the shift gate.", U.Windows)
    # Census: ENC_EVERY -> SIG_TRAIN_EVERY, typed Windows by the census and confirmed against the
    # source: `step % _enc_cad == 0` at :6648, where `step` advances once per window.
    # RENAMED BECAUSE "EVERY" ALONE NEVER SAID EVERY-WHAT, and because the field `every` would be as
    # anonymous under PREFIX SIG as it was under `misc`.
    # ITS OLD SECOND JOB IS GONE, and that is the point of the row. ENC_EVERY was the parent of two
    # computed defaults -- ENC_EVERY_IDLE, and then SIG_LOOK through it -- which self_organize.py:
    # 6119-6120 names as the model case of a laundered coupling: "ENC_EVERY quietly setting SIG_LOOK
    # (two hops, through ENC_EVERY_IDLE) stayed unstated". L1 forbids a computed default, so the
    # first hop becomes a declared relation and the second hop is deleted with SIG_LOOK itself.

    train_every_idle = Lever(12, "Throttled encoder cadence once the stream has been stable for "
                                 "longer than the dense window.", U.Windows)
    # Census: ENC_EVERY_IDLE -> SIG_TRAIN_EVERY_IDLE. Resolved at :5306, consumed at :5320 and :6647.
    # THE DEFAULT WAS A WIRE. The old declaration was `_i("ENC_EVERY_IDLE", max(ENC_EVERY * 6, 12))`
    # -- a default read from another lever, which spine/lever.py refuses in as many words. THE
    # LITERAL 12 IS WHAT THE RUN OF RECORD USED: at the shipped ENC_EVERY=1, max(1*6, 12) = 12. The
    # "idle follows the dense cadence" intent is not lost, it is relocated: SIG.d_idle_cadence =
    # `max(train_every*6, train_every_idle)` IS DECLARED in spine/assemble.py as of 2026-08-30, and
    # sig/api.py's cadence_due reads it. Same-package couplings were already the practice there
    # (FAB.d_operating_population is computed from FAB's own levers).
    #
    # IT SAID "it is simply not declared yet" FOR SIX COMMITS, and that sentence is why this note is
    # longer than the fix. A relation recorded as relocated to somewhere it never landed is INVISIBLE
    # to every check that reads declarations, because the declaration it was relocated TO does not
    # exist: train_every_idle sat at a literal 12 with no connection to train_every, so changing the
    # dense cadence left the idle one where it was, silently. At the shipped train_every=1,
    # max(1*6, 12) = 12 and no recorded result moves -- which is exactly what let it survive. It was
    # found by tests/test_ownership.py's O11, which reads the docstring SPECIFICATIONS precisely
    # because every body here is still a stub (ISSUES H53).
    # THIS LEVER ABSORBS THE ONE MERGE ROW IN THE SIG CENSUS, and the merge is RESOLVED -- the target
    # is this row, which exists, so nothing had to be invented (census defect 3). SIG_LOOK capped how
    # many upcoming windows the signature lookahead could pre-compute:
    #     _H = min(_sig_horizon(step, _last_boundary), SIG_LOOK, (len(stream)-1-i)//WIN)     (:6656)
    # and _sig_horizon already returns at most ENC_EVERY in the dense phase and at most
    # ENC_EVERY_IDLE in the idle phase (:5317-5320), while SIG_LOOK's own default WAS ENC_EVERY_IDLE.
    # The third term of that min could only ever tie, never cut. Removing the knob removes the second
    # hop of the laundered coupling; the LOOKAHEAD ITSELF SURVIVES, bounded by this cadence and by
    # the retok distance. This is a redundancy drop, not an inertness drop.

    dense_window = Lever(400, "How long after a detected boundary the encoder stays on the dense "
                              "cadence before falling back to the idle one.", U.Windows)
    # Census: ENC_SHIFT_WIN -> SIG_DENSE_WINDOW. Read at :5307, used at :5318-5319 and :6647.
    # RENAMED BECAUSE THE OLD NAME NAMED THE WRONG THING: "SHIFT_WIN" reads as a shift WIDTH in the
    # SHIFT_DIST family, and it is a recovery DURATION -- how long the dense arm lasts, not how big a
    # distribution shift has to be.
    # ITS CLOCK IS THE WHOLE ROW: it is compared against `step - _last_boundary`, and step counts
    # windows. units.py records that four subsystems' modulo cadences never coincided with the clock
    # they were compared against, and this is the one that decides whether the encoder ever notices a
    # real distribution shift -- a dense window in the wrong unit is a gate that is always open or
    # always shut.

    # ==============================================================================================
    # 5. WARMUP, AND THE ADAPTIVE STOP THAT READS IT
    #
    # The encoder is trained unsupervised BEFORE the main loop starts, so the assembler does not
    # begin on an unseparated encoder. Everything in this group is denominated in encoder optimizer
    # STEPS -- the pre-loop iterations at :5023-5035, each of which calls contrastive_step, which
    # calls opt.step(). They are NOT the main loop's window counter, and typing them as Windows by
    # analogy with group 4 would be the same class of mistake in the other direction.
    # ==============================================================================================

    warmup = Lever(800, "Budget of unsupervised contrastive steps run before the main loop starts.",
                   U.Steps)
    # Census: ENC_WARMUP -> SIG_WARMUP. Read at :5012 and again for the ETA at :4319 at the same
    # default -- which is itself the L1 defect in miniature, one number written twice.
    # NOT A MORE-IS-BETTER SETTING: the file records that 1-NN corpus accuracy PEAKS at roughly
    # 1000-4000 steps and DEGRADES after, which is the group-2 story again (a longer-trained encoder
    # is a more thoroughly locality-invariant one). This is the knob that decides how much of a run's
    # domain identity is fixed before a single byte of text has been trained on.
    # CARRY-FORWARD HAZARD, preserved because losing it would make two archived results look
    # comparable: self_organize.py:611 records that two runs changed the threshold rule AND
    # ENC_WARMUP together, so neither result can be attributed to either change.

    warmup_min_frac = Lever(0.25, "Share of the warmup budget that must be spent before the plateau "
                                  "test is allowed to stop it early.", U.FRACTION)
    # Census: ENC_WARMUP_MIN -> SIG_WARMUP_MIN_FRAC. Read at :5021 as
    # `_wfloor = min(ENC_WARMUP_MIN, ENC_WARMUP)` and tested at :5032.
    # THE MECHANISM KEEPS; THE ABSOLUTE UNIT DOES NOT, and this is the poster child for the
    # untrippable-guard class -- 60 of the survey's 475 records. A floor expressed as an absolute
    # step count can exceed the budget it floors, and then min() collapses it onto the full warmup
    # and the plateau test can NEVER fire: the shipped state was 3000 against a budget of 800, so the
    # adaptive stop -- described in the file as the #1 startup cost saving -- was off in every run
    # that used the defaults, and the run that paid the full budget was told it had converged.
    # Worse, d267864 corrected the registry to 200 and left the call site at 3000, so _env's
    # mismatch check SystemExited every run for five commits (ISSUES C13).
    # AS A FRACTION THE INVERTED PAIR IS NOT MERELY DETECTED, IT IS UNREPRESENTABLE: a fraction of
    # the budget cannot exceed the budget. The run-time warning at :5046 and the min() clamp both
    # disappear with it. The literal 0.25 is 200/800 -- the behaviour of record, not the shipped
    # 3000. NOTE ISSUES M11: a doc prescription asserting the default is 3000 is itself wrong and is
    # deliberately not carried into this comment.
    # THE GUARD COMES BACK IF THE PORT EVER COMPARES THIS TO AN ABSOLUTE STEP COUNT. It is a fraction
    # of `warmup` and must be multiplied by it at the one site that uses it.

    warmup_plateau_eps = Lever(0.015, "Relative gain in separation below which the adaptive warmup "
                                      "declares the curve flat and stops early.", U.FRACTION)
    # Census: ENC_WARMUP_EPS -> SIG_WARMUP_PLATEAU_EPS. Read at :5021, tested at :5032. It is the
    # only threshold the adaptive stop has.
    # THE DEFECT TRAVELS WITH THE INSTRUMENT, NOT WITH THIS LEVER, and the distinction is why the
    # lever keeps its meaning unchanged: `_sep <= _prev_sep * (1 + eps)` is true when separation is
    # FLAT and equally true when it is COLLAPSING. On a single-corpus stream running 0.16 -> 0.05 --
    # a 69% collapse -- it reported a converged plateau and stopped (ISSUES H49), after which
    # SHIFT_DIST never fired, the run found 0 boundaries and 1 domain, and every downstream report
    # line still printed. The post-hoc collapse warning at :5049 patches the REPORT, not the STOP.
    # Under P5 the stop becomes a Gate whose predicate is a pure function of the probe samples and
    # whose arithmetic is printed, so a stop on a falling curve shows its own numbers instead of
    # claiming convergence. No value of this lever fixes that; a smaller eps just stops later.

    warmup_probe_every = Lever(500, "How often, during warmup, the separation probe is taken -- the "
                                    "sample grid the plateau test reads.", U.Steps)
    # Census: ENC_WARMUP_PROBE -> SIG_WARMUP_PROBE_EVERY. Read at :5021, tested at :5024 as
    # `t % _probe_ev == 0` against the warmup loop counter, which is why this is Steps and not
    # Windows: t counts encoder optimizer steps, and the main loop has not started yet.
    # GENUINELY INDEPENDENT OF THE STOP THRESHOLD -- grid resolution versus stopping criterion -- so
    # it is not merged into warmup_plateau_eps. It sets the resolution of the only curve that can say
    # whether the encoder separated or collapsed.
    # ALREADY DECLARED AS MEASUREMENT RATHER THAN TRAINING, and the new declaration keeps that: the
    # probe carries `@no_rng_drift` at :5013 with the comment "ENC_WARMUP_PROBE is a cadence, not a
    # training knob", which is exactly the instrument-line property P5 formalises. Under P5 the probe
    # becomes a Sample carrying its own width and seed count instead of an inline 64-window draw, so
    # the separation number is comparable across runs that probed at different cadences.
