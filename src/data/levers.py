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

This file emits 17 levers:

    11  rows with verdict rename
  +  6  rows with verdict keep
  -------
    17  Lever declarations, all reachable as DATA_<FIELD>

Not emitted, by verdict: 1 merge, 0 drop, 0 promote-to-wire.
  MERGED (folds into a lever this file DOES declare, so it is not an unresolved merge):
    PHASED (1) -> `phase_sched`. PHASED=0 IS a schedule -- the single-phase all-active one -- and the
                  duplicate encoding cost more than redundancy: every consumer tested both (`if PHASED
                  and PHASE_SCHED` :5499, `if (PHASED and _cur_ph >= 0)` :6414), three report sections
                  branched on PHASED alone (:8099, :8133, :9809), and the whole-process UNLEARN test ran
                  OUTSIDE the `if PHASED:` guard holding the other two edit tests, so it could delete
                  what _edit_test had already deleted and print "LOCAL" from an edit that removed
                  nothing (ISSUES:525). See DEFECT 3 for the one thing the merge still requires.

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
   fact about this package rather than an oversight. The census types these rows bytes, count, fraction,
   on/off, NAME and PATH. DATA measures its material in BYTES and its schedule in AREAS; it counts no
   running counter of its own, so nothing here is a threshold compared against one. The one clock this
   package's material genuinely touches -- the epoch -- is not owned here: EPOCHS is filed under the
   `data` family in _SPEC and the census moves it to RUN.RUN_EPOCHS, typed Epochs, which is right,
   because units.py rules that an epoch is never a schedule horizon and that ruling has to be enforced
   where the horizon is declared. Nothing to correct. TWO ADJACENT FAULTS ARE NAMED RATHER THAN FIXED,
   both of which a clock kind would not have caught anyway because neither is a clock:
     * `steps = STREAM_LEN // WIN` (:4317, :4719) divides a BYTE budget by a TOKEN window. That is the
       byte/token confusion this family keeps producing, and it is why `stream_bytes` carries the unit
       in its NAME as well as its metadata. It cannot be typed away: U.BYTES and U.TOKENS are metadata
       labels, not runtime types, and only Clocks are enforced.
     * ASSEMBLE ALREADY NAMES A QUANTITY THIS PACKAGE DOES NOT OWN. spine/assemble.py:789 records a
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
   including `if w >= n_areas: w = n_areas - 1` (derive.py:524-525, self_organize.py:1346) -- never
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

ONE VALUE LEAVES, AND IT IS NOT DECLARED HERE EITHER. The census's val_cap row requires the RESOLVED
held-out size to reach EVAL "as a wire so the Sample can state how many bytes it actually covered".
That is a wire on the receiving package (EVAL.d_holdout_bytes) declared in spine.assemble, not a lever
here, and it is a resolved SIZE rather than the cap -- see `val_cap`.

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
# sys.path -- tests/test_derive.py:33, tests/test_ownership.py's SRC insert, and this file's own
# verification command -- which makes `data` a TOP-LEVEL package, and a relative import one level above
# a top-level package raises "attempted relative import beyond top-level package" at import time. All
# six sibling packages (domains, eval, fabric, memory, sig, tok) spell it exactly this way; two packages
# spelling one import two ways is the difference that decides which of them a runner can load.
from spine.lever import Lever, LeverSet
from spine import units as U


