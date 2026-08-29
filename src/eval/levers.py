"""EVAL -- the instruments: how much is measured, how long, how often, and where the verdict line sits.

WHAT THIS PACKAGE OWNS. Everything that MEASURES the run, and nothing that changes it. That sentence is
the instrument line, and it is why several knobs below arrive here from families that used to hold them:
AFF_MIN sat on the fabric, VERIFY_FIT sat on the store, GENUINE_MIN/GENUINE_SIL sat in `misc` beside the
domain knobs they grade. A threshold that only shapes a printed number must not ride in the Config a
mechanism receives, because then the mechanism can change how it is graded -- and the fabric grading its
own affiliation report is not a measurement, it is a mechanism with an opinion.

WHY THESE ARE THE LEVERS, AND WHY THEY ARE ALL SAMPLE SIZES AND THRESHOLDS. Both project goals are
CLAIMS, and a claim is only as good as the instrument under it. This package's whole job is to make the
resolution of each instrument an explicit, declared, printable number rather than an accident of a
hardcoded slice:

  GOAL A (language production) is judged by `gen_*` (the text a human reads) and `coh_*` (the scored
  continuation test). The recorded defect is exact: coherence used to be scored on the four printed
  GENERATION samples, about two windows each, so every coherence number this project ever printed landed
  on 0.25/0.50/0.75/1.00 -- a four-sample mean whose standard error is 0.25. "memory HELPS (0.50 -> 0.75)"
  and "the fabric buys coherence (0.75 vs 0.50)" were each ONE sample flipping, and both were reported as
  findings, twice, in opposite directions on consecutive runs. `coh_seeds` x `coh_len` is that instrument
  getting its own sample; `gen_samples` is the same repair for the generation section, which had scored
  "fraction of generated words that appear in the training text" on 64-91 words and reported 91% against
  71% as a difference.

  GOAL B (continual learning without catastrophic forgetting) is judged by `holdout_windows`, and it is
  the load-bearing lever in this file. Every other metric is computed on the CURRENT stream, so the moment
  a new domain arrives both old and new material are in it and both were just trained on. Only the
  retention probe answers "did adding an area damage what was already known", and its n decides whether a
  null result means anything at all.

  AND THE NULL. `null_draws` sizes the permutation null behind every 2-sigma verdict. Two runs of the SAME
  configuration once printed opposite conclusions at excess +0.010 and +0.013 against a 0.010 cutoff,
  because the null had been estimated from too few draws to have an error bar.

Every number this package produces is a SIGNAL, not a fact, and the levers here are the only thing that
says how strong a signal it is.

CENSUS ACCOUNTING (.rework/census.json, filtered on new_owner == "EVAL"): 19 rows.
    17 rename                     -> 17 levers declared below
     1 drop                       -> not declared (VERIFY_SWEEP: it made the report delete the entries it
                                     was measuring, mem.delete(mem.is_unverified()) at :8889-8891, after
                                     which every later section scored a store the report had edited)
     1 merge                      -> EXPERT_NULLS folds into `null_draws`, which INFO_NULLS already
                                     declares here; see DEFECT 3 for the default that collides
     0 promote-to-wire            -> none of EVAL's own rows; the wires that reach this package are
                                     listed under WHAT IS DELIBERATELY ABSENT below
   17 levers in total. The rows came from four old families -- 9 `report`, 7 `misc`, 2 `memory`, 1
   `fabric` -- which is the census's largest single correction visible from one package: `report` was
   never an owner, and the instruments were filed apart from the switch that runs them.

THREE CENSUS DEFECTS REPAIRED WHILE READING IT. All three were real. All three are recorded here rather
than fixed in silence, because a correction nobody can find reads exactly like a transcription error.

  DEFECT 1 -- DOUBLED ENV NAMES. SIXTEEN emitted rows named their target as PREFIX.PREFIX_FIELD.
  lever.py generates the environment name as PREFIX + "_" + FIELD.upper() (lever.py:104-106), so
  `EVAL.EVAL_COH_LEN` taken literally declares a field named `eval_coh_len` answering to
  EVAL_EVAL_COH_LEN -- a name no operator would type and no run would ever read, and one that no static
  check would flag, since a doubled name is a perfectly well-formed name. The prefix is stripped from the
  field in all sixteen and the environment name is exactly what the census intended. Corrected rows:
  GENERATE, GENUINE_MIN, GENUINE_SIL, INFO_NULLS, WRONG_CHECK, WRONG_INJECT (misc); AFF_MIN (fabric);
  COH_LEN, COH_N, EVAL_N, GEN_LEN, GEN_N, GEN_PROCS, GEN_TEMP, HOLDOUT_N, RATE_EVERY (report). A
  seventeenth doubled row is EXPERT_NULLS -> `EVAL.EVAL_NULL_DRAWS`, which is the merge into `null_draws`
  and therefore already corrected by INFO_NULLS's row. The one row that named its target correctly is
  VERIFY_FIT -> `EVAL.verify_fit_steps`, from the `memory` family. Seventeen doubled rows seen, sixteen
  corrections landed on declarations.

  DEFECT 2 -- CLOCK KINDS. Two rows here carry a clock unit and they are NOT the same case.
    `curve_every` is a CADENCE compared as `step % RATE_EVERY == 0` (self_organize.py:6385), and `step`
    advances once per WINDOW (`i += WIN; step += 1`, :7708) while the loop body runs once per FLUSH.
    units.py names that confusion the project's single most repeated defect. Declared U.Windows, which is
    what the census says; its name and every discussion of it said "steps", so at BATCH_W > 1 the cadence
    an operator set was never the cadence they got. No correction to the census was needed.
    `verify_fit_steps` is NOT a cadence. It is a length: optimizer steps spent fitting a small
    Reconstructor post hoc, on a settled store, in its own loop that has no windows and no flushes in it.
    Steps is right and stays Steps -- and the two levers being different kinds in one file is the point,
    not an inconsistency.
    THE CONFLICT WITH THE SPINE, STATED RATHER THAN RESOLVED. spine/assemble.py:686, :698 and :711 wrap
    the analogous `step`-counter cadences as `derive.flush_period(Steps(r["FAB"].manage_every), ...)` and
    `Steps(r["TRAIN"].grow_cap_every)` -- typing as Steps the same counter this file (and derive.py's own
    docstring at :207, "`step` advances once per WINDOW") types as Windows. The same counter therefore has
    two kinds in two files. The practical consequence for whoever ports the curve probe: derive.flush_period
    REFUSES anything but Steps (derive.py:223-226), so there is today NO legal conversion from a
    Windows-typed cadence to the flush clock. Either spine.derive gains a Windows->Flushes conversion or
    FAB.manage_every and TRAIN.grow_cap_every change kind. Picking one here, silently, is how a knob
    acquires two meanings; src/memory/levers.py:49-56 records the identical conflict from its own side,
    which is evidence that this is the spine's row to settle and not a per-package taste.

  DEFECT 3 -- A MERGE WITH TWO DEFAULTS. EXPERT_NULLS (20 draws, the SPECIALIZATION null at :9171) merges
  into EVAL_NULL_DRAWS, and INFO_NULLS (5 draws, the PARTITION INFORMATIVE null at :3831) renames to the
  same target. So unlike src/memory/levers.py's unresolved merge, the survivor DOES have a row of its own
  and is not invented here -- but the two rows carry defaults 4x apart for one name. The renamed row's
  literal wins (5), following the census's own convention for a merged-away value ("The 0.08 value is not
  carried over", EXPERT_CULL_RANK; "The 3000 does not carry over", EXPERT_GRACE). The cost is stated at
  the declaration: the specialization null gets COARSER, from 20 draws to 5, under one name that now sizes
  both. Both old literals are recorded there so the choice is auditable rather than inferred.

WHY NOT ONE LEVER HERE CARRIES choices=. The eleven silent-else knobs the survey found (ISSUES M24:
DATA_MODE, SIG_MODE, MODEL, VERIFY, LR_SCHED, KEY_SRC, SIG_SPACE, EVICT, CULL_MODE, WARMSTART_MODE,
TOK_PROBATION_BY, CHAIN_ROUTE) are every one of them owned elsewhere -- FAB, MEM, SIG, TOK, DATA, OPT --
and they carry choices= in those files. EVAL owns no string-valued knob at all: fifteen numbers and two
flags. AND THE HONEST LIMIT ON THE TWO FLAGS, because this is the same class of defect from a direction
choices= cannot reach: a bool lever's coercion (lever.py:122) reads anything outside
("0", "", "off", "no", "none", "false") as TRUE, so `EVAL_GENERATE=of` -- one dropped letter -- resolves
to ON, silently, exactly like an unrecognised string falling into an else. choices=(True, False) would be
vacuous, since coercion has already collapsed the typo to a member of that set before the check runs. The
repair, if it is wanted, belongs in Lever.coerce as a refusal for unrecognised flag spellings, not as a
choices= list here that would pass every typo it was added to catch.

WHAT IS DELIBERATELY ABSENT. No `d_` field is declared here -- lever.py refuses a d_-named lever precisely
so a declaration cannot shadow the wire that writes it. Four couplings that touch this package are named
by census rows and NONE of them exists in spine/assemble.py yet (verified by grep: no coupling there names
EVAL). They are listed so the port has the list rather than rediscovering it:
    incoming  d_prior_blend    DOM.prior_blend, so the domain-prior probe scores the same blend weight
                               training accumulated (census: domains/DOM_PRIOR)
    incoming  the held-out size resolved by DATA.val_cap, so a Sample can state how many bytes it
                               actually covered instead of 4 MB on one path and the whole tail on the
                               other (census: misc/VAL_CAP, ISSUES:593)
    incoming  the eval signature width, which EVAL_GIST used to switch between two constructions. The
                               census files it as SIG.d_eval_gist and its reason says eval receives the
                               wire; either way it is not a lever and not declared here. At the shipped
                               default it built the eval signature from ONE byte while training encoded
                               >= 256, so every eval-path routing decision in every report was made on a
                               one-byte signature (ISSUES C4/C5).
    outgoing  d_curve_bpb to CKPT and d_best_bpb to OPT -- a held-out measurement crossing back into a
                               training decision. OPT_LR_RESTART_DAMP turns `_best_bpb` into a restart,
                               and PLAN 3.8 forbids a verdict on n=1, so the Reading that supplies it must
                               carry its seed count.

IMPORT STYLE, AND WHY IT DEPARTS FROM THE ASSIGNMENT'S SKETCH. `from ..spine.lever import ...` cannot work
here: every entry point in this tree puts `src/` itself on sys.path (tests/test_derive.py, test_ownership's
SRC insert, and this file's own verification command), which makes `eval` a TOP-LEVEL package, and a
relative import that walks above one raises "attempted relative import beyond top-level package" at import
time. The absolute form below is what the other four packages already use.

A NOTE ON THE PACKAGE NAME. `eval` shadows nothing at import time -- the builtin `eval()` is a name in
builtins, not a module -- but the directory being called `eval` does mean `import eval` inside a file that
also calls the builtin is a readability trap. Nothing here calls it.
"""
from spine.lever import Lever, LeverSet
from spine import units as U


