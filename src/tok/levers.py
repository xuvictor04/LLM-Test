"""TOK -- the online byte-BPE: what the run's symbols ARE, and when they are allowed to change.

WHAT THIS PACKAGE OWNS. One vocabulary and the policy that grows it. Its levers fall into four groups and
each group is one decision: MODE AND CADENCE (which tokenization regime the run is in, and on what clock
the vocabulary and the stream are allowed to move), THE PRE-TRAINING BUILD (how large a vocabulary the run
enters training with, and how much corpus it is allowed to look at to get there), MINT CRITERIA (which
adjacent pair becomes a token, and which does not), and PROBATION (what happens to a minted token that did
not earn its slot). Nothing about MODEL WIDTH is here: the softmax has LM_VOCAB_SLOTS rows and the census
gives that number to LM, which is the one boundary in this file worth reading twice -- see THE CONFLICT
WITH THE SPINE below.

WHY THESE ARE THE LEVERS. Goal A is language production, and this package sets the units it is produced
in: bits/byte is measured per BYTE precisely so that a run which changes its spelling is still comparable
with itself, and every b/B number in the project's records is downstream of what is declared here. The
largest single effect anywhere in those records is a tokenizer lever -- two arms with IDENTICAL
vocabularies (512 minted, 441 used, 0% dead) differing only in whether re-segmentation fired scored 4.364
against 2.175 held-out b/B, and 26% against 94% real words. That is 2.189 b/B and 68 points of word
quality from `retok_every` alone, which is why the cadence group is declared before anything else.

Goal B is continual learning without catastrophic forgetting, and this package has its OWN version of that
failure, distinct from the model's and from memory's: plain most-frequent minting takes the globally most
frequent pair, which by construction re-spells all existing material at once. tokenizer.py:243-254 states
it plainly -- "in a system whose point is continual learning, that is backwards: a new area arriving
should buy vocabulary for ITSELF, not rewrite how everything already learned is spelled." `mint_novel` is
the only lever in the tree that addresses that, and `freeze_at` is its blunt alternative (stop the
vocabulary moving at all, partway through). Both are declared below at defaults that mean OFF, because
that is what the old tree ran, and a default that quietly differs from the measured one makes every
existing number in the records unattributable.

The "room for additional modalities" half of goal A also lands here and it is arithmetic, not aspiration:
self_organize.py:6086-6099 spells out that `grow_every` x `grow_burst` pays for roughly N mints per epoch,
and if that product is below the slot ceiling then raising the ceiling sizes a softmax that minting can
never fill -- "a new area gets new EXPERTS and could not get new TOKENS". A modality is a different
alphabet; it needs vocabulary before it needs anything else.

CENSUS ACCOUNTING (.rework/census.json, filtered on new_owner == "TOK"): 21 rows.
    14 rename + 4 keep             -> 18 levers declared below
     2 merge                       -> both fold into levers declared here: TOKENIZER into `mode`
                                      (the "bytes" arm), GROW_PASSES into `build_passes`
     1 drop                        -> not declared (RETOK_TAIL)
     0 promote-to-wire
   18 levers in total, from 21 rows. CENSUS.md's ownership table says "TOK 21" because it counts ROWS
   assigned to this package, not declarations that survive them; the two are not the same number for any
   package with a merge or a drop in it, and the difference is exactly the three rows above.

FIVE ROWS THAT LOOK LIKE TOK'S AND ARE NOT, listed because a reader who finds them missing will otherwise
go looking for a mistake. The census moved them and this file obeys it: VMAX -> LM.LM_VOCAB_SLOTS,
TOK_COMPOSE -> LM.LM_COMPOSE, TOK_ANCHOR -> LM.LM_ANCHOR_W, TOK_ANCHOR_USES -> LM.LM_ANCHOR_USES (all four
are model geometry and model loss terms that merely have TOK in the old spelling), TOK_ANCHOR_TAU dropped
by LM. TOKENIZER_PATH is a promote-to-wire owned by CKPT and arrives as `d_vocab_path`; it must not be
declared here even though this package is what reads and writes that file.

THREE CENSUS DEFECTS REPAIRED WHILE READING IT. All three were checked against this package's 21 rows; two
were present, one was not, and the negative is recorded too, because "no unresolved merge" is only useful
if someone can see that it was looked for.

  DEFECT 1 -- DOUBLED ENV NAMES. EIGHTEEN of the emitted rows name their target as PREFIX.PREFIX_FIELD:
  `TOK.TOK_DROPOUT`, `TOK.TOK_RETOK_EVERY`, `TOK.TOK_MODE` and so on for every one of them (CENSUS.md:299,
  310, 319 among others). lever.py generates the environment name as PREFIX + "_" + FIELD.upper(), so
  `TOK.TOK_DROPOUT` taken literally declares a field `TOK_DROPOUT` answering to TOK_TOK_DROPOUT -- a name
  no operator would ever type, that from_env() would never find, and that leaves the lever permanently at
  its default while every static check reports it declared and owned. The prefix is stripped from the
  field in all eighteen; the ENV NAME IS UNCHANGED from what the census intended, which is the point of
  the correction rather than a side effect of it. Corrected: TOK_GROW_BURST, TOK_GROW_EVERY, TOK_MODE,
  TOK_RETOK_EVERY, TOK_FREEZE_AT, TOK_SEED_VOCAB, TOK_BUILD_PASSES, TOK_MIN_PAIR, TOK_MAX_BYTES,
  TOK_DROPOUT, TOK_BUILD_BYTES, TOK_MINT_PMIN, TOK_CAND_WINDOW, TOK_MINT_NOVEL, TOK_PROBATION_USES,
  TOK_PROBATION_DEADLINE, TOK_PROBATION_BY, TOK_PROBATION_RESIDUAL. Two further rows carry the same
  doubling on targets this file does not mint separately -- TOKENIZER -> TOK.TOK_MODE and GROW_PASSES ->
  TOK.TOK_BUILD_PASSES, both merges into fields already corrected above. Twenty doubled rows seen,
  eighteen corrections landed on declarations. Unlike MEM, where only the `misc` family was affected, here
  the doubling is uniform: every TOK row uses it, including the two that arrived from `misc`.

  DEFECT 2 -- CLOCK KINDS. Four levers here are cadences or deadlines: `grow_every`, `retok_every`,
  `freeze_at` and `probation_deadline`. Every one of them is compared against `step`, and `step` advances
  once per WINDOW (`i += WIN; step += 1`, self_organize.py:6796 and :7708) while the loop body runs once
  per FLUSH (:934). All four are therefore U.Windows. NO CORRECTION WAS NEEDED: the census already types
  them Windows -- three as "Windows" and GROW_EVERY as lowercase "windows", which is a spelling difference
  and not a kind difference -- and it corrected two of them from the source's own wording as it did so.
  The one whose NAME still lies is declared with its name fixed: TOK_PROBATION_STEPS counts windows and
  says steps, which at BATCH_W=16 is a 16x error in the same family as pin_tick, so it is
  `probation_deadline` here and the old spelling does not survive.

    THE CONFLICT WITH THE SPINE, STATED RATHER THAN RESOLVED. Two of them, both real, both in
    spine/assemble.py, and neither is settled here because picking a side in a declaration file is how a
    knob acquires two meanings.

    (a) OWNERSHIP OF VMAX. assemble.py:723-725 declares `Coupling(src="TOK.vmax", dst="LM.d_softmax_width",
    compute=lambda r: int(r["TOK"].vmax))` -- it reads `vmax` off THIS package's Config. The census gives
    VMAX to LM as LM_VOCAB_SLOTS (verdict rename, default 4096, unit slots, family `tokenizer`), so under
    the census there is no `TOK.vmax` to read and build() will raise LeverError at startup the moment both
    LM and TOK are registered. This file follows the census and does NOT declare `vmax`; declaring it to
    keep assemble quiet would put the softmax width in two packages at once, which is the failure the
    ownership spine exists to prevent, and the coupling's own `why` argues for LM's side ("emb.weight and
    head.weight have exactly this many rows... one number named twice"). The repair is one line in
    assemble.py -- src/compute read from LM -- and it is assemble's to make, not this file's. Note the
    same spelling appears in assemble.py:495 inside a docstring example; that one is prose and harmless.

    (b) TWO CLOCK KINDS ARRIVE AT ONE PACKAGE. assemble.py:708-719 wires `TOK.d_cap_lift_period` as a
    FLUSHES clock, derived by `derive.flush_period(Steps(r["TRAIN"].grow_cap_every), r["TRAIN"].batch_w)`
    -- correctly, since the capacity valve's own knob is typed Steps (census: GROW_CAP_EVERY ->
    CAP.CAP_PIN_STEPS, unit Steps). So this package will hold four Windows cadences of its own and one
    Flushes period from the valve, and units.Clock refuses every comparison and every sum between them --
    including `==`. There is today NO legal conversion in either direction: derive.flush_period accepts
    Steps and nothing else (derive.py:223-226), and spine.derive has no Windows->Flushes function at all.
    Whoever ports the vocabulary cap must therefore either add that named conversion to spine.derive or
    change what the valve hands over; doing it inline at the comparison is the pin_tick defect again, and
    the refusal that will be raised is the mechanism working, not a bug in this file. MEM's levers.py
    records the identical unresolved question for FAB.manage_every, which suggests it is one decision the
    tree owes rather than three.

  DEFECT 3 -- NO UNRESOLVED MERGE HERE, AND IT WAS CHECKED. Both merges name a target that has a row of
  its own in the same family: TOKENIZER -> TOK_MODE, which is TOK_ONLINE's row (verdict rename), and
  GROW_PASSES -> TOK_BUILD_PASSES, which is SEED_PASSES' row (verdict rename). Nothing was invented and
  nothing is left standing on its own. One thing that RESEMBLES an unresolved merge is not one:
  TOK_MINT_NOVEL_K is absorbed into `cand_window` by that lever's reason, but it has no census row
  anywhere because it was never in the old `_SPEC` at all -- it is read at tokenizer.py:140 behind the
  registry's back, which is why the audit printed "NOTHING READ THESE: TOK_MINT_NOVEL_K ... This run used
  the DEFAULTS" when an operator set it, a false sentence about a knob that was read and used (M23,
  ISSUES.md:357). An unregistered knob absorbed into a declared lever is a completed merge with one silent
  half, not a merge with a missing target, and `cand_window` below is the single width it becomes.

WHAT IS DELIBERATELY ABSENT. Values this package uses that it does not own, and must not declare --
lever.py refuses a d_-named lever precisely so a declaration cannot shadow the wire that writes it:
    d_cap_lift_period   Flushes, from TRAIN.batch_w x TRAIN.grow_cap_every   (assemble.py, declared)
    d_vocab_path        the tokenizer json's path, owned by CKPT             (census promote-to-wire)
    d_residual_ratio    ||delta||/||composite|| from LM.compose              (NOT YET IN THE LEDGER)
The third is the one to watch. TOK_PROBATION_MIN's census reason states that the ratio "arrives as the
wire d_residual_ratio from LM", and no such Coupling exists in assemble.COUPLINGS today. Until it does,
`probation_by="embed"` has a threshold with nothing to compare -- which is the shape of the defect the
embed arm already had once: TOK_PROBATION_BY=embed with TOK_COMPOSE=0 left the composer as None and fell
through to the "use" test with no warning, while the banner and the end-of-run [vocab] line at :7864 both
reported "judged by embed" (M41). A missing wire is better than that, because it fails loudly, but it is
still missing and this is the record of it.

IMPORT STYLE. Absolute, `from spine.lever import ...`, matching fabric, sig, memory and domains. Every
entry point here puts src/ itself on sys.path (tests/test_derive.py:33, tests/test_ownership.py's SRC
insert, and this file's own verification command), which makes `tok` a TOP-LEVEL package; a relative
`from ..spine.lever import ...` raises "attempted relative import beyond top-level package" under that
convention, which is the only convention this tree has.
"""
from spine.lever import Lever, LeverSet
from spine import units as U