class DATALevers(LeverSet):
    """The stream's declared knobs: source, shape, schedule, held-out split.

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
    # choices= IS THE REPAIR, NOT DECORATION. This is knob number one of the eleven ISSUES M24 records
    # where an unrecognised string falls into whichever branch is the `else` -- "DATA_MODE, SIG_MODE,
    # MODEL, VERIFY, KEY_SRC, LR_SCHED, SIG_SPACE, WARMSTART_MODE, TOK_PROBATION_BY, CHAIN_ROUTE,
    # CULL_MODE and EVICT are all compared case-sensitively" (ISSUES:2093, :360). The comparison is
    # `if DATA_MODE == "real"` at :1102/:1120, so DATA_MODE=Real takes the SYNTHETIC branch silently and
    # then dies at :1104 with a message that reads as if the operator had asked for synthetic. With
    # choices, DATA_SOURCE=Real is a startup refusal naming the two legal values. Case is NOT normalised
    # here: AMP is the only knob in the tree that lowercases, and refusing is honest where silently
    # accepting two spellings is a second name for one arm.
    # THE DEFAULT IS THE CENSUS'S LITERAL AND IT IS KNOWN-BROKEN IN COMBINATION. Shipped default
    # synthetic + TOKENIZER=1 exits at startup (ISSUES:345), and the synthetic path itself crashed on a
    # bare NameError for twelve days -- VALC/CORP/DN/SEG_LEN/DISK_STREAM only exist under the real
    # branch -- with preflight.sh's END-TO-END SMOKE the only caller that ever exercised it (C33, H9).
    # The default is not changed here because the fix is TOK's (its row merges TOKENIZER into TOK_MODE
    # and removes the constraint) and because a default changed in two packages at once is a default
    # nobody decided. P3's empty-environment test on both paths is what proves it.

    dir = Lever("data", "Root of the corpus tree; areas are read from DATA_DIR/train/<area>/part*.txt.",
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
                                  "score in the report and across the run boundary.", U.NAME)
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
    # rests on, computed across two languages (ISSUES:1421). The trigger is an undersized corpus: a
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
                            "indices (\"0|0,1|0,1|1\"); empty generates a sliding window from `phases` "
                            "and `phase_live`.", U.NAME)
    # Census: PHASE_SCHED, verdict keep, and it ABSORBS PHASED (the merge above). The parse-at-startup
    # shape is already right and is the model for the port: :1355-1366 refuses an empty phase or an
    # out-of-range area id loudly, at startup, rather than producing a silently different experiment.
    # D2 IS A RULING THIS LEVER CANNOT CARRY AS A LITERAL, AND SAYING SO IS THE POINT. D2 (2026-08-28)
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
    # byte segment past each bound -- so PH_BOUNDS drift and the stream comes out short (ISSUES L22);
    # (2) the `[a for a in act if a < NP] or list(range(NP))` fallback at :1404 is unreachable dead code
    # (ISSUES:812), and the parser at :1358-1361 is what makes it unreachable, so the port must not
    # reintroduce it as a safety net that quietly re-enables every area in a phase.
    # THE STATIONARY ARM IS EXPRESSIBLE ONLY EXPLICITLY -- see DEFECT 3 in the module header.

    phases = Lever(4, "How many phases the generated sliding-window schedule has, when no explicit "
                      "schedule is given.", U.COUNT)
    # Census: PHASES, verdict keep. Read once, at :1343, and only when PHASE_SCHED is empty -- narrow but
    # genuinely live, and it is the generator's one honest parameter.
    # KEPT RATHER THAN "JUST WRITE THE SCHEDULE OUT", because a hand-written schedule silently becomes
    # wrong when the area order changes, and the tree is living with that defect right now: longrun.sh
    # hand-types `_AI=1` under a comment claiming it is computed from the DOMAINS order, and nothing
    # reads DOMAINS (ISSUES L2). The generator itself replaced a per-n lookup table for the stated reason
    # that a rule applies the same shape at any n (:1332-1336).
    # THE FLOOR OF TWO IS A PORT REQUIREMENT THIS DECLARATION CANNOT ENFORCE. The shipped resolution is
    # `p = p or max(2, _i("PHASES", 4))` (:1343) and spine/derive.py:506-508 says in as many words that
    # the floor "belongs on the lever declaration" -- but `choices=` enumerates a closed set and cannot
    # express "any integer >= 2", and lever.py has no bounds parameter. So the guard lives at the read
    # site, and the reason it must exist is concrete: one phase cannot have anything fade, and `faded` is
    # computed off the last phase, so PHASES=1 makes the unlearn-a-faded-area test skip itself as
    # vacuous -- a test that reports passing because it had nothing to check.
    # AND DO NOT REPRODUCE THE ALIASING: the shipped n<=1 path returned `[[0] if n else []] * p`, which
    # is p references to ONE list (ISSUES L23). derive.phase_schedule builds independent lists and is
    # equal by value to the oracle; the difference appears the moment anyone mutates a phase.

    phase_live = Lever(0, "How many areas are live in each phase of the GENERATED schedule; 0 derives "
                          "it from the area count.", U.COUNT)
    # Census: PHASE_W -> DATA_PHASE_LIVE. RENAMED BECAUSE "W" READS AS A WIDTH IN BYTES OR WINDOWS and it
    # is a count of AREAS -- the same ambiguity class that produced the byte/token faults in this family.
    # THE DEFAULT WAS COMPUTED, AND ITS DECLARED PARENT WAS WRONG -- which is the census catching itself.
    # The old _DERIVED table says PHASE_W follows PHASES (:91, "window width follows the phase count"),
    # while the code reads `w = w or max(1, min(n, _i("PHASE_W", (n + 1) // 2)))` at :1345 where n is the
    # AREA count (ISSUES M18). So changing PHASES left it untouched, and losing a corpus to the
    # 5000-byte drop filter silently changed the schedule SHAPE. A declared-vs-actual parent mismatch is
    # exactly what spine.derive's replay table exists to make impossible.
    # 0 IS A SENTINEL, NOT A VALUE, and it is the literal that keeps the derivation where it belongs.
    # THE LITERAL THE RUN ACTUALLY USED WAS 2 -- (4 + 1) // 2 at the default four areas -- but declaring
    # 2 here would FREEZE the width at 2 for every area count and reproduce M18 from the other side:
    # add a fifth area and the schedule shape stops following it, silently. spine/derive.py:522 resolves
    # `width or max(1, min(n_areas, (n_areas + 1) // 2))`, so a falsy value routes to the derivation the
    # spine already owns and replays against the oracle. Any positive value overrides it -- and note that
    # a caller-supplied width is NOT clamped to n_areas by that first expression, only by the
    # `>= n_areas` line below it (derive.py:522-525), which reproduces the shipped behaviour exactly.
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
                               "stream.", U.FRACTION)
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

    val_cap = Lever(4000000, "Maximum bytes of held-out tail kept per area.", U.BYTES)
    # Census: VAL_CAP -> DATA_VAL_CAP, mis-tagged misc, and the row the adversarial reviewer cites by
    # name as an instance of the doubled-name defect (DEFECT 1 in the module header).
    # IT APPLIES ON BOTH PATHS NOW, AND THAT IS THE FIX. Read at exactly one site, :1168, inside the
    # DISK_STREAM branch only -- so on the disk path the held-out set is the tail truncated to 4 MB while
    # on the RAM path it is the ENTIRE holdout_frac tail (:1170). ISSUES M82, stated exactly: "every
    # held-out number is computed over a different amount of text depending on a knob that is nominally
    # about where bytes live" (M81 and M83 are the same root, ISSUES:593). The memorization check, the
    # anchors and ACROSS THE RUN BOUNDARY were therefore computed over different amounts of text in two
    # configurations that differ in paging, and nothing in either report said which.
    # WHAT LEAVES THIS PACKAGE IS THE RESOLVED SIZE, NOT THE CAP. The census requires the held-out byte
    # count to reach EVAL as a wire so the Sample can state how many bytes it actually covered. That wire
    # is declared in spine.assemble on the RECEIVER (EVAL.d_holdout_bytes) and must not be declared here;
    # this lever is only the ceiling.

    exposure_max = Lever(2.0, "Whole-run repetition multiple (bytes drawn x epochs / bytes on disk) "
                              "above which the data plan is flagged before training starts.", U.COUNT)
    # Census: EXPOSURE_MAX, verdict keep, and it is explicitly the not-dropped case: it has never been
    # observed to fire, and the reason is the INSTRUMENT rather than the mechanism. Both reads (:5535,
    # :5538) sit inside `if DATA_MODE == "real" and NP > 1` at :5497, so the whole-run repetition check
    # is unavailable on exactly the single-area configuration goal A runs in -- which is where accidental
    # repetition is EASIEST to reach, since one corpus plus a large stream_bytes is the default way to
    # hit it (ISSUES L21, :2091). The quantity is perfectly well defined at one area.
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
    # confounded with "py was memorised and eng was skimmed" (ISSUES:1620, :5490-5496).

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

    corpus_cap = Lever(2000000, "Bytes read from disk per area before any holdout split or stream "
                                "draw; the ceiling on how much of a corpus this run can see.", U.BYTES)
    # Census: CORPUS_CAP, verdict keep. GENUINELY DISTINCT FROM stream_bytes: one caps what is OPENED,
    # the other caps what is DRAWN. Read once at :1124 into datastream.open_corpus (datastream.py:34-36,
    # 78-81), where it bounds the disk read on both the mmap and the RAM path.
    # THE DEFAULT IS THE MOST EXPENSIVE TRAP IN THE TREE AND IT IS DECLARED HERE UNCHANGED, ON PURPOSE.
    # 2,000,000 bytes per area means a multi-day run trains on 2 MB per area no matter what is on disk.
    # ISSUES H8 and M15 both record SHIPPED scripts that ask for more than the cap allows
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
