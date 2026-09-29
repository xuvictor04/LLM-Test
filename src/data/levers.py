"""DATA -- the bytes the run trains on: which corpora, in what order, cut where, and what is held back.

WHAT THIS PACKAGE OWNS. One stream of bytes, the per-byte area labels that go with it, and the held-out
split that every claim about generalisation is computed on. Four mechanisms, and the four groups of
levers below are those four: the SOURCE (corpora on disk, or synthetic Markov processes), the SHAPE of
the splice (how long a segment is, and whether it is read in order or seeked to), the SCHEDULE (who is
live in each phase -- which is the continual-learning protocol itself, not a detail of it), and the
HELD-OUT SPLIT plus the exposure guards that say whether the split means anything. What leaves this
package is a byte stream, an area label per byte, the set of splice positions, and one held-out block
per area. Nothing else in the tree may decide any of that.

WHY THESE ARE THE LEVERS, UNDER TWO GOALS AND NOT THREE. Goal A needs bytes and needs them measured
honestly, which is `holdout_frac`, `val_cap` and the two exposure guards: a held-out number computed
over a block the model has effectively seen is not a language-production result, it is a memorisation
result wearing one. Goal B is stronger than that -- it needs a NON-STATIONARY stream, because a
stationary i.i.d. splice of N corpora does not require continual learning at all. It is ordinary
training with extra machinery, and every number this project has published was measured on one. That
makes `phase_sched` the sharpest lever in this file by a distance: it decides whether the system appears
to satisfy goal B. The two protocols disagreed 10x on the same toy -- +0.046 HELD rehearsed against
+0.444 WORSE pure -- so the schedule is not a parameter of the experiment, it IS the experiment.
D2 (2026-08-28) rules PURE_ADD the default protocol: the added area streams alone, and rehearsed
([[0],[0],[1],[1]]) is the named comparison arm. See `phase_sched` for why that ruling could NOT be
carried as this lever's literal default, and where it has to live instead.

--------------------------------------------------------------------------------------------------
WHAT WAS EMITTED, AND WHAT WAS NOT
--------------------------------------------------------------------------------------------------
The census (.rework/census.json, filtered on new_owner == "DATA") files 18 of its 328 rows here, and
they arrive from THREE families, which is the whole argument for owning by prefix rather than by tag:

    13 rows from the `data` family      -- the ones nobody disputes
     3 rows from the `domains` family   -- seg_min, seg_max, seg_contig. All three are read only inside
                                           build_stream (:1299-1312, :1406, :1410); the domains package
                                           never sees them. Two of the three were MISSING from the
                                           census entirely until review 2 found them ("domains only
                                           31/37 covered ... SEG_MIN and SEG_MAX are recorded as
                                           'registry says domains; is a data/stream knob'").
     2 rows from the `misc` family      -- n_processes and val_cap, both mis-tagged, and the survey's
                                           so-config record says so outright for both.

This file emits 40 levers:

    11  rows with verdict rename
  +  6  rows with verdict keep
  +  1  amendment: DATA_DRAW, minted 2026-09-02 under the owner's ruling on ISSUES P1-H58. It has no
         census ancestor -- the old tree had one draw law and no switch over it -- so it is carried
         as an `amendments` row in census.json, which is what N2 reads.
  +  1  amendment: DATA_SYNTH_HOLDOUT, minted 2026-09-27 under Proposal 04's SR0 (register 04-Q5,
         Proposal 05 §8 3.1; docs/04_CONTRACT.md Q-DATA-9). No ancestor either: the old synthetic
         generator held nothing out and had no switch over it.
  +  3  amendments: DATA_REPLAY_SHARE, DATA_REPLAY_NEWEST and DATA_REHEARSE_PARENT, minted
         2026-09-28 with DATA_DRAW's 'replay' law (Proposal 04 §1 item 2; register 04-Q1, 04-Q4, O9
         and O16, Proposal 05 §8 3.3; docs/04_CONTRACT.md Q-DATA-10). No ancestors: the old tree had
         no rehearsal law and no parent record to rehearse from.
  + 14  amendments: DATA_TRUST and the thirteen levers of its book (DATA_TRUST_RULE, _CLAIM, _CTX,
         _VAL, _DELIMS, _HOT, _SELF, _MIN_N, _MIN_EV, _MIN, _EVERY, _SKETCH and _TABLE), minted
         2026-09-28 with Proposal 04's SR3 source-reliability book (register 04-6.3, Proposal 05
         §8 3.4; docs/04_CONTRACT.md Q-DATA-11). No ancestors: the old tree kept no book of which
         source to believe. Section 6 below.
  +  4  amendments: DATA_TRUST_COPY and the three numbers of its model (DATA_TRUST_COPY_PRIOR,
         _RATE and _P), minted 2026-09-28 with Proposal 04's SR6 copy detection (register §8 3.7;
         docs/04_CONTRACT.md Q-DATA-12). No ancestors: the old tree judged no pair of sources.
         Section 6b below.
  -------
    40  Lever declarations, all reachable as DATA_<FIELD>

Not emitted, by verdict: 1 merge, 0 drop, 0 promote-to-wire.
  MERGED (folds into a lever this file DOES declare, so it is not an unresolved merge):
    PHASED (1) -> `phase_sched`. PHASED=0 IS a schedule -- the single-phase all-active one -- and the
                  duplicate encoding cost more than redundancy: every consumer tested both (`if PHASED
                  and PHASE_SCHED` :5499, `if (PHASED and _cur_ph >= 0)` :6414), three report sections
                  branched on PHASED alone (:8099, :8133, :9809), and the whole-process UNLEARN test ran
                  OUTSIDE the `if PHASED:` guard holding the other two edit tests, so it could delete
                  what _edit_test had already deleted and print "LOCAL" from an edit that removed
                  nothing (ISSUES P1-M65). See DEFECT 3 for the one thing the merge still requires.

--------------------------------------------------------------------------------------------------
THE THREE CENSUS DEFECTS, CHECKED HERE
--------------------------------------------------------------------------------------------------
1. DOUBLED ENVIRONMENT NAMES -- 14 rows corrected, out of 17 emitted.
   spine/lever.py generates the environment name as f"{PREFIX}_{FIELD.upper()}" and the Lever carries no
   prefix of its own. A census row that names its target `DATA.DATA_VAL_CAP` therefore declares, taken
   literally, a FIELD called DATA_VAL_CAP answering to the environment name DATA_DATA_VAL_CAP: a name no
   operator has ever set, on a lever that then runs at its declared default forever while
   registry.unread_env() reports the operator's real DATA_VAL_CAP as a typo with no near match. Both
   halves of that failure are silent. The adversarial reviewer reproduced the mechanism on this exact
   row ("PREFIX='FAB' with a field FAB_N0 yields env_names {'FAB_FAB_N0', ...}" -- and the list of
   offenders it gives names `DATA.DATA_VAL_CAP` explicitly, .rework/reviews.json review 2).
   Corrected here by stripping the repeated prefix, field = new_name without its leading "DATA_":
       DATA_N_PROCESSES -> n_processes    DATA_PHASES        -> phases
       DATA_VAL_CAP     -> val_cap        DATA_PHASE_SCHED   -> phase_sched
       DATA_CORPUS_CAP  -> corpus_cap     DATA_PHASE_LIVE    -> phase_live
       DATA_DIR         -> dir            DATA_STREAM_BYTES  -> stream_bytes
       DATA_SOURCE      -> source         DATA_HOLDOUT_FRAC  -> holdout_frac
       DATA_RESAMPLE    -> resample       DATA_EXPOSURE_MAX  -> exposure_max
       DATA_AREAS       -> areas          DATA_EXPOSURE_SKEW -> exposure_skew
   Every generated environment name is unchanged from what the census intended (DATA_VAL_CAP, DATA_DIR,
   DATA_PHASE_SCHED, ...); it is the FIELD that had to lose the prefix. A fifteenth occurrence of the
   doubled form sits on the merged PHASED row, whose target is also written `DATA.DATA_PHASE_SCHED`; it
   needed no correction because that row emits nothing.
   THREE ROWS WERE ALREADY CORRECT and were carried over verbatim: seg_min, seg_max and seg_contig,
   which the census names in bare-field form. They are the three rows that were added LAST, after review
   2, which is consistent with the reviewer's reading that the doubling is a clerical habit in the older
   sections rather than a decision anywhere.

2. CLOCK KINDS -- 0 rows corrected, because 0 of the 18 DATA rows carry a clock unit, and that is a
   fact about this package rather than an oversight. (ONE AMENDMENT DOES, since 2026-09-28:
   DATA_TRUST_EVERY is U.Windows, the source-reliability book's cadence, compared against RUN's
   window clock through DATA.trust_period -- a threshold on the loop's counter and not on this
   package's material, so no census row, and nothing below, moves by it.) The census types these
   rows bytes, count, fraction, on/off, NAME and PATH. DATA measures its material in BYTES and its
   schedule in AREAS; it counts no running counter of its own, so nothing here is a threshold
   compared against one. The one clock this package's material genuinely touches -- the epoch -- is
   not owned here: EPOCHS is filed under the `data` family in _SPEC and the census moves it to
   RUN.RUN_EPOCHS, typed Epochs, which is right, because units.py rules that an epoch is never a
   schedule horizon and that ruling has to be enforced where the horizon is declared. Nothing to
   correct. TWO ADJACENT FAULTS ARE NAMED RATHER THAN FIXED, both of which a clock kind would not
   have caught anyway because neither is a clock:
     * `steps = STREAM_LEN // WIN` (:4317, :4719) divides a BYTE budget by a TOKEN window. That is the
       byte/token confusion this family keeps producing, and it is why `stream_bytes` carries the unit
       in its NAME as well as its metadata. It cannot be typed away: U.BYTES and U.TOKENS are metadata
       labels, not runtime types, and only Clocks are enforced.
     * ASSEMBLE ALREADY NAMES A QUANTITY THIS PACKAGE DOES NOT OWN. spine/assemble.py::COUPLINGS records a
       rejected wire as "SIG.d_signature_width_bytes from DATA.win x the measured bytes/token", i.e. it
       calls the loop window DATA.win. The census gives WIN to LM (WIN -> LM.LM_CTX, 128, TOKENS), and
       this file declares no window lever. The rejection itself still stands on its own reasoning and is
       not affected; the LABEL is stale and should read LM.ctx. Stated, not silently changed: editing
       another package's rejection note to match my reading of the census is exactly the kind of quiet
       reconciliation the census exists to prevent.

3. UNRESOLVED MERGES -- 0. The single merge row (PHASED) names DATA_PHASE_SCHED as its survivor, and
   DATA_PHASE_SCHED has its own census row (verdict keep) which this file declares as `phase_sched`.
   Nothing had to be emitted under its own name to avoid inventing a target.
   WHAT THE MERGE STILL REQUIRES OF THE READER, because a merge that the resolver cannot express is a
   dropped mechanism wearing a merge's clothes: PHASED=0 was the STATIONARY stream, every area present
   throughout, and the generator CANNOT produce it. `derive.phase_schedule` reproduces the shipped rule
   including `if w >= n_areas: w = n_areas - 1` (derive.py::pin_tick, self_organize.py:1346) -- never
   all-active, deliberately, because `faded` is read off the last phase and an all-active last phase
   makes the unlearn test skip itself as vacuous. So the stationary arm exists only as an EXPLICIT
   schedule, "0,1,2,3" at four areas: one phase, everyone live. The port must accept that string, and
   the report must be able to say the run was stationary, or PHASED=0 has been deleted rather than
   merged.

--------------------------------------------------------------------------------------------------
WHAT IS DELIBERATELY ABSENT
--------------------------------------------------------------------------------------------------
NO WIRES ARRIVE HERE TODAY. spine/assemble.py declares no d_ field on DATA (the only three mentions of
the string DATA in that file are prose). If one is added later it must NOT be declared in this class --
lever.py refuses a d_-named lever precisely so a declaration cannot shadow the wire that writes it.

ONE VALUE LEAVES, AND IT IS NOT DECLARED HERE EITHER -- NOR IS IT A WIRE. The census's val_cap row asks
for the RESOLVED held-out size to reach EVAL "as a wire so the Sample can state how many bytes it
actually covered". THAT WIRE DOES NOT EXIST AND MUST NOT: docs/04_CONTRACT.md section 0's
"Candidates examined and refused as wires" table lists EVAL.d_holdout_bytes among the REFUSED wires
-- cited by SECTION and not by line, because the contract grew 1908 lines on 2026-09-02 and the
line number this comment used to give (:74) now lands twelve lines above the table -- because the
size depends on how many bytes are on disk,
so build() would have to stat the corpus -- IO inside the ownership spine and a non-reproducible
startup -- and wiring val_cap instead would print the CEILING as the size. It is the same refusal that
holds for bytes_per_token and the SIG width. The resolved size travels as an ARGUMENT and is recorded
as a Sample field -- see `val_cap`. This sentence used to say the wire was declared in spine.assemble;
it never was, and a P4 author following it would try to declare a coupling A1/K5 then bounces with a
message that does not explain why.

FOUR FOREIGN VALUES THIS PACKAGE READS TODAY AND MAY NOT. None is declared here; a value another package
owns arrives as a wire or it does not arrive:
    WIN         -- LM's context width (census: LM.LM_CTX). Read at :5707 to compute windows-per-segment
                   and at :4317/:4719 to turn the byte budget into steps.
    EPOCHS      -- RUN's (census: RUN.RUN_EPOCHS). The exposure arithmetic at :5514 multiplies by it,
                   and _resample runs once per epoch.
    SEED        -- RUN's (census: RUN.RUN_SEED). `_srng` built the stream generator as
                   `random.Random((_i("SEED",0) * 1000003) ^ (epoch * 2654435761))` at :1390, reading
                   the environment from inside the stream builder. The replacement is spine.rng:
                   rng_for("data", seed) -- per-subsystem, name-keyed, and recorded by rng.issued(), so
                   a stream that never drew reads armed-and-inert instead of reading like a healthy one.
                   assemble.py's NOT_WIRES rejects a d_seed wire by name and gives that reason.
    TOKENIZER   -- TOK's (census: merged into TOK.TOK_MODE). :1102-1106 raises SystemExit("TOKENIZER=1
                   requires DATA_MODE=real") while DATA_MODE defaults to synthetic, so THE DEFAULT
                   ENVIRONMENT EXITS AT STARTUP. That constraint is an artifact of where the build code
                   sits, not a property of either mechanism, and it is TOK's row to repair.

PURE_ADD IS NOT A LEVER, HERE OR ANYWHERE. It appears 0 times in self_organize.py. It is longrun.sh's
shorthand: `PURE_ADD=1` EXPANDS to PHASE_SCHED="1|1|1|1", and only because that harness runs two areas.
Declaring it as a lever would be minting a knob the census never censused, and a boolean whose meaning
depends on the area count is the class of defect `phase_live` is being repaired for.

THE SURVIVING-AREA COUNT IS NOT A LEVER AND MUST NOT BECOME A d_ FIELD. On the real path the old tree
read N_PROCESSES into NP at :539 and then OVERWROTE it with `NP = len(CORP)` at :1148, so the lever had
no effect at all under DATA_MODE=real while still being reported as the run's configuration. The count
of corpora that survived the 5000-byte filter is a quantity DATA computes from its own levers; that
makes it neither a lever (computed) nor a wire (d_ is the CROSS-package namespace, and an intra-package
derivation would appear in the coupling graph as an edge from DATA to DATA). It belongs in the
resolver, computed once and printed, and `n_processes` below must never be written to.
"""
# ABSOLUTE, NOT `from ..spine.lever import ...`. Every entry point in this tree puts `src` ITSELF on
# sys.path -- tests/test_derive.py::<module>, tests/test_ownership.py's SRC insert, and this file's own
# verification command -- which makes `data` a TOP-LEVEL package, and a relative import one level above
# a top-level package raises "attempted relative import beyond top-level package" at import time. All
# six sibling packages (domains, eval, fabric, memory, sig, tok) spell it exactly this way; two packages
# spelling one import two ways is the difference that decides which of them a runner can load.
from spine.lever import Lever, LeverSet
from spine import units as U