class TOKLevers(LeverSet):
    """The online byte-BPE's declared knobs: mode and cadence, the build, the mint criteria, probation.

    Read `cfg.retok_every`, never an environment name. Every value here is resolved once by
    spine.assemble and frozen; a function receiving this Config should open with `tok.owned_by("TOK")`,
    because a Config is an ordinary object and a foreign one handed in reads happily and wrongly.

    Grouped by mechanism rather than alphabetically. The clearest reason is the cadence pair: `freeze_at`
    and `retok_every` were called "two knobs, one idea, and setting only one is almost always a mistake"
    in the source (self_organize.py:6053-6061), and reading either without the other tells you nothing
    about whether the vocabulary the run reports is the vocabulary the run trained on.
    """

    PREFIX = "TOK"

    # ==============================================================================================
    # 1. MODE AND CADENCE -- what regime the run is in, and when symbols are allowed to move
    #
    # These five decide whether there is a vocabulary at all, whether it grows, and how often the
    # already-emitted stream is re-spelled. They are declared first because every measured number in
    # this project is denominated in what they set, and because the largest single effect in the
    # records lives here.
    # ==============================================================================================

    mode = Lever("online", "Which tokenization regime the run uses: raw bytes, a vocabulary built once "
                           "before training, or an online byte-BPE that keeps minting while it trains.",
                 U.NAME, choices=("bytes", "fixed", "online"))
    # Census: TOK_ONLINE -> TOK_MODE, verdict rename, ABSORBING the TOKENIZER row (verdict merge) as the
    # "bytes" arm. Field corrected from `TOK_MODE` to `mode` (DEFECT 1); the env name is TOK_MODE either
    # way, which is what the census meant.
    # THE DEFAULT IS A RE-ENCODING OF TWO LITERALS, NOT A NEW CHOICE. The old tree spelled this state as
    # TOKENIZER=1 (subword mode on) plus TOK_ONLINE=1 (keep minting), and both defaulted to 1, so
    # "online" is exactly the configuration every existing record was taken under. TOKENIZER=0 is
    # "bytes"; TOKENIZER=1 with TOK_ONLINE=0 is "fixed"; TOKENIZER=0 with TOK_ONLINE=1 is the nonsense
    # corner that three values cannot spell.
    # choices= IS THE REPAIR, AND IT REPAIRS SOMETHING BIGGER THAN A TYPO HERE. Two booleans encoding
    # three states is why whole knobs are unreachable per branch and nobody can see it: GROW_PASSES is
    # never read at TOK_ONLINE=1 (the default) and SEED_VOCAB/SEED_PASSES are never read at
    # TOK_ONLINE=0, so setting one on the wrong branch is silently ignored AND produces a "NOTHING READ
    # THESE" line whose stated cause -- a typo -- is false (ISSUES.md:820, :2089). The source already
    # admitted the encoding was wrong: self_organize.py:5848 reports ("TOK_ONLINE", USE_TOK and
    # TOK_ONLINE), i.e. the printed value of one knob is an AND of two.
    # ONE COUPLING DIES WITH THE MERGE AND THAT IS DELIBERATE. self_organize.py:1102-1106 raised
    # SystemExit("TOKENIZER=1 requires DATA_MODE=real") while DATA_MODE defaulted to "synthetic", so THE
    # DEFAULT ENVIRONMENT EXITED AT STARTUP -- which P3's tests/test_default_runs.py (empty environment,
    # 200 steps, both data paths) cannot pass against. The constraint was an artifact of where the build
    # code sat, not a property of the mechanism: a byte-BPE tallies bytes and synthetic Markov bytes are
    # bytes. The rebuild builds the vocabulary on both data paths and the refusal does not carry over.

    freeze_at = Lever(0, "Window after which no further token is minted; the vocabulary is fixed from "
                         "there to the end of the run. 0 means never freeze.", U.Windows)
    # Census: TOK_MINT_UNTIL -> TOK_FREEZE_AT, verdict rename, unit Windows. Field corrected (DEFECT 1).
    # KEPT BECAUSE IT IS AN ARM, NOT A SAFETY VALVE. "The vocabulary stops moving partway through" is a
    # first-class continual-learning condition and it produced real comparisons (survey chat-a: a dead
    # heat against base on d_order1). Its unit was corrected by the census for the same reason as
    # `retok_every`: the test is `step >= TOK_MINT_UNTIL` at :7578 and `step` counts windows.
    # THE COUPLING WARNING IT USED TO CARRY IS STALE AND DOES NOT CARRY OVER. :5992 and :6053-6061 warn
    # that freezing without also stopping retok is "almost always a mistake"; the guard at :7739 already
    # resolves it, because once minting stops (vocab_size, len(seq2id)) stops changing and every
    # subsequent retok is skipped. What was actually measured is the residue of that: at
    # TOK_MINT_UNTIL=1 a frozen run still fired 39 NO-OP re-tokenizations, which cost time and reported
    # as activity. The rebuild should report them as skipped rather than pretend they did not happen.
    # 0 IS STILL A SENTINEL AND THE CENSUS ASKED FOR THAT TO END. Its reason says 0-means-never should
    # become "an explicit off value under choices/derivation rather than a sentinel". choices= cannot
    # express "0, or any positive window" -- the same limit domains/levers.py:262 records -- and inventing
    # a second lever to hold the off switch would be minting a knob the census never voted on. So the
    # sentinel stands, declared in the help text where a reader will see it, and the honest repair is a
    # derivation inside this package that names the frozen state once.

    retok_every = Lever(3000, "How often the unconsumed stream is re-segmented with the vocabulary as it "
                              "now stands; 0 leaves already-emitted ids alone forever.", U.Windows)
    # Census: RETOK_EVERY -> TOK_RETOK_EVERY, verdict rename, unit Windows. Field corrected (DEFECT 1).
    # THE LARGEST SINGLE EFFECT IN THE PROJECT'S RECORDS, AND THE REASON THIS LEVER MAY NOT BE QUIETLY
    # HARDCODED. Two arms with IDENTICAL vocabularies (512 minted, 441 used, 0% dead) differing only in
    # whether retok fires: at 3000, held-out 4.364 b/B and 26% real words; at 0, held-out 2.175 b/B and
    # 94% real words. That is 2.189 b/B and 68 points of word quality -- and 23 retoks fired, of which 22
    # added zero tokens (:7714-7722). A mechanism that changes the headline number by more than the
    # difference between a working model and a broken one, while doing nothing 96% of the times it runs,
    # is the definition of a lever that must stay measurable.
    # UNIT CORRECTED BY THE CENSUS, NOT BY THIS FILE: it is compared through `_due` against `step`
    # (:7733, :5283) and `step` advances once per WINDOW (:7708 `i += WIN; step += 1`; :934 states it in
    # words), yet it has been read as steps throughout. Same class as pin_tick.
    # TWO COUPLINGS MUST SURVIVE AS DECLARED WIRES AND NEITHER IS IN THE LEDGER YET. (1) It bounds the
    # signature lookahead horizon: :6663-6664 computes _H = min(_H, RETOK_EVERY - ...). (2) A retok
    # invalidates _VALT/_BL, remaps mem.ctx and decays asm.tokc (:7766-7788), so it reaches SIG, MEM and
    # DOM. domains/levers.py:615 already states the other end of (2) correctly -- DOM must not read this
    # cadence, the retok arrives as a SIGNAL -- and that is the shape the rest should take too.

    grow_every = Lever(200, "Cadence at which the vocabulary mints a burst of new tokens.", U.Windows)
    # Census: GROW_EVERY -> TOK_GROW_EVERY, verdict rename, unit "windows" (lowercase in the row; the
    # kind is the same). Filed under `misc` in the old tree and moved here. Field corrected (DEFECT 1).
    # WINDOWS, FOR THE SAME REASON AS EVERY OTHER CADENCE IN THIS GROUP: read at :5266 and used at :7591
    # (probation) and :7619 (minting) through `_due`, which compares against `step`.
    # ONE IMPLEMENTATION NOTE WORTH CARRYING, because it looks like a bug and is not: the probation path
    # deliberately asks `_due` under its OWN key rather than under the grow key. Sharing the key would
    # consume the event, and minting would then never fire at all -- an armed-but-inert mechanism created
    # by a tidy-up. Whoever ports :7591 and :7619 must keep the two keys distinct.

    grow_burst = Lever(6, "How many new tokens are minted at each grow event.", U.TOKENS)
    # Census: GROW_BURST -> TOK_GROW_BURST, verdict rename, filed under `misc`. Field corrected (DEFECT 1).
    # IT IS HALF OF THE MINT BUDGET AND THE ARITHMETIC IS LOAD-BEARING FOR THE MODALITIES CLAIM.
    # self_organize.py:6086-6099 spells it out: GROW_EVERY x GROW_BURST pays for roughly N mints per
    # epoch, and if that product falls below the slot ceiling then raising the ceiling sizes a softmax
    # that minting can never fill -- "a new area gets new EXPERTS and could not get new TOKENS". The
    # coupling check at :6086 reads this knob for exactly that reason, and it is the one arithmetic in
    # this package that must be reported at startup rather than discovered at the end of a run.

    # ==============================================================================================
    # 2. THE PRE-TRAINING BUILD -- what the run enters training holding
    #
    # Three numbers, one for the target, one for the effort and one for the material. They are separate
    # from the cadence group because they run ONCE, before the loop, and separate from the mint criteria
    # because they bound the build rather than judge a candidate.
    # ==============================================================================================

    seed_vocab = Lever(512, "Target vocabulary size the pre-training build aims for, before any online "
                            "minting.", U.TOKENS)
    # Census: SEED_VOCAB -> TOK_SEED_VOCAB, verdict rename. Field corrected (DEFECT 1).
    # THE SIZE A RUN ENTERS TRAINING AT IS A DIFFERENT QUANTITY FROM THE CEILING IT MAY GROW TO, and
    # conflating the two is how the report went wrong twice (:1274-1281). First, the end-of-run summary
    # printed a hardcoded "grew 256 -> N", so every round18 log says "grew 256 -> 2048" for a run that
    # entered training at 512. Second, DID IT FIRE's tokenizer.mint row subtracts SEED_VOCAB from the
    # final size -- but SEED_VOCAB is the loop's TARGET and the loop breaks early on `minted == 0`
    # (:1271), so a corpus that converges below target makes that row report MORE mints than happened,
    # and on a resume the target has nothing to do with the starting point at all.
    # THIS IS THE TARGET; THE ACHIEVED SIZE IS A READING WITH ITS OWN NAME (TOK_V0) AND IS NEVER
    # COMPUTED BY SUBTRACTION. That is the whole repair, and it belongs in the instrument, not here.
    # In the "fixed" arm of `mode` the target is also the ceiling; that is a declared derivation inside
    # this package rather than the branch at :1224.

    build_passes = Lever(2, "How many tally-and-mint passes over the build corpus the pre-training "
                            "vocabulary build takes.", U.COUNT)
    # Census: SEED_PASSES -> TOK_BUILD_PASSES, verdict rename, ABSORBING GROW_PASSES (verdict merge).
    # Field corrected (DEFECT 1).
    # ONE QUANTITY THAT WAS READ ON OPPOSITE SIDES OF ONE TERNARY: :1225 is
    # `_passes = _i("SEED_PASSES", 2) if TOK_ONLINE else _i("GROW_PASSES", 8)`, so exactly one of the two
    # is reachable in any run and the other triggers a false "NOTHING READ THESE" typo report
    # (ISSUES.md:820, :2089). Two names for one number, each unreachable half the time, is the merge case
    # in its purest form.
    # THE DEFAULT IS 2 BECAUSE 2 IS WHAT THE DEFAULT CONFIGURATION RAN. GROW_PASSES=8 was the offline
    # build's literal and it is NOT lost information: the offline build genuinely wants more passes,
    # since it is the only chance it gets. But a per-arm default cannot be expressed on a Lever -- the
    # default must be one literal.
    # RULED 2026-09-02 (Q-TOK-9): THERE IS ONE LITERAL, 2, AND IT IS READ ON ALL THREE ARMS. This
    # comment used to say the 8 "carries over as the fixed arm's declared target inside this package's
    # build code", which put a second number where the generated lever reference cannot reach it:
    # docs/04_LEVERS.md is generated from these declarations (fabric/levers.py:104, domains/levers.py:166,
    # opt/levers.py:499 -- "reads the default off the registry instead of retyping it"), so an 8 in
    # build code prints as 2 for the arm where it is wrong. That is L1's failure with a second literal
    # instead of a second environment name, and src/tok/api.py:57 and :75 already told P4 the opposite
    # of this comment -- two frozen surfaces, opposite instructions, different tok.v0 on the arm that
    # carries the project's largest recorded effect (4.364 vs 2.175 b/B).
    # THE 8 SURVIVES AS A DECLARED GATE, NOT AS A NUMBER: build_vocabulary's tok.build_passes_advice
    # prints the recommendation with its predicate on mode="fixed" and prints "unreachable" otherwise.
    # It must NOT come back as a second lever: that is the state the merge removed, and N1 has one row
    # (SEED_PASSES -> TOK_BUILD_PASSES absorbing GROW_PASSES), so a second lever needs a second row.
    # A mode="fixed" run at 2 passes is not the offline build of record -- P9's moved-numbers list.

    build_bytes = Lever(1000000, "How many bytes are taken from the head of each corpus for the "
                                 "pre-training vocabulary build.", U.BYTES)
    # Census: TOK_GROW_CAP -> TOK_BUILD_BYTES, verdict rename. Field corrected (DEFECT 1).
    # RENAMED AWAY FROM GROW_* ON PURPOSE. Four different mechanisms shared that prefix -- GROW_CAP,
    # GROW_CAP_VOCAB, GROW_EVERY, GROW_BURST -- and this one belongs to none of their families; it is a
    # bound on the BUILD's input, and reading it as a member of the capacity valve is a mistake the old
    # name actively invited.
    # NOT A DUPLICATE OF DATA'S CORPUS_CAP, and the distinction is mechanical: :1261 is
    # `gb = b''.join(c[:TOK_GROW_CAP] for c in CORP)`, which bounds the cost of the build passes
    # specifically, while CORPUS_CAP=2000000 bounds the corpus the run TRAINS on. The seed build wants a
    # smaller and cheaper sample than training does, and folding them would make a cheap build
    # impossible without shrinking the run. The corpus itself arrives from DATA; this is TOK's own bound
    # on how much of it the build reads.

    # ==============================================================================================
    # 3. MINT CRITERIA -- which adjacent pair becomes a token
    #
    # A frequency floor, a length ceiling, a candidate window, and two re-rankers that compose. Every
    # one of them was read on the fresh-construction branch only (:1256): DynamicTokenizer.load
    # reconstructs them from the saved json, so ON EVERY RESUME the environment value was silently
    # ignored (M80, ISSUES.md:2085). Under L1 this package holds ONE declaration, and a load either
    # matches it or is reported as a reconciliation -- never silently wins.
    # ==============================================================================================

    min_pair = Lever(50, "How many times an adjacent pair must have been counted before it is a "
                         "candidate for minting at all.", U.COUNT)
    # Census: MIN_PAIR -> TOK_MIN_PAIR, verdict rename. Field corrected (DEFECT 1).
    # THE FREQUENCY FLOOR THE WHOLE MINT RANKING SITS ON (tokenizer.py:290-297, :481).
    # IT HAD TWO DEFAULTS AND THAT IS THE EXACT FAILURE THIS SPINE EXISTS FOR: the registry said 50 and
    # DynamicTokenizer.__init__ said 200 (tokenizer.py:130). lever.py:66-72 describes the five-defaults
    # problem in the abstract; this is it in the concrete, and it survived because it lived in the OTHER
    # FILE, where the registry could not see it. 50 is the registry's literal and the one the recorded
    # runs were configured with, so 50 is the declaration. If the construction path wants 200 it is now
    # a visible disagreement rather than a value that depends on which file you read.

    max_bytes = Lever(16, "The longest byte string a single token may stand for; a candidate merge "
                          "longer than this is refused.", U.BYTES_PER_TOKEN)
    # Census: MAX_TOK -> TOK_MAX_BYTES, verdict rename. Field corrected (DEFECT 1).
    # LOAD-BEARING ON THE FAILURE THE TOKENIZER CALLS ITS WORST. Candidates refused for length used to
    # abort the entire grow burst: measured "max_tok=6 vmax=4000 -> stalled at 658/4000 with 1866 pairs
    # still above min_pair (83.5% dead)" (tokenizer.py:318-324). A ceiling that stops a burst instead of
    # skipping a candidate turns a length preference into a vocabulary cap nobody asked for.
    # IT CARRIES AN UNDECLARED WIRE THAT MUST BECOME A DECLARED ONE. ByteComposer hardcodes maxb=16
    # (:1441) and does not follow this knob, so any value above 16 silently truncates the composer's view
    # of a token to its first 16 bytes while the tokenizer happily emits the whole thing -- two
    # components disagreeing about what a token IS, with no error. The rebuild sends this to LM as
    # d_max_token_bytes and LM sizes its byte and position tables from it; that Coupling is not in
    # assemble.COUPLINGS yet, and until it is, this default agreeing with that hardcode is luck.

    cand_window = Lever(1024, "How many candidates deep the mint ranking is materialized, so a "
                              "re-ranker has something to choose from.", U.COUNT)
    # Census: TOK_MINT_GATE_K -> TOK_CAND_WINDOW, verdict rename, absorbing the unregistered
    # TOK_MINT_NOVEL_K. Field corrected (DEFECT 1); see DEFECT 3 in the header for why the absorbed knob
    # has no row of its own.
    # ONE QUANTITY, TWO KNOBS, ONE OF THEM INVISIBLE TO THE REGISTRY. maybe_grow computes a single window
    # width from both re-rankers -- `_k = 1; if novel>0: _k = max(_k, novel_k); if pmin>0: _k = max(_k,
    # gate_k)` (tokenizer.py:257-260) -- and TOK_MINT_NOVEL_K was read at :140 while being absent from
    # _SPEC, so setting it made the audit print "NOTHING READ THESE: TOK_MINT_NOVEL_K ... This run used
    # the DEFAULTS", which was false (M23, ISSUES.md:357). A knob the audit cannot see is worse than a
    # knob that does not exist, because the audit is what the operator trusts.
    # THE FLOOR ABOVE 1 IS A REQUIREMENT AND IT CANNOT BE DECLARED HERE. At _k=1 the window is a single
    # pair, so "walk on to the next candidate" has nothing to walk and one unmintable top pair ends the
    # burst -- the fault the lazy re-query at tokenizer.py:325-329 exists to patch. `choices=` cannot
    # express "at least 2", so the floor lives at the point of use and this comment is the reason it must
    # be there.
    # CALIBRATION EVIDENCE TO PRESERVE: at 64 the window itself starved minting (419 of 1024 minted,
    # against 1010 at 1024), which means the CAP and not the threshold was deciding. Anyone re-tuning
    # `mint_pmin` at a small window is measuring this lever instead.

    mint_pmin = Lever(0.0, "Minimum p(b|a) for a merge to be accepted as a unit rather than a frequent "
                           "collision across a boundary; 0 mints on frequency alone.", U.PROBABILITY)
    # Census: TOK_MINT_PMIN -> TOK_MINT_PMIN, verdict keep. Field corrected from `TOK_MINT_PMIN` to
    # `mint_pmin` (DEFECT 1) -- the env name is unchanged, which is what makes this row look harmless and
    # is exactly why it needed the same correction as the rest.
    # THE PRE-MINT QUALITY CRITERION, AND THE ONLY ONE THAT CAN WORK. tokenizer.py:141-157 argues it
    # carefully: an absolute branching-entropy cutoff rejects 81% of left tokens over 400 kB of English
    # and rejects the USEFUL merges first, because H is anti-correlated with frequency. p(b|a) asks the
    # same question scale-free.
    # THE PROJECT'S BEST-DOCUMENTED FAIL-OPEN LESSON. As a HARD GATE it left 609 of 2048 rows (29.7%)
    # never minted and scored 3.600 b/B against a ~1.96 baseline. It now REORDERS the candidate window
    # instead of blocking it, so it can never starve the vocabulary (tokenizer.py:305-313). A quality
    # criterion that can empty the softmax is not a quality criterion.
    # TWO THINGS FOLLOW IT INTO THE REBUILD. (1) It must stop being read from os.environ inside
    # tokenizer.py:158, behind the registry's back -- lever.py's own module docstring names this exact
    # read as the reason from_env is the single reader, and O1 now makes it impossible. (2) h_pmin_seen
    # must stop accumulating one float per candidate for the whole run (millions of floats at
    # cand_window=1024, ISSUES.md:1012); that is a Sample, and it belongs below the instrument line.

    mint_novel = Lever(0.0, "Exponent re-ranking mint candidates by how much a pair has grown since it "
                            "was last considered; 0 reproduces plain most-frequent minting.", U.FRACTION)
    # Census: TOK_MINT_NOVEL -> TOK_MINT_NOVEL, verdict keep. Field corrected (DEFECT 1).
    # THE MOST DIRECTLY GOAL-B-RELEVANT KNOB IN THIS PACKAGE. most_common(1) mints the globally most
    # frequent pair, which by construction re-segments ALL existing material at once, and tokenizer.py
    # :243-254 names that for what it is: "in a system whose point is continual learning, that is
    # backwards: a new area arriving should buy vocabulary for ITSELF, not rewrite how everything already
    # learned is spelled." Nothing else in this package addresses that, and it is the tokenizer's own
    # version of catastrophic forgetting.
    # NOT DROPPED DESPITE ONE BAD RUN, and the reason is a defect rather than a preference: pilot_gru_8
    # at TOK_MINT_NOVEL=0.5 landed at 5.360 held-out (:974), a single arm with a confounder, and the
    # mechanism has a known open bug that would explain it -- the fail-open fallback claims to take "the
    # most frequent candidate clearing min_pair", but _top has ALREADY been re-sorted by novelty, so it
    # takes the most NOVEL one instead (ISSUES.md:573). The two re-rankers were designed to compose and
    # the fallback silently inherits one. Fix that before re-measuring; a number taken against a broken
    # composition is not evidence about the mechanism.
    # UNIT IS A LABEL AND IT IS THE CLOSEST WRONG ONE. This is a dimensionless EXPONENT, not a proportion.
    # U.FRACTION is what the metadata list carries; the census says so in as many words, and a reader who
    # takes "fraction 0..1" as a bound on legal values will be surprised by 2.0, which is legal.

    dropout = Lever(0.0, "Probability of skipping an available merge during a counting segmentation, so "
                         "byte-level material still reaches the tally.", U.PROBABILITY)
    # Census: TOK_DROPOUT -> TOK_DROPOUT, verdict keep. Field corrected (DEFECT 1) -- CENSUS.md:299 names
    # the target `TOK.TOK_DROPOUT`, which would have answered to TOK_TOK_DROPOUT.
    # THE NEVER-FIRED CASE, NOT THE SUPERFLUOUS CASE. BPE-dropout is a real regularizer; the default is
    # 0.0 so it has never run, and the owner ruled that a mechanism never observed to fire is not thereby
    # proven useless -- several were inert because the INSTRUMENT was broken.
    # IT CARRIES ONE HARD REQUIREMENT INTO THE REBUILD AND IT IS NOT OPTIONAL. tokenizer.py:188-190 draws
    # from the process-global `random`, so any value above 0 shifts the RNG stream of the ENTIRE RUN --
    # including maintenance segmentations that are supposed to be observational -- in a codebase that
    # otherwise guards this carefully (frozen_rng and no_rng_drift exist because diagnostics were
    # silently editing runs, ISSUES.md:1016). It must draw from this package's own generator via
    # spine/rng.py. Without that, G3's fingerprint diff reads this lever as a coupling into every other
    # package, and L3's isolation sweep -- whose only oracle is affects() -- reports a leak that is real
    # but not the one anybody is looking for.

    # ==============================================================================================
    # 4. PROBATION -- what happens to a token that did not earn its slot
    #
    # Mint-then-judge is the only criterion that can see anything AFTER the merge, and the source proves
    # the alternative is impossible: greedy longest-match consumes a+b, so p(b|a) is 0 from the instant
    # of the merge. Measured directly -- mint 't'+'h', read the pair count after forty more passes -> 0,
    # and a re-test would retire 100% of candidates (:6304-6313). Four levers: how much, by when, judged
    # how, and against what threshold.
    # ==============================================================================================

    probation_uses = Lever(0, "How many appearances a newly minted token must earn before it keeps its "
                              "place in the match table; below it the merge is undone.", U.COUNT)
    # Census: TOK_PROBATION -> TOK_PROBATION_USES, verdict rename. Field corrected (DEFECT 1). Renamed so
    # the unit is in the name, beside `probation_deadline`.
    # THE FIRED-BUT-ALARMING CASE, NOT THE INERT ONE. On the probation arms it retired 217 and 224 of 256
    # minted tokens (:3986-3988). That is a signal that the threshold is miscalibrated, not that the
    # mechanism is absent -- and those same arms exposed a real bug worth carrying: a retired id sits
    # BELOW vocab_size, so it sailed straight through mask_dead until that was fixed. Any port must keep
    # retired ids in the dead-row accounting, or the loss quietly trains rows that can never be produced.
    # THE DEFAULT 0 MEANS OFF, which is what every recorded run outside those arms used.

    probation_deadline = Lever(5000, "The window by which a minted token must have earned its "
                                     "appearances, after which it is judged.", U.Windows)
    # Census: TOK_PROBATION_STEPS -> TOK_PROBATION_DEADLINE, verdict rename, unit Windows. Field
    # corrected (DEFECT 1) and the OLD NAME IS PART OF THE DEFECT: it says STEPS and the quantity is
    # WINDOWS. The test is `step - TOK.prov[t][2] >= TOK_PROBATION_STEPS` (:7598) and `step` counts
    # windows (:934, :7708), so at BATCH_W=16 reading it as steps is a 16x error in the pin_tick family.
    # Renaming it is how it stops being re-read as steps by the next person; the unit type is how the
    # comparison stops compiling if it is.
    # A WALL-CLOCK DENOMINATOR IS RIGHT HERE AND THAT IS NOT ALWAYS TRUE. TOK_ANCHOR_TAU was dropped for
    # having one by accident; this one has one on purpose. The whole point is to catch "a merge taken on
    # a transient burst", which is a statement about a RATE, and a rate needs a denominator in time
    # (:6321-6323).

    probation_by = Lever("use", "Which post-mint test decides whether a token keeps its slot: did it get "
                                "used, or did its learned residual move away from what its bytes say.",
                         U.NAME, choices=("use", "embed"))
    # Census: TOK_PROBATION_BY -> TOK_PROBATION_BY, verdict keep, choices=("use","embed"). Field
    # corrected (DEFECT 1).
    # BOTH ARMS ASK GENUINELY DIFFERENT QUESTIONS (:6320-6327) and both are worth having: "was it used"
    # is about the stream, "did its embedding have to become something its parts did not already say" is
    # about the model.
    # choices= CLOSES TWO HOLES AT ONCE, AND THIS KNOB IS ONE OF THE ELEVEN M24 NAMES (with DATA_MODE,
    # SIG_MODE, MODEL, VERIFY, LR_SCHED, KEY_SRC, SIG_SPACE, EVICT, CULL_MODE, WARMSTART_MODE,
    # CHAIN_ROUTE). (1) An unrecognised value falls into whichever branch is the else rather than being
    # refused, compared case-sensitively -- the same class as DATA_MODE=Real silently taking the
    # synthetic branch (ISSUES.md:361, :2093). TOK_PROBATION_BY=Embed ran the "use" test and said nothing.
    # (2) TOK_PROBATION_BY=embed with TOK_COMPOSE=0 leaves _emb = None and falls through to the "use"
    # test with NO warning anywhere, while the banner prints the requested mode and the end-of-run
    # [vocab] line at :7864 reports "judged by embed" (M41) -- a wrong-measurement record in the largest
    # defect class in the survey. choices= fixes (1) outright. It does NOT fix (2): the embed arm must be
    # reachable only through a declared Gate on the composer's existence, and the arithmetic must print
    # when that gate is shut. See the d_residual_ratio note in the header -- the wire that arm needs is
    # not in the ledger yet.

    probation_residual = Lever(0.10, "Minimum ratio of a token's learned residual to its byte composite "
                                     "for the token to be judged worth its slot.", U.FRACTION)
    # Census: TOK_PROBATION_MIN -> TOK_PROBATION_RESIDUAL, verdict rename. Field corrected (DEFECT 1).
    # Renamed so the name says what it MEASURES rather than which knob it sits beside.
    # ||delta|| / ||composite|| IS "HOW MUCH THIS TOKEN HAD TO BECOME THAT ITS PARTS DID NOT ALREADY
    # SAY", and near zero means the parts explain it (:6324-6327, computed at :7601-7611).
    # A GENUINE SECOND PARAMETER, NOT A DUPLICATE OF probation_uses, BECAUSE THE TWO TESTS COMPOSE:
    # :7607-7611 requires _earned AND the residual test, for a stated reason -- "a residual that is near
    # zero because the token was never seen says nothing about the merge". Dropping either turns a
    # two-sided judgement into a one-sided one that retires tokens for not having been looked at.
    # THE THRESHOLD IS TOK'S; THE RATIO IS NOT. The ratio is computed from model.compose and arrives as
    # the wire d_residual_ratio from LM. The retire decision stays here because retirement pops from
    # seq2id, which is this package's table and nobody else's.