class EVALLevers(LeverSet):
    """The instruments' declared knobs: sample sizes, lengths, cadences, and the four verdict thresholds.

    Read `cfg.holdout_windows`, never an environment name. Every value here is resolved once by
    spine.assemble and frozen; a function receiving this Config should open with `ev.owned_by("EVAL")`,
    because a Config is an ordinary object and a foreign one handed in reads happily and wrongly.

    THE RULE THAT GOVERNS EVERY LEVER BELOW: a number in this file may change how precisely something is
    measured. None of them may change what happens. Two of them used to break that rule -- WRONG_CHECK's
    section force-wrote entries and then called `mem.selfcon.fill_(-1.0)`, and VERIFY_SWEEP deleted what
    it had flagged -- which is why one is dropped and the other is documented at its declaration as a
    Sample that must be built on a copy.
    """

    PREFIX = "EVAL"

    # ==============================================================================================
    # SAMPLE SIZE -- how many draws stand behind each printed number
    # ==============================================================================================

    windows = Lever(
        64, "Default number of windows an eval Sample draws when it does not declare its own.", U.COUNT)
    # WAS EVAL_N, AND THE RENAME IS HALF THE FIX. Two defects rode on the old name.
    # (1) ONE NAME, THREE DENOMINATORS, IN ONE REPORT: at :7958/:7971/:8220 it meant windows per DOMAIN,
    #     at :8810 (`eval_win[p] = idx[:EVAL_N]`) windows per PROCESS, and at :9048
    #     (`_nw = max(1, min(EVAL_N, ...))`) windows in TOTAL across the stream. One knob, three units of
    #     answer, printed side by side with no way for a reader to tell which was which.
    # (2) IT COULD NOT BE RAISED: five of its six readers wrapped it as min(24, EVAL_N) or min(48, EVAL_N),
    #     so EVAL_N=256 drew 24 -- the untrippable-guard shape, 60 of the survey's 475 records. Lowering it
    #     was just as bad and the cost is recorded at :8172-8177: CAN A DOMAIN PREDICT needs 16 held-out
    #     windows and drew min(48, EVAL_N) per domain, so at EVAL_N=4 it collected 4, produced nothing at
    #     all, and DOM_PRIOR was accumulated every window and never read.
    # NOT A DROP, EMPHATICALLY. This is the knob the fabric node-mass probe depends on: that line once
    # measured stream[:WIN] -- ONE window -- and printed "1 of 2214 nodes carry any, top node 100%" under
    # a note reading "all mass on one node = collapsed", in the same report as "ROUTER SELECTION over the
    # whole run: 2108 distinct experts | top 6.1%". A routing collapse was reported that had not happened.
    # UNIT IS U.COUNT AND NOT U.Windows ON PURPOSE. Windows is a CLOCK KIND -- a thing compared against a
    # cadence. This is a sample size that happens to be counted in windows, and typing it as a clock would
    # invite exactly the comparison (`if n >= curve_every`) that units.py exists to make impossible.

    holdout_windows = Lever(
        32, "Held-out windows per domain for the retention probe -- the resolution of the R matrix.",
        U.COUNT)
    # GOAL B'S HEADLINE INSTRUMENT, and the reason it is a separate lever from `windows` rather than a
    # share of it: merging them would make the resolution of a null claim about forgetting a side effect
    # of what unrelated instruments happen to cost. RETENTION compares earliest to latest windows WITHIN
    # one stream and cannot see across a run boundary at all, so this n is the entire error bar on "did
    # adding an area damage what was already known".
    # THE DEFAULT IS A CANDIDATE TO RAISE AND THE RECORD SAYS SO: research_continual_memory.md:743-745
    # warns that the 2-sigma rule at n=32 will report "HELD (inside the noise)" for real effects of
    # moderate size, and recommends 128-256 if a null result is going to be published as a claim. It is
    # left at 32 because that is the literal the runs used; raising it is a decision for after G2 has
    # measured this machine's noise floor, not a silent edit here.
    # TWO COUPLINGS THAT MUST NOT COME BACK. Before c76dc74, changing this 4 -> 16 moved 48 report lines
    # including a verdict SIGN FLIP, because build_stream() drew segment lengths from the same global RNG
    # the diagnostics drew from -- how much you measured decided what you trained on. And SAVE_CKPT gates
    # extra holdout_bpb passes, which once moved a same-seed result by 1.594 b/B. The first is fixed by a
    # separately named eval RNG stream; the second must be declared as a wire or removed.
    # KEYED BY DOMAIN NAME, not by index, so adding a domain does not shift the comparison. That property
    # is part of the lever's meaning and has to survive the port.

    null_draws = Lever(
        5, "Permutation draws used to build the null distribution every 2-sigma verdict is judged against.",
        U.COUNT)
    # TWO OLD KNOBS, ONE NAME -- see DEFECT 3 in the header. INFO_NULLS (default 5, the PARTITION
    # INFORMATIVE null at :3831) is the row that renames to this name and supplies the literal.
    # EXPERT_NULLS (default 20, the SPECIALIZATION null at :9171) is merged away and its 20 does NOT carry
    # over. THE COST, STATED SO IT IS NOT DISCOVERED LATER: the specialization null drops from 20 draws to
    # 5. Both literals are here in this comment; if the merge turns out to have been the wrong trade the
    # evidence for reversing it is written down.
    # WHY IT EXISTS AT ALL: with a single draw the null has no error bar, and two runs of the SAME
    # configuration printed OPPOSITE conclusions at excess +0.010 and +0.013 against a 0.010 cutoff.
    # THE FLOOR IS NOT EXPRESSIBLE HERE, AND THAT IS A GAP, NOT AN OVERSIGHT. ISSUES L44 (this knob at 0
    # -> ZeroDivisionError) and L45 (at 1 -> the 2-sigma test is a rubber stamp, since a one-sample null
    # has zero spread) both want a floor of 2. `choices=` cannot express "any integer >= 2" without
    # enumerating an unbounded set, so the floor belongs in the nulls module that consumes this, as a
    # refusal at construction. Declaring choices=(2, 3, 5, 10, 20) here instead would trade a silent
    # rubber stamp for an arbitrary and equally silent cap.

    # ==============================================================================================
    # COHERENCE -- the scored continuation test, and the four-sample mean it replaces
    # ==============================================================================================

    coh_seeds = Lever(
        16, "Seed passages the coherence instrument draws -- the sample size behind its standard error.",
        U.COUNT)
    # RENAMED FROM COH_N TO SAY WHAT IT COUNTS: seeds, not windows and not tokens. This family had three
    # different N-shaped knobs and that is what let EVAL_N mean three things in one report.
    # IT MUST STAY SEPARATE FROM gen_samples. GEN_N sizes the text a human reads by eye; this sizes a
    # SCORED measurement. The original defect was precisely that one number served both, so improving the
    # readability of the printed samples silently changed a number in the verdict table.
    # COST SCALES WITH THE PARTITION: in the self-referential case HOME is measured per seed by encoding
    # it and taking the nearest centroid, so both the cost and the meaning of this number depend on how
    # many domains the system assembled.

    coh_len = Lever(
        384, "Tokens of continuation per seed -- how far the model must stay in its seed's domain.",
        U.TOKENS)
    # THE DEFECT THAT CREATED IT IS THE REASON IT MUST EXIST. Coherence used to be scored on the four
    # printed GENERATION samples: at ~200 tokens with WIN=256 and stride WIN//2 that is about TWO windows
    # each, so every coherence number this project ever printed landed exactly on 0.25/0.50/0.75/1.00 --
    # the signature of a four-sample mean, whose standard error there is 0.25. "memory HELPS (0.50 ->
    # 0.75)" and "the fabric buys coherence (0.75 vs 0.50)" were each ONE sample flipping, and both were
    # reported as findings, twice, in opposite directions on consecutive runs.
    # coh_seeds x coh_len is this instrument getting its own sample -- about 10x the decisions -- with the
    # standard error printed, so a difference inside it cannot be read as a result.

    # ==============================================================================================
    # GENERATION -- the direct evidence for goal A, the text a human actually reads
    # ==============================================================================================

    generate = Lever(
        True, "Run the GENERATION section: model alone versus model+memory, from the same real seeds.",
        U.FLAG)
    # THE CENSUS RECORDS THE OLD DEFAULT AS `1` (`if _i("GENERATE", 1)` at :9532) and it is declared True
    # here, which is the same value: the old reader used it only in a boolean test. What changes is
    # coercion -- EVAL_GENERATE=off now resolves rather than failing as "not an int" -- and what does not
    # change is the flag's meaning. See the header for the honest limit on flag coercion.
    # KEPT BECAUSE IT IS THE SECTION THAT SPEAKS TO GOAL A DIRECTLY, and because it is expensive enough to
    # want off. Its caveat must be recorded ON THE SAMPLE rather than printed as prose: the samples come
    # from the LIVE model at the end of training, which in every arm so far is 1.1-1.3 b/B WORSE than the
    # model around step 6000. Text read from the end of a run is not text from the best model in it.

    gen_samples = Lever(
        4, "Distinct seed passages sampled per domain in the GENERATION section.", U.COUNT)
    # RENAMED FROM GEN_N TO SAY WHAT IT COUNTS. It exists because every text judgement this project ever
    # made had rested on a SINGLE 200-token continuation: IS IT COMPOSING scored "fraction of generated
    # words that appear in the training text" on 64-91 words, so 91% and 71% were three or four words
    # apart and the difference between them was not resolvable at all.
    # DRAWS WITH random.sample, NOT REPEATED random.choice, so the same passage cannot be drawn twice and
    # the samples are not secretly correlated. That is part of the lever's meaning, not an implementation
    # detail, and it must survive the port.
    # ON A SINGLE-CORPUS RUN THIS IS THE ONLY KNOB THAT RAISES GENERATION RESOLUTION, because gen_domains
    # caps domains and there is only one.

    gen_domains = Lever(
        4, "How many domains the GENERATION section samples -- it slices the sorted domain labels.",
        U.DOMAINS)
    # RENAMED FROM GEN_PROCS, AND THE RENAME IS A GLOSSARY REPAIR RATHER THAN COSMETICS. "proc"/"process"
    # is the dead word for what the rest of the tree calls a domain -- the code already reads
    # `for p in sorted(set(labels))[:GEN_PROCS]`, slicing domain labels directly. The same word meaning
    # two things across two eras is a recorded failure here, which is why docs/10_GLOSSARY is in the plan.
    # SEPARATE FROM gen_samples BECAUSE THEY BOUND DIFFERENT AXES: how many domains you look at versus how
    # many samples each gets. Conflating them is what produced the single-continuation judgements above.
    # On this project's usual one-corpus runs this buys nothing at all -- worth knowing before raising it
    # in the hope of more text.

    gen_len = Lever(
        200, "Tokens per printed continuation, model-only and model+memory, from the same seed.",
        U.TOKENS)
    # COST IS EXPLICIT AND SMALL: gen_samples x 2 x gen_len single-token forwards, 4 x 2 x 200 = 1600.
    # Seconds, once, after training.
    # THE RENAME FIXES A LIVE L1 VIOLATION, which is the real reason this row matters. prompt.py:168
    # declares its own `int(os.environ.get('GEN_LEN', 200))` -- a second reader with a second default,
    # outside the registry entirely, in the one script that exercises the deliverable by hand. ISSUES:685
    # records what that class produces: prompt.py's KEY=VALUE loop sets N=16 intending a generation
    # length, nothing reads N, the sampler generates 200, and the old levers.py could not see it because
    # it audited only self_organize.py. Under the spine, prompt.py receives this frozen Config instead of
    # re-reading the environment.

    gen_temp = Lever(
        0.7, "Sampling temperature for every generated continuation, printed and scored alike.",
        U.FRACTION)
    # ONE OWNER AND ONE DEFAULT, BECAUSE TODAY IT HAS NEITHER.
    # (1) TWO DEFAULTS THAT DISAGREE: 0.7 in _SPEC and 0.6 at prompt.py:168. The sampler a human reads by
    #     hand and the sampler the report scores were two different experiments and nothing said so. The
    #     literal here is 0.7, the _SPEC value the runs used. L1 makes the second default unrepresentable.
    # (2) ONE KNOB, TWO INSTRUMENTS: read by GENERATION (:9648-9649) and by COHERENCE (:9771), so turning
    #     it down to make the printed text look better silently moves a SCORED number in the same report.
    #     That coupling is not removed by this declaration -- it is made visible: both instruments take it
    #     from this one frozen Config and each Sample prints the temperature it ran at.
    # UNIT CAVEAT, STATED RATHER THAN HIDDEN: units.py has no dimensionless-scale label and temperature is
    # unbounded above, so U.FRACTION is the nearest constant and is not exactly right. A TEMPERATURE
    # constant belongs in the metadata table; this is one of two places in this file that wants one.

    # ==============================================================================================
    # CADENCE -- when the learning curve is measured, as opposed to when a log line is printed
    # ==============================================================================================

    curve_every = Lever(
        2000, "Windows between learning-curve probes -- 16 fixed windows per domain under frozen RNG.",
        U.Windows)
    # RENAMED *AND SPLIT*. One cadence currently drives five unrelated things: the learning-curve probe
    # (:6385), the rate/ETA meter (:6489), the profiler dump, the per-expert LR line (:7297) and the
    # no-eligible-expert line. The cost of that is on the record: setting RATE_EVERY=100000 to quieten
    # smoke runs SUPPRESSED THE CURVE TABLE ENTIRELY, so the curve fix went unverified on a live table for
    # a whole round -- every smoke run silently removed the table it existed to check. Here the
    # MEASUREMENT cadence is this lever and the progress/ETA line and profiler dump take a separate
    # RUN-owned log cadence, so quietening a log can no longer disable a measurement.
    # UNIT: Windows. The guard is `step % RATE_EVERY == 0` and `step` advances per WINDOW, not per
    # optimizer step, so this knob has always been denominated in Windows while its name and every
    # discussion of it said steps -- at BATCH_W > 1 the cadence a reader sets is not the cadence they get.
    # See DEFECT 2 in the header for the conflict with spine/assemble.py:686/698/711, which types the same
    # counter as Steps, and for why that is the spine's row to settle rather than this file's.
    # THE SAME GUARD LINE IS WHERE A CRASH LIVED: `... and VALC:` with VALC built only inside
    # `if DATA_MODE == 'real':`, so every synthetic run died the first time the meter came round -- for
    # twelve days, unnoticed, because nothing exercised the synthetic path.

    # ==============================================================================================
    # VERDICT THRESHOLDS -- the four numbers that turn a measurement into a printed word
    # ==============================================================================================

    genuine_min = Lever(
        20, "Minimum member count before a discovered domain is reported as genuine rather than noise.",
        U.COUNT)
    # EVAL'S AND NOT THE DOMAIN PACKAGE'S, and the reason is the instrument line in one sentence: domains
    # must not be able to change how they are graded. Read once at :8545 beside genuine_sil.
    # THE SIZES IT TESTS MUST COME FROM asm.size, NOT FROM THE REPORT LOG. When the count came from the
    # log, every size read 1/BATCH_W of the truth -- a domain of ~2100 members printed as "size 134" --
    # so this threshold was being applied to a number 16x too small and passing almost nothing.

    genuine_sil = Lever(
        0.10, "Minimum silhouette (own-centroid similarity minus nearest-other) for a genuine domain.",
        U.FRACTION)
    # THE HALF THAT MAKES THE TEST BIND AT ALL. The predecessor test was coh >= 0.5 AND sep >= 0.10, which
    # never bound and "silently reduced to a size threshold" -- the untrippable-guard class again, 60 of
    # the survey's 475 records. A conjunction where one clause can never be false is a one-clause test
    # wearing a second clause's name.
    # UNIT CAVEAT: the score is coh + sep - 1 and is really -1..1, so U.FRACTION is the closest available
    # metadata label and is not an exact one. units.py has no signed-score constant; this and gen_temp are
    # the two places in this file that want a new label rather than the nearest existing one.

    aff_min = Lever(
        0.10, "Minimum share of a domain's expert-usage mass at which an expert counts as SERVING it.",
        U.FRACTION)
    # MOVED OFF FAB, and this is the clearest case in the file. Its only two reads are :8965 and :8986,
    # both inside the end-of-run AFFILIATION section; nothing in training touches it. Leaving it on FAB
    # would put a pure instrument knob in the Config a fabric function receives, which is how a mechanism
    # ends up able to adjust the threshold it is judged by.

    # ==============================================================================================
    # WRONGNESS AND VERIFICATION -- the instruments that must not edit what they measure
    # ==============================================================================================

    wrongness = Lever(
        True, "Run the WRONGNESS section: self-consistency detection over the settled store, with its "
              "precision and recall.", U.FLAG)
    # CENSUS DEFAULT IS `1` (`if _i("WRONG_CHECK", 1)` at :8846); declared True for the same reason as
    # `generate`, and with the same coercion caveat.
    # KEPT BECAUSE IT IS THE ONLY INSTRUMENT ON A FLAG THAT GATES EVERY RETRIEVAL, and it is expensive --
    # selfcheck is a full forward over every active entry.
    # WHAT MUST CHANGE IN THE PORT, AND IT IS NOT OPTIONAL: the block currently MUTATES WHAT IT MEASURES.
    # It force-writes the injected entries, runs selfcheck, deletes src 99, and then calls
    # `mem.selfcon.fill_(-1.0)`. Every later section then scores a store the report itself edited. Under
    # G7 the store digest is asserted around every instrument call, so this becomes a Sample built on a
    # COPY and the flag stops being a switch that silently changes state. VERIFY_SWEEP, its sibling, is
    # dropped outright for the same violation -- see the census accounting in the header.

    wrong_inject = Lever(
        8, "Synthetic cross-domain wrong entries planted so precision and recall have a denominator.",
        U.ENTRIES)
    # THE POSITIVE CONTROL, NOT A MEMORY POLICY, which is why it is EVAL's. Without it the section can
    # only print "flagged N of M" with nothing to weigh it against -- the code says so itself at
    # :8919-8921.
    # TWO CONDITIONS THE SOURCE ALREADY DOCUMENTS AND THE PORT MUST HONOUR:
    #   (1) IT IS UNDEFINED BELOW TWO SOURCE DOMAINS with window-aligned samples. An English-only run is
    #       supported and must stay supported: the unguarded version raised IndexError and took the WHOLE
    #       eval battery down AFTER training and checkpointing had completed -- a full run's compute spent
    #       and no report.
    #   (2) THE PLANTED ENTRIES MUST NEVER REACH A MEASUREMENT OF THE REAL STORE. They are the control;
    #       counting them as findings is measuring the instrument.

    verify_fit_steps = Lever(
        3000, "Optimizer steps spent fitting the Reconstructor post hoc on the final settled store.",
        U.Steps)
    # MOVED OFF MEM: read once at :8883, inside the report, and it parameterises the report's OWN
    # verification pass. Under the instrument line it belongs to the package that owns that Sample, not to
    # the store being measured. The one census row in this file that named its target correctly
    # (`EVAL.verify_fit_steps`), so nothing was corrected here.
    # IT IS WHAT MAKES THE SURVIVING HALF OF VERIFICATION WORK. Fitting on the FINAL settled store is the
    # repair for the joint in-loop fit, which trained against a churning, re-tokenized, re-keyed store and
    # reached 0.3% precision (:529-531). Post hoc, on a store that has stopped moving, the same
    # Reconstructor has a fixed target.
    # UNIT IS Steps AND STAYS Steps -- see DEFECT 2. These are genuine optimizer steps of a small separate
    # model, in a loop with no windows and no flushes in it, so this is the one place in this file where
    # the clock kind units.py reserves for optimizer steps is literally what is being counted. It is
    # unrelated to the run's own window and flush clocks, and it must never be compared against
    # curve_every -- which, both being Clocks of different kinds, is now a UnitError rather than a number.