class DATALevers(LeverSet):
    """The stream's declared knobs: source, shape, schedule, held-out split -- and, since 2026-09-28,
    the source-reliability book that reads the stream's text (section 6).

    Grouped by mechanism, because that is how they fail together -- and because a flat list is what let
    the old tree file the splice lengths under `domains`, the held-out cap under `misc`, and the phase
    schedule beside them under `data`, three families for one build_stream.

    Read `cfg.stream_bytes`, never an environment name. Every value here is resolved once by
    spine.assemble and frozen; a function receiving this Config should open with
    `dat = dat.owned_by("DATA")`, because a Config is an ordinary object and a foreign one handed in
    reads happily and wrongly.
    """

    PREFIX = "DATA"

    # ==============================================================================================
    # 1. WHERE THE BYTES COME FROM
    #
    # Two sources, and the choice gates whether half the names in this package exist at all. Both must
    # run from an empty environment (P3), which the shipped pair does not.
    # ==============================================================================================

    source = Lever("synthetic", "Which stream the run trains on: `real` splices the corpora under "
                                "DATA_DIR, `synthetic` generates from Markov processes.",
                   U.NAME, choices=("real", "synthetic"))
    # Census: DATA_MODE -> DATA_SOURCE. "Mode" names nothing; the knob picks the stream's SOURCE.
    # choices= IS THE REPAIR, NOT DECORATION. This is knob number one of the eleven ISSUES P1-M24 records
    # where an unrecognised string falls into whichever branch is the `else` -- "DATA_MODE, SIG_MODE,
    # MODEL, VERIFY, KEY_SRC, LR_SCHED, SIG_SPACE, WARMSTART_MODE, TOK_PROBATION_BY, CHAIN_ROUTE,
    # CULL_MODE and EVICT are all compared case-sensitively" (ISSUES P1-M24, and the [so-config/facts]
    # entry beginning "AMP is the only string knob in the region that is case-normalised").
    # The comparison is
    # `if DATA_MODE == "real"` at :1102/:1120, so DATA_MODE=Real takes the SYNTHETIC branch silently and
    # then dies at :1104 with a message that reads as if the operator had asked for synthetic. With
    # choices, DATA_SOURCE=Real is a startup refusal naming the two legal values. Case is NOT normalised
    # here: AMP is the only knob in the tree that lowercases, and refusing is honest where silently
    # accepting two spellings is a second name for one arm.
    # THE DEFAULT IS THE CENSUS'S LITERAL AND IT IS KNOWN-BROKEN IN COMBINATION. Shipped default
    # synthetic + TOKENIZER=1 exits at startup (ISSUES P1-M20), and the synthetic path itself crashed on a
    # bare NameError for twelve days -- VALC/CORP/DN/SEG_LEN/DISK_STREAM only exist under the real
    # branch -- with preflight.sh's END-TO-END SMOKE the only caller that ever exercised it (C33, H9).
    # The default is not changed here because the fix is TOK's (its row merges TOKENIZER into TOK_MODE
    # and removes the constraint) and because a default changed in two packages at once is a default
    # nobody decided. P3's empty-environment test on both paths is what proves it.

    dir = Lever("data", "Root of the corpus tree; an area with no '/' is read from "
                        "DATA_DIR/train/<area>/*, and an area containing '/' is joined under "
                        "DATA_DIR verbatim (DATA_AREAS=\"eng,continual/01_rust\").",
                U.PATH)
    # Census: DATA_DIR -> DATA_DIR, one of the few knobs whose shipped name is ALREADY exactly
    # PREFIX + FIELD, so the field has to be the bare word `dir` for the generated name to come out
    # unchanged. Read at :1124 (open_corpus), :1161-1164 (the no-usable-corpus message) and :1184 (the
    # _fetch_manifest.json check that decides whether the held-out tail is a sample or a block).
    # ONE NAME, TWO DECLARATIONS, AND NOW ONE: longrun.sh:538 reads `DD=${DATA_DIR:-data_big}` with its
    # own default. That harness variable and this lever are now the SAME environment name with two
    # different defaults, which is the L1 failure this spine exists to end -- and it can only be ended
    # on the harness side, by the launcher setting DATA_DIR and letting the lever read it, never by both
    # declaring what it means when unset.

    areas = Lever("eng,py,num,c", "The corpora to stream, in order; their names label every per-area "
                                  "score in the report and across the run boundary. An entry may "
                                  "contain '/' to reach a tree beside train/ (continual/01_rust); "
                                  "the label is then the basename.", U.NAME)
    # THE SLASH RULE, RULED 2026-09-02 (Q-DATA-4), AND IT IS A CHANGE TO WHAT THIS STRING MAY SAY --
    # not to its default, which is untouched. datastream.py:72 hardcoded {data_dir}/train/{d}/*, so
    # data/continual/ (1.5 MB, four arriving areas) and data/ood/ (764 KB) -- the material the
    # add-an-area benchmark exists for -- were reachable only by moving files, i.e. by a configuration
    # no Sample can record. An entry with no "/" keeps train/ as the implicit prefix, so every shipped
    # spelling means exactly what it meant. Two startup refusals come with it and DATA.open_areas owns
    # both: an absolute entry or one containing ".." is refused (otherwise this is an arbitrary-path
    # read), and two entries whose BASENAMES collide are refused with both source paths printed --
    # because the label is what per-area scores, the holdout rng key and ACROSS THE RUN BOUNDARY look
    # up by name, and one label over two corpora is ISSUES P3-C19 from the other side.
    # Census: DOMAINS -> DATA_AREAS. RENAMED FOR A GLOSSARY COLLISION THAT IS ALREADY PRODUCING WRONG
    # NUMBERS (G12). "Domain" in the DOM package is a self-assembled partition cell; this knob is a list
    # of corpus DIRECTORIES. Two meanings, one word, and the old _DERIVED table even wired SEG_CONTIG's
    # default off it (:92). "Area" is the word the add-an-area benchmark uses, which is the benchmark
    # the whole continual-learning claim is measured on.
    # THE LEVER DECLARES WHAT WAS REQUESTED; THE RECORD MUST CARRY WHAT SURVIVED. open_corpus returns
    # one entry per name in this order, then :1143-1147 drops every corpus under 5000 bytes from CORP
    # WITHOUT dropping the name from DN, so the lists desynchronise and report_holdout labels each
    # held-out score with a neighbour's name. Reproduced in the source's own comment, at DOMAINS="eng,py"
    # with an undersized eng: VALC[0] is the PYTHON corpus and the report calls it 'eng'. Because ACROSS
    # THE RUN BOUNDARY looks the previous run's probe up BY NAME, the next run then compares this run's
    # Python against last run's English and reports the difference AS FORGETTING -- the one number goal B
    # rests on, computed across two languages (ISSUES P3-C19). The trigger is an undersized corpus: a
    # partial fetch, an interrupted download, a gated dataset that wrote nothing -- i.e. the single most
    # likely thing to go wrong on the very run that adds a second area.
    # AND THE CHECKPOINT USED TO RECORD `_env('DOMAINS','')`, so any run that did not set it stored an
    # empty area list. That is the defect the old knob registry was created for (:71).

    n_processes = Lever(4, "How many synthetic Markov processes the stream is generated from, on "
                          "DATA_SOURCE=synthetic only.", U.COUNT)
    # Census: N_PROCESSES -> DATA_N_PROCESSES, mis-tagged misc; the survey's so-config record says so.
    # SCOPED TO THE SYNTHETIC GENERATOR, DELIBERATELY. Read once at :539 into NP, which the real path
    # then OVERWRITES with `NP = len(CORP)` at :1148 -- so under DATA_MODE=real this knob has no effect
    # whatsoever while every banner still prints it as the run's configuration. That silent overwrite is
    # what must not carry over: on the real path the source count is the number of corpora that survived
    # the 5000-byte filter, which is DATA's own derived quantity (module header), and this lever must be
    # left alone rather than reused as a variable to write the answer into.

    # ==============================================================================================
    # 2. HOW THE STREAM IS CUT
    #
    # A segment is drawn from one area, appended, and the next segment is drawn from whoever the phase
    # allows. These three numbers decide how much settled material sits between two boundaries, which
    # is what every clustering instrument downstream is actually scoring.
    # ==============================================================================================

    seg_min = Lever(700, "Shortest spliced segment drawn from one area before the stream switches.",
                    U.BYTES)
    seg_max = Lever(1800, "Longest spliced segment drawn from one area before the stream switches.",
                    U.BYTES)
    # Census: SEG_MIN/SEG_MAX, filed under `domains` and owned by DATA -- read only inside build_stream
    # (`_rs.randint(_i("SEG_MIN", 700), _i("SEG_MAX", 1800))` at :1406 and again at :1410); the domains
    # package never sees them. THREE RESTATED DEFAULTS EACH, at :1406, :1410 and :5707, which is exactly
    # the multi-default failure L1 exists to end -- and :5707 is a WARNING computing what it thinks the
    # segment length is, so a run that changed the knob at only two of three sites would have been warned
    # about the wrong stream. One declaration, here, is the whole repair.
    # KEPT AS A PAIR, NOT MERGED INTO A MEAN: the two define a uniform draw, and the variability is what
    # stops the assembler learning a fixed splice period.
    # THE COUPLING THE REPORT ALREADY PRINTS, and the reason these are BYTES while the thing they are
    # compared against is TOKENS: at ~490 bytes per window, a 700-byte segment is 2.6 windows, of which
    # DOM's sustain=2 is spent detecting the boundary -- leaving well under one settled window per
    # segment, so the clustering scores describe the TRANSITIONS rather than the domains (:5707-5712).
    # The guard fires below 8 windows per segment and recommends >= 8x/20x the window in bytes. The
    # window belongs to LM (LM_CTX, tokens) and the conversion needs the MEASURED bytes/token, so this
    # coupling is irreducible and gets printed rather than wired.

    seg_contig = Lever(False, "Read each area in order instead of seeking to a random offset every "
                              "segment, so the only boundaries left are the text's own.", U.FLAG)
    # Census: SEG_CONTIG -> seg_contig. THE DEFAULT WAS COMPUTED AND THEREFORE CANNOT BE ONE:
    # `SEG_CONTIG = bool(_i("SEG_CONTIG", 1 if NP == 1 else 0))` at :1299 -- contiguous when exactly one
    # corpus survives, random when several. spine/lever.py refuses a computed default outright ("A value
    # derived from another lever is a WIRE, not a default"), and that refusal is right: the old form read
    # its input eagerly into the audit, which is the MAX_DOMAINS class of defect (O2).
    # THE LITERAL THE RUN ACTUALLY USED IS FALSE, on both shipped configurations: at the default
    # areas="eng,py,num,c" the real path has four corpora and the synthetic path four processes, so
    # `1 if NP == 1 else 0` resolved to 0 every time either default ran.
    # NOR IS IT A WIRE, and the census's own phrasing ("stays inside the package as a d_ field") is not
    # available: d_ is the CROSS-package namespace, lever.py refuses a d_-named lever, and an
    # intra-package derivation would enter the coupling graph as an edge from DATA to DATA. So the
    # derivation has to happen in the resolver, from the SURVIVING area count, and be printed.
    # PORT REQUIREMENT, AND IT IS NOT COSMETIC: a rebuild that hard-defaults False silently changes the
    # single-corpus goal-A configuration, which is the one where contiguity matters. seg_from seeks to a
    # random point every 700-1800 bytes, so an English-only stream jumps elsewhere in English every
    # 8-20 KB -- discontinuities WE manufacture at a spacing WE choose -- and the assembler then
    # discovers domains at our seek points. That is how eng_only reported 71 domains: it was partly
    # counting our splices (:1291-1298).
    # AND CARRY THE INSTRUMENT DEFECT WITH IT: boundary precision/recall is scored against every splice
    # START, including consecutive segments drawn from the SAME area, so on a single-area run with
    # seg_contig=1 there is not even a discontinuity at the points the instrument calls true switches
    # (:1407-1412 against :8481-8483). The knob is honest; the scorer that reads it is not, yet.

    stream_bytes = Lever(120000, "Bytes of stream one epoch draws from the areas.", U.BYTES)
    # Census: STREAM_LEN -> DATA_STREAM_BYTES. THE UNIT IS IN THE NAME BECAUSE THE MISSING UNIT IS
    # LOAD-BEARING. The survey record itself hedged ("bytes/tokens per epoch"); the run computes
    # `steps = STREAM_LEN // WIN` at :4317 and :4719, dividing a BYTE budget by a TOKEN window; and the
    # phase widths are `STREAM_LEN // len(PHASE_SCHED)`. It is the number that makes "EPOCHS=8" mean
    # anything, so it cannot be dropped -- it just has to stop being unit-free.
    # A CORPUS SMALLER THAN THIS DUPLICATES ITSELF, SILENTLY. build_stream draws segments until it has
    # this many bytes and stops; it never checks how many DISTINCT bytes exist. Ask for 94 MB an epoch
    # from a 58 MB corpus and you get 94 MB containing the same text ~1.6x over, with nothing in the log
    # to say so, and the fact is unrecoverable afterwards because the log never said (H15, :5473-5489).
    # That is what `exposure_max` and `exposure_skew` exist to state before the run starts.

    # ==============================================================================================
    # 3. THE PHASE SCHEDULE -- WHO IS LIVE, AND WHEN
    #
    # This is the continual-learning protocol. Not a parameter of it: the thing itself. It is also the
    # group where the old tree encoded one idea three ways -- an on/off flag, a generator with two
    # parameters, and an explicit override -- so that four call sites had to test two of them together
    # to work out what was running.
    # ==============================================================================================

    phase_sched = Lever("", "Explicit phase schedule, pipe-separated phases of comma-separated area "
                            "indices OR area names (\"0|0,1|0,1|1\", \"eng|eng|rust|rust\"); empty "
                            "generates a rehearsed sliding window from `phases` and `phase_live`.",
                        U.NAME)
    # Census: PHASE_SCHED, verdict keep, and it ABSORBS PHASED (the merge above). The parse-at-startup
    # shape is already right and is the model for the port: :1355-1366 refuses an empty phase or an
    # out-of-range area id loudly, at startup, rather than producing a silently different experiment.
    # D2 IS RULED (Q-DATA-7, 2026-09-02) AND THE DEFAULT BELOW DID NOT MOVE. Two things landed. First,
    # AN ENTRY MAY BE AN AREA NAME as well as an index, resolved against Areas.names at the parse site
    # and refused loudly on a name no area carries. That is what makes "the added area alone" WRITABLE
    # at any area count -- "rust|rust|rust|rust" -- which the paragraph below says no literal string
    # could express, and it removes the order-fragility longrun.sh:930-932 is living with (it hand-types
    # _AI=1 under a comment claiming the index is computed from DOMAINS, and nothing reads DOMAINS,
    # ISSUES P1-L2). Second, DATA.data_plan RECOGNISES the protocol from the resolved schedule -- four
    # written predicates, no generator, no new lever -- so Plan.protocol names explicit / generated /
    # stationary / pure_add on every run.
    # WHAT IS DELIBERATELY NOT DONE, AND THE OWNER IS OWED THE SENTENCE: empty still generates the
    # REHEARSED sliding window. The owner's ruling keeps pure-add as the protocol of the add-an-area
    # experiment, and it is kept -- as a schedule the launcher writes and the resolver NAMES. Flipping
    # this default to generate pure-add would stream ONE area at the shipped DATA_AREAS="eng,py,num,c"
    # and leave three declared corpora untrained without saying so, and a default whose shape changes
    # between n=2 and n=4 is M18 (a declared parent that is not the actual one) reproduced on the
    # protocol. The comparison arm is measurable either way and DATA.data_plan states the run that
    # settles it.
    # THE PARAGRAPH BELOW IS THE PRE-RULING RECORD AND IS KEPT BECAUSE ITS ARGUMENT IS WHY THE DEFAULT
    # STANDS. D2 (2026-08-28)
    # makes PURE_ADD the default protocol -- the added area streams alone. PURE_ADD is not and never was
    # a knob in self_organize.py (0 occurrences); it is longrun.sh shorthand that EXPANDS to
    # PHASE_SCHED="1|1|1|1", and it expands to that string only because that harness runs exactly two
    # areas. There is no literal string that means "the added area alone" independent of how many areas
    # there are, so encoding D2 as this lever's default would encode a two-area assumption as a global
    # default -- the same defect `phase_live` is being repaired for one declaration down. The default
    # stays the census literal (empty = generate), and D2 lands where the area count is known: on the
    # RESOLVER, which must produce the pure-add schedule for an add-an-area run and record on the Sample
    # which protocol ran. A run that wants the rehearsed comparison arm at two areas writes it out:
    # PHASE_SCHED="0|0|1|1" ([[0],[0],[1],[1]]). Recording this in the file rather than in the number is
    # deliberate: the two arms disagreed 10x on the same toy, so a default that quietly picks one is a
    # result the report cannot honestly attribute.
    # WHAT EMPTY GENERATES TODAY, so the gap between D2 and this default is on the page and not implied:
    # derive.phase_schedule(4) -> [[0,1],[1,2],[1,2],[2,3]] at the default four areas, which is a
    # REHEARSED sliding window, not pure add.
    # TWO DEFECTS TO CARRY, both from the census evidence rather than from the knob: (1) the phase fill
    # truncates and overshoots -- `per = STREAM_LEN // len(PHASE_SCHED)` at :1402 plus a whole 700-1800
    # byte segment past each bound -- so PH_BOUNDS drift and the stream comes out short (ISSUES P1-L22);
    # (2) the `[a for a in act if a < NP] or list(range(NP))` fallback at :1404 is unreachable dead code
    # (ISSUES P1-L18), and the parser at :1358-1361 is what makes it unreachable, so the port must not
    # reintroduce it as a safety net that quietly re-enables every area in a phase.
    # THE STATIONARY ARM IS EXPRESSIBLE ONLY EXPLICITLY -- see DEFECT 3 in the module header.

    phases = Lever(4, "How many phases the generated sliding-window schedule has, when no explicit "
                      "schedule is given.", U.COUNT)
    # Census: PHASES, verdict keep. Read once, at :1343, and only when PHASE_SCHED is empty -- narrow but
    # genuinely live, and it is the generator's one honest parameter.
    # KEPT RATHER THAN "JUST WRITE THE SCHEDULE OUT", because a hand-written schedule silently becomes
    # wrong when the area order changes, and the tree is living with that defect right now: longrun.sh
    # hand-types `_AI=1` under a comment claiming it is computed from the DOMAINS order, and nothing
    # reads DOMAINS (ISSUES P1-L2). The generator itself replaced a per-n lookup table for the stated reason
    # that a rule applies the same shape at any n (:1332-1336).
    # THE FLOOR OF TWO IS A PORT REQUIREMENT THIS DECLARATION CANNOT ENFORCE. The shipped resolution is
    # `p = p or max(2, _i("PHASES", 4))` (:1343) and spine/derive.py::pin_tick says in as many words that
    # the floor "belongs on the lever declaration" -- but `choices=` enumerates a closed set and cannot
    # express "any integer >= 2". spine/lever.py::Lever's `domain=` CAN state exactly that, as
    # (2, None) -- this declaration does not carry one because populating it was not this pass's
    # list, and an unpopulated interval is not a check. So the guard lives at the read
    # site, and the reason it must exist is concrete: one phase cannot have anything fade, and `faded` is
    # computed off the last phase, so PHASES=1 makes the unlearn-a-faded-area test skip itself as
    # vacuous -- a test that reports passing because it had nothing to check.
    # AND DO NOT REPRODUCE THE ALIASING: the shipped n<=1 path returned `[[0] if n else []] * p`, which
    # is p references to ONE list (ISSUES P1-L23). derive.phase_schedule builds independent lists and is
    # equal by value to the oracle; the difference appears the moment anyone mutates a phase.

    phase_live = Lever(0, "How many areas are live in each phase of the GENERATED schedule; 0 derives "
                          "it from the area count.", U.COUNT)
    # Census: PHASE_W -> DATA_PHASE_LIVE. RENAMED BECAUSE "W" READS AS A WIDTH IN BYTES OR WINDOWS and it
    # is a count of AREAS -- the same ambiguity class that produced the byte/token faults in this family.
    # THE DEFAULT WAS COMPUTED, AND ITS DECLARED PARENT WAS WRONG -- which is the census catching itself.
    # The old _DERIVED table says PHASE_W follows PHASES (:91, "window width follows the phase count"),
    # while the code reads `w = w or max(1, min(n, _i("PHASE_W", (n + 1) // 2)))` at :1345 where n is the
    # AREA count (ISSUES P1-M18). So changing PHASES left it untouched, and losing a corpus to the
    # 5000-byte drop filter silently changed the schedule SHAPE. A declared-vs-actual parent mismatch is
    # exactly what spine.derive's replay table exists to make impossible.
    # 0 IS A SENTINEL, NOT A VALUE, and it is the literal that keeps the derivation where it belongs.
    # THE LITERAL THE RUN ACTUALLY USED WAS 2 -- (4 + 1) // 2 at the default four areas -- but declaring
    # 2 here would FREEZE the width at 2 for every area count and reproduce M18 from the other side:
    # add a fifth area and the schedule shape stops following it, silently. spine/derive.py::pin_tick.held resolves
    # `width or max(1, min(n_areas, (n_areas + 1) // 2))`, so a falsy value routes to the derivation the
    # spine already owns and replays against the oracle. Any positive value overrides it -- and note that
    # a caller-supplied width is NOT clamped to n_areas by that first expression, only by the
    # `>= n_areas` line below it (derive.py::pin_tick.held), which reproduces the shipped behaviour exactly.
    # UNIT: this counts AREAS. units.py has no AREAS constant and U.DOMAINS means DOM's partition cells,
    # which is the collision `areas` was renamed to avoid, so it carries U.COUNT and says so here.
    # Adding an AREAS label is a spine edit, not a data edit.

    # ==============================================================================================
    # 4. WHAT IS HELD BACK, AND WHETHER THE MEASUREMENT MEANS ANYTHING
    #
    # Every number goal B rests on -- the memorization check, the anchors, ACROSS THE RUN BOUNDARY,
    # retention -- is computed on this split. The two exposure levers below are the only things that
    # say whether the held-out score is a measurement of generalisation or of repetition.
    # ==============================================================================================

    holdout_frac = Lever(0.05, "Fraction of each area held out and never sampled into the training "
                               "stream.", U.FRACTION, domain=(0.0, 1.0))
    # DOMAIN (0.0, 1.0) -- A FRACTION OF A BODY, SUBTRACTED FROM THAT SAME BODY.
    # src/data/api.py::open_areas computes `int(len(blob) * float(dat.holdout_frac))` and trains on
    # `len(blob) - n_hold`, so the number can only name bytes that exist: above 1.0 it asks for more
    # held-out bytes than the area has, and below 0.0 it asks for a NEGATIVE block, which reached
    # the 0-byte refusal with arithmetic that refusal's own message misreports -- measured at -0.5
    # over a 2 MB area: "min(int(2000000 * -0.5), 4000000) == 0", where the min is -1000000. That
    # route is closed HERE rather than there, and the message is left to its owner. 1.0 stays inside
    # and is the whole area held out; open_areas then refuses THAT by the usable-bytes floor, with
    # the area's own numbers. 0.0 is a legal spelling refused per area by the same function -- "raise
    # DATA_HOLDOUT_FRAC or DATA_VAL_CAP" -- wherever a block is carved: on a real source, and since
    # 2026-09-27 on the synthetic one at DATA_SYNTH_HOLDOUT=1 (whose refusal names that lever too). At
    # DATA_SYNTH_HOLDOUT=0 the synthetic arm holds nothing out and this lever is inert there (Q-DATA-9).
    # Census: VAL_FRAC -> DATA_HOLDOUT_FRAC. Renamed to the word the report already prints: "VAL" appears
    # nowhere in the output this produces (G12). Read at :1165 and applied at :1167-1172.
    # THE DEFECT TO CARRY IS IN THE SPLIT, NOT THE FRACTION. The last 5% of a corpus is a SAMPLE only if
    # the corpus was written in no particular order. Corpora written in ARRIVAL order from a dataset that
    # arrives ordered -- the-stack by repository, C4 by crawl -- put a contiguous block of whichever
    # documents came last on the held-out side, and the headline becomes a measurement of those
    # documents. Measured, on the run that added the-stack's Python: py held out at 5.061 +/- 0.560
    # against 2.922 in-stream, while eng (fineweb-edu, shuffled upstream) was 2.273 against 2.303. The
    # gap was the ORDERING, and the run reported it as a property of Python (:1173-1198).
    # THE REBUILD TAKES A SEEDED RANDOM HOLDOUT and records the choice on the Sample. The shipped
    # mechanism is a fetcher flag plus a warning -- it reads _fetch_manifest.json and prints if
    # shuffle_buffer is 0, and prints NOTHING when there is no manifest, which "says nothing either way,
    # so claim nothing" (:1189-1190). A measurement whose validity depends on a file that may be absent
    # is not a measurement the report can stand behind.

    synth_holdout = Lever(True, "DEFAULT BEHAVIOUR CHANGE 1 (register 04-Q5, on since 2026-09-29): hold "
                                "out a block per area on DATA_SOURCE=synthetic, under the real sources' "
                                "law: min(DATA_HOLDOUT_FRAC x body, DATA_VAL_CAP) bytes, a seeded "
                                "contiguous block removed from the body. Off, the synthetic source holds "
                                "nothing out, as it did before; a run that pairs with one from before "
                                "the change pins it to 0.", U.FLAG)
    # CENSUS AMENDMENT, 2026-09-27 (Proposal 04's SR0, register 04-Q5, Proposal 05 §8 3.1; ruled in
    # docs/04_CONTRACT.md Q-DATA-9). No ancestor: the old synthetic generator held nothing out and had
    # no switch over it, so there is no (family, old_name) key and N2 is satisfied by an amendment row.
    # ONE LAW FOR BOTH SOURCES, NOT A SECOND ONE. At 1, data/api.py::open_areas runs the real sources'
    # carve on each generated body verbatim: the size min(int(body x holdout_frac), val_cap), the start
    # from rng_for("data.holdout.<key>", seed) -- one child stream per area, keyed by name (Q-DATA-6)
    # -- the block REMOVED from the body, its seam and its overlap reading, the val-cap tally, and the
    # 0-byte refusal. The judge's variant (generate the held-out text from a separate rng child and
    # leave the body whole, so the stream does not move) was rejected in SR0: it is a second holdout
    # law, and its block is a continuation drawn after the body rather than a sample of it.
    # BUILT OFF, AND 04-Q5 RULES IT ON: ON SINCE 2026-09-29, THE STAGE'S LAST COMMIT AND ITS ONLY
    # DEFAULT CHANGE BESIDE THE PROBE'S AND THE BOOK'S (Q-DATA-9's dated note). At 1 every synthetic
    # area trains on a body a block shorter, so the stream every default run draws changed there and
    # no run before the change pairs with one after it; the flip therefore landed last and alone,
    # after SR0's bit-identity (§8 3.1), and a fleet that pairs with earlier runs pins it to 0 beside
    # EVAL_RETENTION_EVERY=0 and DATA_TRUST=off (04-Q5's pin rule: gpu_world.sh's EXP=retok and its
    # resume line carry the three; tests/test_baseline.py holds the pre-change records to this tree
    # under them). At 0 the synthetic branch runs the statements it ran before this lever existed, in
    # order, and mints no data.holdout child.
    # THE RESUME RULE (restore_stream_state). A checkpoint whose record for an area is key None and
    # size 0 -- what a synthetic run at 0 writes -- is ADMITTED against a synthetic block now, counted
    # per area in data.holdout_admitted; the parent trained on those bytes, so an admitted block is
    # text the lineage has seen. The reverse (a block then, none now) is refused naming this lever and
    # DATA_SOURCE=real, the two settings that write a block, and the same record against a REAL
    # block, a change of source, stays refused. A CONTINUING mid-epoch resume across an admission is
    # refused by the root, because the redrawn stream is not the one the parent was reading.
    # ONE LAW, ON A GENERATED BODY (2026-09-27, Q-DATA-9's review). At 1 the block rides on the area's
    # generated body: its length is max(DATA_SEG_MAX + 1, 5000, DATA_STREAM_BYTES // DATA_N_PROCESSES)
    # x 2, which every area shares, and its text is the alphabet the area's position in DATA_AREAS
    # picks. So along a lineage at 1 those three levers keep the parent's length and the parent's
    # areas keep their positions -- an add-an-area resume appends the area and raises
    # DATA_STREAM_BYTES with DATA_N_PROCESSES -- and the admission holds only where both are the
    # parent's. restore_stream_state refuses every other move by name, and the record carries each
    # block's digest, so a text that moved under agreeing offset, size and key is refused too.
    # A BOOL, WITH THE BOOL BRANCH'S KNOWN HAZARD (see `resample`): DATA_SYNTH_HOLDOUT=flase reads as on,
    # which at the shipped True is the default, so a misspelt pin to 0 is silent -- spell it 0.

    val_cap = Lever(4000000, "Maximum bytes of held-out tail kept per area.", U.BYTES)
    # Census: VAL_CAP -> DATA_VAL_CAP, mis-tagged misc, and the row the adversarial reviewer cites by
    # name as an instance of the doubled-name defect (DEFECT 1 in the module header).
    # IT APPLIES ON BOTH PATHS NOW, AND THAT IS THE FIX. Read at exactly one site, :1168, inside the
    # DISK_STREAM branch only -- so on the disk path the held-out set is the tail truncated to 4 MB while
    # on the RAM path it is the ENTIRE holdout_frac tail (:1170). ISSUES P1-M82, stated exactly: "every
    # held-out number is computed over a different amount of text depending on a knob that is nominally
    # about where bytes live" (M81 and M83 are the same root; the quoted sentence is M82's). The
    # memorization check, the
    # anchors and ACROSS THE RUN BOUNDARY were therefore computed over different amounts of text in two
    # configurations that differ in paging, and nothing in either report said which.
    # WHAT LEAVES THIS PACKAGE IS THE RESOLVED SIZE, NOT THE CAP -- AND NOT AS A WIRE. The census asks for
    # the held-out byte count to reach EVAL as a wire so the Sample can state how many bytes it actually
    # covered. docs/04_CONTRACT.md section 0's refused-wires table REFUSES that wire
    # (EVAL.d_holdout_bytes) and gives the reason -- cited by section, not by line, for the reason the
    # header gives at the same claim: the
    # size depends on bytes on disk, so build() would have to stat the corpus, and wiring this ceiling
    # instead would print the cap as the size. It travels as an argument and is recorded on the Sample.
    # This comment claimed the wire was declared in spine.assemble; grep finds no such coupling, and the
    # refusal is structural rather than an omission (Q-DATA-6, 2026-09-02).

    exposure_max = Lever(2.0, "Whole-run repetition multiple (bytes drawn x epochs / bytes on disk) "
                              "above which the data plan is flagged before training starts.", U.COUNT)
    # Census: EXPOSURE_MAX, verdict keep, and it is explicitly the not-dropped case: it has never been
    # observed to fire, and the reason is the INSTRUMENT rather than the mechanism. Both reads (:5535,
    # :5538) sit inside `if DATA_MODE == "real" and NP > 1` at :5497, so the whole-run repetition check
    # is unavailable on exactly the single-area configuration goal A runs in -- which is where accidental
    # repetition is EASIEST to reach, since one corpus plus a large stream_bytes is the default way to
    # hit it (ISSUES P1-L21, :2091). The quantity is perfectly well defined at one area.
    # PORT REQUIREMENT: move the read out of the NP>1 guard, and print the arithmetic as a declared Gate
    # (G4) so "did not fire" is distinguishable from "could not fire". A guard that cannot trip reads
    # exactly like a healthy run.
    # UNIT: a MULTIPLE (bytes drawn / bytes on disk), which is why it is U.COUNT and not U.FRACTION --
    # a 2.0 printed as "fraction 0..1" in docs/04_LEVERS.md is a label its own default falsifies. This
    # matches the call the domains and fabric files made on their multipliers; units.py has no MULTIPLIER
    # constant and adding one is a spine edit.
    # WHY EXPOSURE IS A WHOLE-RUN QUANTITY AND WAS FIRST WRITTEN PER-EPOCH: 60 MB of English beside 8 MB
    # of Python draws 2.00 MB/epoch from each -- under the cap, quiet, fine -- while over EPOCHS=8 that
    # is 16 MB drawn from 7.6 MB of Python against 16 MB drawn from 57 MB of English. The added area is
    # seen 2.1x over while the original is 28% sampled, and "adding py cost eng X bits/byte" is then
    # confounded with "py was memorised and eng was skimmed" (ISSUES P3-H22, self_organize.py:5490-5496).
    # nan AND +inf ARE REFUSED AT THE READ SITE, data/api.py::data_plan, together with exposure_skew
    # below. Neither is a declared meaning here -- this help text says only "above which the data
    # plan is flagged", and there is no inf branch in data/api.py. What they DID, measured before the
    # refusal landed: `max(vals) > nan` is False for every possible exposure and no finite exposure
    # exceeds +inf, so the gate could not fire and printed the middle state anyway --
    # "Gate data.exposure_max: armed, did not fire (0.75 vs nan)" and "(0.75 vs inf)". A guard that
    # cannot trip reads exactly like a healthy run, which is the sentence three lines above this one
    # about the NP>1 defect, arriving a second time through the threshold instead of the guard.
    # 0 AND -inf ARE NOT REFUSED and are not sentinels either: both make the gate FIRE on every plan
    # -- measured, "FIRED (0.75 vs 0.0)" and "FIRED (0.75 vs -inf)" -- and both print the truth while
    # doing it, so refusing them would remove a configuration that behaves and reports correctly.
    # THE REFUSAL CLOSES TWO VALUES AND NOT THE CLASS: DATA_EXPOSURE_MAX=1e26 is finite, passes it,
    # and is exactly as uncrossable as +inf while printing as an ordinary number. A declared
    # per-lever domain is the general answer and it is the owner's open question.

    exposure_skew = Lever(3.0, "Max/min exposure ratio across areas above which the data plan is "
                               "flagged as imbalanced.", U.COUNT)
    # Census: EXPOSURE_SKEW, verdict keep. A DISTINCT QUANTITY FROM exposure_max -- imbalance BETWEEN
    # areas, not repetition of one -- so it is not a merge candidate however similar the names look.
    # IT IS THE ADD-AN-AREA CONFIGURATION'S DEFAULT PATHOLOGY, and therefore the guard that stands
    # closest to the goal-B headline: the areas get the same SHARE of the stream at very different SIZES,
    # the added area is always the small one, and what looks like the new area displacing the old is
    # partly the new area having been memorised (:5544-5556). D3's reservoir quota addresses the same
    # dilution one package over, in MEM.
    # ITS NP>1 GUARD IS HONEST, unlike its sibling's: a max/min ratio over one area is undefined. L21's
    # inertness finding applies to exposure_max, not to this. Same Gate treatment though -- the report
    # must state the ratio it computed and the areas it compared, or "no warning" is unreadable.
    # nan AND +inf ARE REFUSED AT data/api.py::data_plan, on the same reasoning as exposure_max above
    # and with the same measurements: "Gate data.exposure_skew: armed, did not fire (3.0 vs nan)" and
    # "(3.0 vs inf)" against "FIRED (3.0 vs 0.0)" and "FIRED (3.0 vs -inf)" at the two values left
    # alone. THE DISTINCTION THIS LEVER MAKES THAT ITS SIBLING DOES NOT, and it is why the refusal is
    # a refusal rather than a reachable=False: this gate ALREADY has a declared unreachable arm, at
    # n_areas == 1, and that one is STRUCTURAL -- a max/min ratio over one area is undefined and no
    # lever can change it. A threshold nothing can cross is an out-of-range value the operator typed,
    # which is a different statement, and folding the two into one rendering would put a lever fault
    # and a shape fact under the same word.
    # UNIT: a RATIO of two exposures, U.COUNT for the same reason as exposure_max.

    # ==============================================================================================
    # 5. WHAT HAPPENS BETWEEN EPOCHS
    # ==============================================================================================

    resample = Lever(False, "Redraw a fresh stream from the areas at the start of every epoch instead "
                            "of replaying the same bytes.", U.FLAG)
    # Census: DISK_STREAM -> DATA_RESAMPLE. TWO DIFFERENT THINGS LIVED IN ONE KNOB AND ONLY ONE OF THEM
    # IS A LEVER.
    # THE HALF KEPT is per-epoch resampling: _resample() runs only inside `if DISK_STREAM` (:6511-6521),
    # so at 0 every epoch is a BYTE-IDENTICAL REPLAY -- the run says so itself at :5470-5472 -- and that
    # is a real experimental choice with real consequences, since resampling also fires
    # fabgrow.note_shift, clears _sigq and arms LR_SHIFT_WARM.
    # THE HALF DROPPED is the mmap/paging choice, because it silently changed WHAT THE HELD-OUT SET IS
    # (see val_cap). Paging is an internal decision driven by corpus size and must be invisible to every
    # measurement. This is a wrong-MEASUREMENT removal, not a mechanism removal, and the distinction
    # matters: nobody argued the mmap path was useless, only that it must not be able to change a number.
    # DECLARED False, NOT 0, like every other flag in this tree. The bool default selects the coercion
    # branch in Lever.coerce, so DATA_RESAMPLE=off means off; with an int default it raises. The honest
    # cost is the spine's for every bool and not a choice made here: any string outside
    # ("0", "", "off", "no", "none", "false") reads as True, so DATA_RESAMPLE=flase is silently on.

    draw = Lever("planned", "How a phase's bytes are allocated across its areas: 'planned' gives "
                            "each live area its scheduled share, 'uniform' picks an area per "
                            "segment, and 'replay' also gives each faded area a fixed share. Under "
                            "'planned' only the order and the offsets are random; under 'replay' a "
                            "phase with a faded area gives them DATA_REPLAY_SHARE of its bytes, "
                            "spread through the phase, and every other phase is 'planned'.",
                 U.NAME, choices=("planned", "uniform", "replay"))
    # AMENDMENT, 2026-09-02, ruled by the owner under ISSUES P1-H58. NO ANCESTOR KNOB: the old tree had
    # one law, `_r.choice(act)` per segment, and no switch over it.
    # 'replay' JOINED THE CHOICES 2026-09-28 (Proposal 04 §1 item 2 and SR0; register 04-Q1, O16,
    # Proposal 05 §8 3.3; docs/04_CONTRACT.md Q-DATA-10), BUILT OFF. It is the hand-set rehearsal
    # control the self-regulated draw has to beat: each phase with a faded area gives
    # `replay_share` of its bytes to its faded areas, split evenly, and the rest to its live areas,
    # laid by DEFICIT (at each segment, the area furthest behind its target share of the phase's
    # bytes so far, ties in Plan order) and truncated to the area's per-phase target, so the
    # realised split is the planned one exactly. 'retention', the self-regulated draw, is SR2's and
    # is not a choice until it is built.
    # THE MEASUREMENT THAT MADE IT A LEVER. DATA.data_plan computes `per_area_draw` by distributing
    # stream_bytes across the schedule and tests exposure_max / exposure_skew against it, under a
    # docstring saying it computes what the run "will actually" be exposed to. Under the old law
    # draw_stream then picked an area UNIFORMLY AT RANDOM per segment, so the run trained on a DRAW
    # from that distribution rather than the distribution: measured over eight seeds at the shipped
    # defaults, the worst per-area deviation was 47.9% (seed 0: planned eng 15,000 / py 45,000,
    # realized 14,396 / 42,499). A gate that reads "armed, did not fire" on a planned split while the
    # realized split crossed its threshold is a true sentence about the wrong number -- in the
    # instrument whose whole job is catching P3-H22, where an added area seen 2.1x while the original
    # was 28% sampled made "adding py cost eng X b/B" indistinguishable from "py was memorised and eng
    # was skimmed".
    # WHY "planned" IS THE DEFAULT AND NOT THE OTHER WAY ROUND. It is the only value under which the
    # startup gate is EXACT, and a startup gate is the only thing that can refuse a bad configuration
    # BEFORE it spends the GPU time. Defaulting to the law that makes the guard approximate would keep
    # the instrument and throw away the guarantee. (2026-09-28: 'replay' is exact the same way -- it
    # truncates every segment to its area's per-phase target as 'planned' does -- and it is built OFF.
    # 'planned' stays the default by the owner's D8 until a GPU reading says otherwise: register O16,
    # §8 5.3's 'replay' 0.27 against 'planned' pair, whose confirming reading goes to the owner.)
    # WHAT "uniform" IS FOR, because it is kept and not dropped: it is the law every recorded result in
    # this project was taken under, so it is the arm that reproduces them. The owner's standing rule is
    # that a mechanism kept for future use is kept with a switch.
    # THE PAIRED INSTRUMENT is Stream.per_area_drawn beside Plan.per_area_draw: under 'planned' and
    # 'replay' they agree EXACTLY, per area (this line said "to within one segment per area" until
    # 2026-09-28, which the planned law's truncation to each area's budget had already made an
    # understatement), and under 'uniform' the difference is the error bar on every exposure number
    # the run reports. The gates say which law produced them. Since 2026-09-28 the same pair is also
    # printed PER PHASE under every law, as Stream.counters' share gauges
    # (data.share.p<k>.<area>.planned / .realised, in permille of the phase).

    replay_share = Lever(0.27, "Share of each phase's bytes the 'replay' draw gives the areas faded in "
                               "that phase, split evenly among them; read only at DATA_DRAW=replay.",
                         U.FRACTION, domain=(0.0, 1.0))
    # CENSUS AMENDMENT, 2026-09-28 (Proposal 04 §1 item 2; register 04-Q1 and O16, Proposal 05 §8 3.3;
    # docs/04_CONTRACT.md Q-DATA-10). No ancestor: the old tree had no rehearsal law at all.
    # THE FADED SET IS DATA's OWN, known at startup: Plan.faded[k], every area live in an earlier
    # phase and not in phase k (Q-FAB-18), and -- at `rehearse_parent` -- Plan.parent_faded from
    # window 0. A phase with no faded area is laid by the 'planned' law, verbatim, and this share is
    # not read for it. THE BYTES ARE EXACT, NOT EXPECTED: data_plan rounds `replay_share` x the
    # phase's span to whole bytes (half to even, on the decimal the operator wrote, so 0.27 is 27/100
    # and not its binary neighbour), splits them evenly with the remainder on the first in Plan
    # order, and draw_stream truncates each segment to its area's per-phase target, so the realised
    # split is the planned one byte for byte and the exposure gates stay exact (04 §1 item 2).
    # 0.27 IS A TOY VALUE AND PROVISIONAL (register NEW-19): it matches the self-regulated arms'
    # measured last-phase rehearsal share on the d3 toy, and 0.2 was measured worse there; the E1
    # secondary reads 0.15 / 0.27 / 0.40 if 'replay' ever becomes a default (04-6-UNMEASURED (h)).
    # DOMAIN (0.0, 1.0): a share of a phase's bytes. 1.0 gives a faded phase wholly to its faded
    # areas; `replay_share` + `replay_newest` above 1 is refused at data_plan by name, because no
    # phase can give away more bytes than it has. At 0.0 -- or a share that comes to no byte in a
    # phase -- the faded phase gives its faded areas nothing and is still laid by deficit over its
    # live areas: Gate data.replay counts only the phases that give a faded area a byte, and reads
    # armed-but-zero with the reason naming the rest (Q-DATA-10's review; it read FIRED there).

    replay_newest = Lever(0.0, "Share of each faded phase's bytes the 'replay' draw gives the "
                               "newest-arrived live area, the other live areas splitting what is "
                               "left evenly; 0 is off. Read only at DATA_DRAW=replay.",
                          U.FRACTION, domain=(0.0, 1.0))
    # CENSUS AMENDMENT, 2026-09-28 (Proposal 04 §1 item 2 and R-3; register 04-Q1 note (d);
    # docs/04_CONTRACT.md Q-DATA-10). No ancestor. It is the critic's `replay_late` control exactly:
    # at 0.34 over five live areas the newest takes 0.34 of a faded phase and each of the other four
    # (1 - 0.27 - 0.34) / 4 = 0.0975. It exists because the self-regulated draw's newest-area gain
    # was measured to be EXPOSURE, and a hand-set boost reproduced it (04 §2 row 8), so E1 needs the
    # boost as an arm of its own. OFF at 0 (04's table), and 0.34 is an E1 arm value, not a default.
    # "NEWEST-ARRIVED" IS READ OFF THIS RUN'S SCHEDULE: among the phase's live areas, the one whose
    # first live phase is latest, ties to the last in Plan order (an add-an-area run appends its new
    # area, Q-DATA-9). A faded phase whose only live area is the newest gives it the whole live
    # remainder, 1 - `replay_share`, and the boost moves nothing there. Applied only in phases the
    # 'replay' law lays; a phase with no faded area is 'planned' and reads no share.

    rehearse_parent = Lever(False, "At DATA_DRAW=replay, count the areas the resumed lineage drew and "
                                   "this schedule makes live in no phase as faded from window 0, so "
                                   "the draw rehearses them; no effect under 'planned' or 'uniform'.",
                            U.FLAG)
    # CENSUS AMENDMENT, 2026-09-28 (register 04-Q4 and O9, Proposal 05 §8 3.3; docs/04_CONTRACT.md
    # Q-DATA-10). No ancestor: the old tree had no parent record to read. Without it a pure-add
    # child has nothing faded -- its own schedule never had the parent's areas live -- so no draw
    # can protect what the parent learned (04-Q4). The set is Plan.parent_faded, which Q-FAB-18
    # reads off Areas.drawn: an area this run declares, that the lineage's streams drew, and that no
    # phase of this schedule makes live. A DECLARED AREA IS NOT A DRAWN ONE, so an area a parent
    # declared and never trained is not rehearsed -- WHERE THE RECORD CAN SAY (Q-DATA-10's review):
    # a record older than the drawn list cannot, every area it declares is held drawn by assumption
    # (Areas.drawn_assumed, carried down the lineage until a draw confirms it), and such an area is
    # rehearsed with data.rehearse_parent's reason naming it. BUILT OFF, AND OFF IN EVERY TRAINING AND
    # MEASUREMENT RUN (O9: D2 stands, pure-add is the unprotected measurement arm); the unbuilt
    # continue preset carries True with 'replay' 0.27, provisional until §8 5.3. The area's body is
    # this run's, as every declared area's is (its corpus on disk, or its generated text on the
    # synthetic source); a recorded parent area this run does not declare is refused at
    # restore_stream_state, because the replay reservoir that would carry it in the checkpoint
    # (NEW-06, register §8 4.5) is not built. ON THE SYNTHETIC SOURCE THE GENERATED TEXT IS THE
    # PARENT'S ONLY AT THE PARENT'S POSITION IN DATA_AREAS AND AT ITS RUN_SEED (Q-DATA-10's review):
    # a rehearsed area whose position moved is refused at data_plan, and RUN_SEED, which no record
    # carries, is the operator's to keep.
    # A BOOL, WITH THE BOOL BRANCH'S KNOWN HAZARD (see `resample`): DATA_REHEARSE_PARENT=flase reads as
    # on.

    corpus_cap = Lever(2000000, "Bytes read from disk per area before any holdout split or stream "
                                "draw; the ceiling on how much of a corpus this run can see.", U.BYTES)
    # Census: CORPUS_CAP, verdict keep. GENUINELY DISTINCT FROM stream_bytes: one caps what is OPENED,
    # the other caps what is DRAWN. Read once at :1124 into datastream.open_corpus (datastream.py:34-36,
    # 78-81), where it bounds the disk read on both the mmap and the RAM path.
    # THE DEFAULT IS THE MOST EXPENSIVE TRAP IN THE TREE AND IT IS DECLARED HERE UNCHANGED, ON PURPOSE.
    # 2,000,000 bytes per area means a multi-day run trains on 2 MB per area no matter what is on disk.
    # ISSUES P1-H8 and M15 both record SHIPPED scripts that ask for more than the cap allows
    # (run_full_unfrozen.sh PART B, run_cl_test.sh part 3: a 6 MB / 2 MB stream against a 2 MB
    # per-area cap); preflight.sh's own header lists "a multi-day run that would have trained on 2 MB"
    # as a known past failure; and self_organize.py:5616-5618 warns about ITS OWN DEFAULT -- a knob whose
    # shipped value is wrong often enough that the program apologises for it at startup.
    # WHY IT IS STILL 2000000: L1 says the declared default is the literal the run used, and the census
    # records it. The census also recommends the fix in the same row -- "New default should be 0 = read
    # what is on disk, with the audit comparing the cap against the bytes actually present" -- and that
    # is a DECISION, not a transcription: 0 must first mean "no cap" at the read site (today it would
    # mean "read nothing"), and open_corpus must report bytes present beside bytes taken so the audit can
    # compare them. Changing the number here before that read site exists would replace a loud, warned
    # trap with a silent one. Recorded as the open item it is.

    # ==============================================================================================
    # 6. WHICH SOURCES THE STREAM CAN BELIEVE -- THE SOURCE-RELIABILITY BOOK (Proposal 04 §1 item 8)
    #
    # Fourteen CENSUS AMENDMENTS, 2026-09-28 (Proposal 04 SR3; register 04-6.3 and §8 3.4;
    # docs/04_CONTRACT.md Q-DATA-11). None has an ancestor: the old tree kept no book of which source
    # to believe. The book reads the TEXT the stream trains on -- the claims its sources make about
    # one key, and who disagrees with whom -- and never a model output or a loss, so no fluency can
    # game it and nothing the model computes can move it (04 §1 item 8's "reason for the book").
    # EVERY VALUE BELOW BUT `trust` IS 04 §6's AND PROVISIONAL (register NEW-19): the testbed tuned
    # them, and nothing has measured them on real text -- E3 (register §8 6.2) is that measurement.
    # ==============================================================================================

    trust = Lever("observe", "DEFAULT BEHAVIOUR CHANGE 3 (register 04-6.3, 'observe' since 2026-09-29): "
                             "the source-reliability book, 'observe' reading every source's claims, "
                             "voting, and reporting each source's reliability and trust while changing "
                             "nothing the run trains on; 'off' keeps none; 'loss' and 'loss+draw' would "
                             "weight the loss (and the draw) by that trust and are declared, NOT BUILT.",
                  U.NAME, choices=("off", "observe", "loss", "loss+draw"))
    # CENSUS AMENDMENT, 2026-09-28 (Proposal 04 §1 item 8 and SR3; register 04-6.3, §8 3.4;
    # docs/04_CONTRACT.md Q-DATA-11). BUILT 'off', AND 'off' IS THE WHOLE BOOK ABSENT: DATA.new_focus
    # allocates nothing, the loop's arm test withholds every DATA.claims_observe call before the
    # 'data.trust' gate is asked, and no data.trust.* key exists -- so a run at 'off' trains as this
    # tree before the book did, bit for bit (SR3's bit-identity, tests/test_trust.py); what it
    # prints beside -- the DATA(trust) row, the ledger key, the cadence audit's one startup line --
    # is Q-DATA-11's "What the default changes". 04-6.3 rules 'observe' ON after that bit-identity,
    # and the flip landed last and alone: 'observe' SHIPS SINCE 2026-09-29 (Q-DATA-11's dated note).
    # What a default run pays for it: the book's passes (6-7% of wall on the toy, owed at the owner's
    # shape under E3's 2% rule, §8 6.2) and, in every checkpoint, the int32 sketch -- DATA_TRUST_SKETCH
    # buckets, 16.8 MB at 4194301. Training numbers are unchanged (SR3's bit-identity). A run that pairs
    # with one from before the change pins 'off' beside DATA_SYNTH_HOLDOUT=0 (04-Q5's pin rule).
    # 'loss' AND 'loss+draw' ARE REFUSED AT STARTUP WITH spine/gate.py::NotBuilt (OPT_LR_CONTINUE=
    # 'regulated' is the precedent): each needs DATA.token_weights and LM.lm_loss(token_weights=),
    # which this tree does not build, and 04-6.3's standing rules forbid either as a default before
    # copy detection passes E5's majority-false and 50%-impersonation worlds -- it is BUILT since
    # 2026-09-28, OFF (DATA_TRUST_COPY, section 6b; Q-DATA-12), and §8 5.12 is its deciding run --
    # and while a truthful source in another format is floored. A run labelled with an actuation that
    # never happened is refused rather than run as 'observe'.

    trust_rule = Lever("claims", "Which estimator fills the book: 'claims', the model-free "
                                 "reliability-weighted vote over the (key, value) claims sources "
                                 "make; the only one built.", U.NAME, choices=("claims",))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). One choice today. 04 §1 item 8 names three more as
    # ablation rule values -- 'peer' (d1's gradient-consistency trust), 'residual' (d3's calibration
    # residual, measured harmful) and 'fluency' (trust by low loss, the gaming demonstration) -- and
    # each is SR5's to build; a name that is not built is not a choice, as 'retention' is not yet a
    # DATA_DRAW value. Read only at DATA_TRUST != 'off'.

    trust_claim = Lever("kv", "What counts as one claim: 'kv' a normalised (key, value) pair around a "
                              "DATA_TRUST_DELIMS delimiter, 'ctx' a raw DATA_TRUST_CTX-unit context "
                              "and the unit after it.", U.NAME, choices=("kv", "ctx"))
    # CENSUS AMENDMENT, 2026-09-28 (Proposal 04 §1 item 8, R-5; Q-DATA-11). 'kv' IS THE BUILD TARGET
    # AND IS UNPROTOTYPED: the key is up to DATA_TRUST_CTX TOK units before a delimiter, case-folded,
    # punctuation stripped and whitespace collapsed, so `@EEE=V;` and `@EEE:V;` are ONE claim and a
    # surface form no longer decides agreement. E5's format-variant world is its acceptance test.
    # 'ctx' IS d3's PROTOTYPE, KEPT AS AN ARM, AND IT MEASURES CONFORMITY TO THE MAJORITY'S SURFACE
    # FORM, NOT TRUTH: on the testbed K = 5 is len('@EEE='), the known answer was tuned to the record
    # format, and a truthful source writing `@EEE:V;` was floored (r 0.001, t 0.3) at 2 of 2 seeds.
    # Changing it on a resume is refused by name: the table's keys are the rule's.

    trust_ctx = Lever(5, "Key length in TOK units: the most units before a delimiter a 'kv' key "
                         "reads, or the context length of a 'ctx' claim.", U.TOKENS, domain=(1, None))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). IN TOK UNITS, NOT BYTES (04 §6): after minting five
    # units span more than five bytes, so the testbed's known answer (K = 5 = len('@EEE=')) does not
    # port to the tree, and the critic's K sweep -- K 3 floors a harmless area, K 8 finds 0
    # conflicted claims through step 500 -- was measured in bytes on byte-level text.
    # DOMAIN (1, None): a key of no unit is no key. Changing it on a resume is refused by name.

    trust_val = Lever(1, "Value length in TOK units: how many units after a 'kv' delimiter the "
                         "value reads, cut at the first punctuation or delimiter.", U.TOKENS,
                      domain=(1, None))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). 'kv' only; a 'ctx' claim's value is always the one
    # unit after its context. At one BYTE-level unit a spaced form -- `x = 5` -- reads the space as
    # its value, which normalises to nothing and makes no claim; after minting, ` 5` is likelier one
    # unit. Stated, not tuned: 04 §6's value is 1. DOMAIN (1, None). Changing it on a resume is
    # refused by name.

    trust_delims = Lever("=|:| is | are | was | were ",
                         "The 'kv' delimiter class, '|'-separated byte strings: a claim is read "
                         "around each occurrence.", U.NAME)
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11; 04 §6: "the delimiter class for 'kv' keys
    # (unmeasured)"). The bytes `=` and `:` and the space-bounded copulas ` is `, ` are `, ` was `,
    # ` were `, in one string because a Lever holds one value: split on '|', each entry used as its
    # bytes. Refused by name at DATA.new_focus when an entry is empty, repeats another, or is a
    # prefix of another -- the last because a claim must be decidable from the bytes it spans, and
    # with one delimiter a prefix of another, whether a position holds the short one depends on
    # bytes a later pass has not read. Changing it on a resume is refused by name.

    trust_hot = Lever(20, "Count-sketch pre-filter: a claim enters the table once its sketch bucket "
                          "has counted this many claims.", U.COUNT, domain=(1, None))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). d3's HOT. The sketch counts every claim; only a claim
    # whose bucket reached this count is recorded, so a key seen a handful of times across the whole
    # stream costs no table entry. DOMAIN (1, None): at 1 every claim is recorded.

    trust_self = Lever(0.8, "Admission: a source's claim on a key counts only when its most frequent "
                            "value holds at least this share of its readings of that key.",
                       U.FRACTION, domain=(0.0, 1.0))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). d3's SELF: a source that contradicts itself about a
    # key makes no claim about it. The top value must also be the ONLY top value -- a tie at the top
    # is no claim at any share, the same "a tie decides nothing" the vote applies.

    trust_min_n = Lever(3, "Admission: a source's claim on a key counts only after this many readings "
                           "of that key from that source.", U.COUNT, domain=(1, None))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). d3's MIN_N.

    trust_min_ev = Lever(10, "Conflicted claims a source must take part in before its reliability is "
                             "reported and its trust set; below it both are ABSENT and trust is 1.",
                         U.COUNT, domain=(1, None))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). d3's MIN_EV. ONLY CONFLICTED CLAIMS ARE EVIDENCE -- a
    # key at least two sources claim with at least two values between them -- because agreement
    # alone says nothing about which source is the more reliable. A source below this count is not
    # judged: its r and t are ABSENT in the report and its trust stays 1, and a new source joins
    # that way (04 §5's geometry rule).

    trust_min = Lever(0.3, "Trust floor: the least trust a source is given, however unreliable its "
                           "claims.", U.FRACTION, domain=(0.0, 1.0))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). t = clip(r / max r, this, 1). Under 'observe' it
    # multiplies nothing: t is reported as the weight a built actuation would apply.

    trust_every = Lever(160, "Windows between passes of the book over the stream consumed since the "
                             "last one (0 = epoch-end passes only).", U.Windows, domain=(0, None))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). 04 §6's 160 is the testbed's 10 steps x 16 windows,
    # to be lengthened if E3 measures more than 2% of wall. UNIT IS Windows, THE CLOCK THE GATE IS
    # ASKED ON: Cadences.due('data.trust', DATA.trust_period(dat), clock), once per window after the
    # flush, behind the arm test. The epoch's last window also passes, due or not, so the book reads
    # every unit of an epoch before the roll rebuilds the segmentation -- which is what 0 leaves.
    # DOMAIN (0, None) and NOT A READ-SITE REFUSAL (the register's critic, finding 23): a negative
    # would DISARM the gate as an undeclared second spelling of 0, and the six other period
    # accessors refuse it under their packages' REFUSE_NEGATIVE_PERIOD; this one is refused at the
    # first read, which O15 then forbids repeating at DATA.trust_period.

    trust_sketch = Lever(4194301, "Count-sketch size, in int32 buckets; fixed for a lineage.", U.SLOTS,
                         domain=(1, None))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). d3's NB, a prime. 16.8 MB of int32 at the default,
    # held only at DATA_TRUST != 'off' and checkpointed there with the book -- as DATA's payload,
    # NOT as a geometry-manifest field: ckpt/api.py::check_geometry refuses a field this run's
    # manifest names and a checkpoint does not record, so a new field would refuse every checkpoint
    # written before it. A resume at another size is refused by name at DATA.new_focus instead,
    # because a bucket index is the crc32 of a key modulo this number and every count would land in
    # another bucket.

    trust_table = Lever(200000, "Most keys the claim table holds; the least recently claimed is "
                                "evicted beyond it.", U.ENTRIES, domain=(1, None))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-11). Unmeasured on real text (04 §6). An LRU bound, not a
    # geometry: data.trust.table_evictions counts what it cost, and a resume at a smaller bound
    # evicts the least recently claimed keys to fit, counted the same way.

    # ----------------------------------------------------------------------------------------------
    # 6b. WHICH SOURCES COPY EACH OTHER -- SR6's COPY DETECTION INSIDE THE BOOK'S VOTE
    #
    # Four CENSUS AMENDMENTS, 2026-09-28 (Proposal 04 §1 item 8's standing actuation rule (2) and
    # SR6; register §8 3.7, 5.12, 04-Q12, C05 and O5; docs/04_CONTRACT.md Q-DATA-12). None has an
    # ancestor: the old tree kept no book, so it judged no pair of sources. The vote above counts
    # one vote per source per claim, and a source that copies another's values -- false ones
    # included -- doubles that source's vote without adding a witness: the majority-false world
    # inverted trust at 3 of 3 seeds (04 §1 item 8). The ACCU-COPY family (Dong, Berti-Equille and
    # Srivastava, VLDB 2009, as 04 cites it -- from memory, not from a review) judges each pair of
    # sources on the conflicted claims they share and discounts a dependent pair's copy. Built
    # OBSERVE-ONLY: the discount moves the book's vote and the trust it reports, and nothing the run
    # trains on. THE THREE NUMBERS ARE THE FAMILY'S PUBLISHED VALUES AS 04 RECALLS THEM AND ARE
    # PROVISIONAL (register NEW-19): no toy, CPU or GPU reading is behind any of them, §8 3.7's
    # known answers are operation only, and §8 5.12 is the run that decides -- stepping
    # DATA_TRUST_COPY_P first if it fails (O5's first next arm).
    # ----------------------------------------------------------------------------------------------

    trust_copy = Lever("off", "Copy detection inside the book's vote (SR6, the ACCU-COPY family): "
                              "'off' judges no pair of sources; 'accu' judges every pair sharing "
                              "DATA_TRUST_MIN_EV conflicted claims for dependence and discounts a "
                              "dependent pair's later-seen source in the next round of the vote. "
                              "Read only at DATA_TRUST=observe; it moves the book, never the run.",
                       U.NAME, choices=("off", "accu"))
    # CENSUS AMENDMENT, 2026-09-28 (Proposal 04 §1 item 8's standing rule (2) and SR6; register §8
    # 3.7; docs/04_CONTRACT.md Q-DATA-12). BUILT 'off', WHERE THE BOOK IS C5's BIT FOR BIT: the vote
    # runs the statements it ran before this lever, no data.trust.copy.* key exists, and the
    # data.trust.copy gate reads UNREACHABLE naming this lever (or DATA_TRUST='off', which keeps no
    # book at all). 'accu' is the E5 arm §8 5.12 reads, in the majority-false and 50%-impersonation
    # worlds on GPU; O5's lock holds meanwhile, and a 'loss' actuation stays refused (NotBuilt)
    # whatever this reads -- the standing rule asks copy detection to be built AND to pass those
    # worlds before any actuation default is proposed, and only the first is true. A RESUME MAY
    # SWITCH IT: the claim table is the same table either way, so no shape moves; the next pass
    # re-votes it with or without the discount, and an 'off' leg carries the book's copy part
    # unchanged to its saves (the book's own ON -> OFF -> ON rule, Q-DATA-11).

    trust_copy_prior = Lever(0.2, "Prior probability that two sources are dependent before their shared "
                                  "claims are read (the model's alpha); 0 and 1 are refused.",
                             U.FRACTION, domain=(0.0, 1.0))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-12). The family's alpha, 0.2 as 04 recalls it;
    # PROVISIONAL (NEW-19). THE DOMAIN IS CLOSED AND THE BODY REFUSES BOTH ENDS BY NAME at
    # DATA.new_focus when the detection is on (spine/lever.py::Lever's rule for an open interval):
    # at 0 every pair's posterior is 0 and every judged pair would be CERTIFIED independent before a
    # claim is read, and at 1 every pair is dependent -- a certainty no count moves is not a prior.
    # Read only at DATA_TRUST=observe with DATA_TRUST_COPY=accu.

    trust_copy_rate = Lever(0.8, "Copy rate (the model's c): the share of its values a dependent source "
                                 "copies; a dependent pair's later-seen source votes at 1 - c x "
                                 "P(dependent) on the values it shares with the earlier; 0 is refused.",
                            U.FRACTION, domain=(0.0, 1.0))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-12). The family's c, 0.8 as 04 recalls it; PROVISIONAL
    # (NEW-19). It enters twice, and both are the model's: in the likelihood of the pair's shared
    # and differing claims under dependence, and in the discount. THE DOMAIN IS CLOSED AND THE BODY
    # REFUSES ITS LOW END BY NAME at DATA.new_focus when the detection is on (Q-DATA-12's review,
    # 2026-09-28; this said both ends were legal). At 0 a "copier" copies nothing, so dependence is
    # independence: every judged pair's posterior is its prior whatever it claims, every verdict is
    # that prior against DATA_TRUST_COPY_P, and a pair called dependent discounts nothing -- a
    # verdict no claim moves, and at the model's values a gate that cannot fire. THE TOP END IS
    # LEGAL: at 1 a copier copies every value, so a single differing value proves the pair
    # independent (its posterior is 0), and a dependent pair's copy votes at 1 - P. Read only at
    # DATA_TRUST=observe with DATA_TRUST_COPY=accu.

    trust_copy_p = Lever(0.5, "Posterior of dependence above which a judged pair of sources is reported "
                              "dependent and its later-seen source discounted; below it the pair is "
                              "certified independent; 0 and 1 are refused.", U.FRACTION,
                         domain=(0.0, 1.0))
    # CENSUS AMENDMENT, 2026-09-28 (Q-DATA-12). 0.5, the even-odds line; PROVISIONAL (NEW-19), and
    # it is "SR6's threshold" O5 names as the first next arm after a failed §8 5.12. ONLY A PAIR
    # ABOVE IT IS DISCOUNTED: a pair below it is certified independent and votes in full, so two
    # truthful sources that agree -- which the model can never tell from a copy, since agreeing on
    # true values is what accurate sources do -- are not taxed for it. A pair exactly at it is judged
    # and neither. THE DOMAIN IS CLOSED AND THE BODY REFUSES BOTH ENDS BY NAME at DATA.new_focus when
    # the detection is on (Q-DATA-12's review, 2026-09-28): no posterior is above 1, so at 1 no pair
    # could be reported dependent -- Gate data.trust.copy armed and untrippable -- and a planted copy
    # of a liar would be certified independent; none is below 0, so at 0 no pair could be certified
    # and two agreeing truthful sources would be reported dependent, the later one discounted. Read
    # only at DATA_TRUST=observe with DATA_TRUST_COPY=accu.
