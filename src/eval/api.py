"""EVAL -- the frozen public surface. Signatures only; P4/P5/P6 write the bodies.

EVAL owns EVERYTHING THAT MEASURES THE RUN AND NOTHING THAT CHANGES IT -- the instrument line.
Several knobs arrive here from the packages they grade (aff_min from the fabric, verify_fit_steps
from the store, genuine_min/genuine_sil from `misc`) for one reason: a threshold that only shapes a
PRINTED number must not ride in the Config a mechanism receives, or the fabric grades its own
affiliation report. Against goal A it is gen_* and coh_*; against goal B it is holdout_windows, the
only instrument that answers "did adding an area damage what was already known". Every lever here
is a sample size or a threshold, because both project goals are CLAIMS and a claim is only as good
as the instrument under it.

WHICH OF THESE ARE LIVE AT WHICH PHASE, STATED RATHER THAN IMPLIED. P3's exit criterion is "no
report at all beyond loss", so at P3 exactly one function below is called by the composition root:
curve_period, because the loop needs a cadence slot and CKPT's Retention needs a number to compare.
curve_probe / holdout_probe / null_excess are P5. The five instruments at the bottom are P6. THEY
ARE DECLARED HERE ANYWAY, and that is a deliberate choice this contract records: an instrument
declared with a signature has a named reader for its levers, so `EVAL_GEN_TEMP` is a knob whose
consumer is written down rather than one of the 57 armed-but-inert records. What P6 owns is the
BODY, not the interface.

THE EIGHT STUB MARKERS BELOW SAY P5/P6 WHILE THE OTHER TWELVE PACKAGES SAY P4, AND THEY STAY THAT
WAY. RE-CHECKED 2026-09-04 AND THE RULING STILL HOLDS: .rework/ISSUES.md P2-H11 rules that the
PHASES renumber and the markers do not, that eval's markers move WITH the renumbering, and that the
renumbering is deliberately NOT YET APPLIED because it touches every row below P2 while the phase
in flight is P4 under the split numbering. Counted rather than assumed: three stub markers here
name phase P5 -- curve_probe, holdout_probe, null_excess -- and five name P6 -- generate, coherence,
verdicts, wrongness_probe, verification_fit -- against the P4 marker the other twelve api.py files
carry, and docs/04_CONTRACT.md's EVAL section attributes the SAME P5/P6 phases to these same entry
points. (The phase names are spelled without their parenthesised package here ON PURPOSE: the
obvious way to check this paragraph is `grep -c` for the marker string, and a marker quoted inside
the count that describes it is a claim that corrupts its own measurement -- which is this file's
subject, one level up.) So rewriting these eight to P4 would apply half of a deferred renumbering and put this
file at odds with the document that declares it. THIS PARAGRAPH EXISTS SO THE NEXT READER DOES NOT
"FIX" IT EITHER: the open item is the renumbering, and it belongs to whoever applies PLAN.md
section 5's amendment, not to this package.

TWO RULES EVERY FUNCTION BELOW OBEYS, both from the survey:
  G7  an instrument may not leave the model in a different mode than it found it, and may not move
      an RNG stream. Every probe runs under spine.rng.frozen_rng and draws from its own named
      stream. Before c76dc74, changing the holdout n from 4 to 16 moved 48 report lines INCLUDING A
      VERDICT SIGN FLIP, because build_stream drew segment lengths from the same global RNG the
      diagnostics drew from -- how much you MEASURED decided what you TRAINED on.
  ONE LOGITS PATH, RESTATED 2026-09-02 UNDER Q-MEM-10 AND STILL ONE PATH PER SYSTEM. `logits_fn`
      is passed in, never constructed here. compose_test built `pm` from `model(X)[0]`, the plain LM
      head, while the held-out path used _eval_logits, so with FABRIC=1 three report sections scored
      a system the run never trained. The rule is therefore: ONE CLOSURE PER SCORED SYSTEM, formed
      in the composition root, passed in, never constructed here -- AND EVERY READING NAMES WHICH
      CLOSURE PRODUCED IT. There are two systems and not one: the trained path (memory off) and the
      trained path plus retrieval (memory on), which has never entered training. The -0.097 -> +0.085
      b/B price of retrieval IS the difference between them, so the PAIR is the deliverable and a
      single unnamed number is the defect. NO SIGNATURE HERE MOVES FOR THIS: `blend_fn` is NOT added
      to curve_probe, holdout_probe, generate or coherence -- see Q-MEM-10 in docs/04_CONTRACT.md,
      which recommended exactly that and was overruled, because four bodies each doing
      softmax -> blend -> log is the ungated mix recomputed at a consumer site, i.e. C8 (prompt.py)
      and C9 (cl_bench.py) rebuilt inside the instrument line.

TWO DECLARED OUTPUTS HAD NO CHANNEL IN THE FROZEN SIGNATURE THAT MUST PRODUCE THEM (found
2026-09-03, referred twice for want of an agent owning both sides). BOTH ARE CLOSED, 2026-09-04, BY
WIDENING THE SIGNATURE ON BOTH SIDES AT ONCE -- docs/04_CONTRACT.md's Q-EVAL-11 carries the full
ruling and the alternatives; what follows is what the two `def` lines now say and why:
  * `CurveReading.step` is returned by curve_probe, whose signature was
    `(ev, *, units_by_domain, logits_fn, rng)`. `step` is RUN's window counter; no argument carried
    it and EVAL owns no clock, so the field could not be filled by the function that returns it.
    curve_probe now takes `step`, and A WIRE WAS NEVER AVAILABLE HERE: a Coupling.compute receives
    only frozen Configs and Config freezes when build() returns, so a per-window counter is refused
    on the same ground as d_curve_bpb and d_shift_at already are in spine/assemble.py::NOT_WIRES.
  * `verification_fit`'s DID IT FIRE declares a Gate on `verify != "off"` -- MEM's lever -- and the
    signature was `(ev, *, store_copy, rng)`, which had no such parameter. MEM's Store carries no
    verify field either (its __slots__ are the entry arrays, the block partition and the census,
    re-checked 2026-09-04 against memory/api.py::Store), so the value could not be recovered from
    `store_copy`, and reading MEM's Config here is exactly what owned_by refuses. verification_fit
    now takes `verify_mode`, which the composition root reads off MEM's frozen Config -- the same
    idiom the root already uses for `vocab_slots=LM.vocab_slots` and `lm_kind=LM.arch` into
    MEM.open_store, and for `sig_dim=SIG.d` into DOM.open_partition.
THE WIRE WAS THE OTHER CANDIDATE FOR THE SECOND ONE AND IT LOST ON ITS MERITS, not on its price.
EVAL DECLARES NO WIRES AND RECEIVES NONE, and that is a design statement rather than an accident:
this package measures the run and changes nothing in it, so a value it consumes to RENDER A GATE
never reaches a mechanism. The ledger has room -- 19 cross-package wires against a budget of 25, so
six edges remain, and the "two left" this paragraph carried until 2026-09-04 was a miscount of
couplings as wires -- and the argument is still the wrong thing to spend one on. THE GATE AND THE
FIELD STAYED DECLARED THROUGHOUT. Deleting either to make this file self-consistent would have
traded a recorded gap for a silently missing reading, which is the trade this package refuses.

RECORD TYPES RETURNED (P4/P5 define them):
  CurveReading   per_domain_bpb, mean_bpb, windows_drawn, units_drawn (the total this probe spent:
                 windows_drawn summed across domains x LM.ctx -- Q-EVAL-5), step
  Reading        value, seed_count -- PLAN 3.8 forbids a verdict on n=1, and OPT refuses to damp a
                 restart on a Reading whose seed count is 1
  NullReading    real, null_mean, null_sd, draws, verdict_allowed
  Sample         the measured population, its SIZE, and the rule that drew it
"""
from spine.lever import Config
from spine import units as U


def curve_period(ev: Config):
    """The learning-curve cadence, AS units.Windows. Handed to RUN's Cadences.due.

    UNIT IS Windows: the guard is `step % RATE_EVERY == 0` (:6385) and `step` advances per WINDOW,
    so this knob has always been denominated in Windows while its name and every discussion of it
    said steps. The block sits ABOVE the batch early-out, so unlike CKPT_EVERY it DID fire -- it
    was the LABEL that was wrong, not the gate.

    RENAMED *AND SPLIT*. One cadence drove five unrelated things: the curve probe (:6385), the
    rate/ETA meter (:6489), the profiler dump, the per-expert LR line (:7297) and the
    no-eligible-expert line. Setting RATE_EVERY=100000 to quieten smoke runs SUPPRESSED THE CURVE
    TABLE ENTIRELY, so the curve fix went unverified on a live table for a whole round. Here the
    MEASUREMENT cadence is this lever and the progress line takes RUN's own fixed constant --
    RUN.PROGRESS_WINDOWS, 100 Windows, a module constant with no environment name (Q-RUN-1, RESOLVED
    2026-09-02, and this file's wording was the one of the three that was already right) -- so
    quietening a log can no longer disable a measurement, and there is no log knob left to turn up.

    LEVERS READ: curve_every
    WIRES READ: none
    DID IT FIRE: Cadences.ledger()["curve"]
    """
    ev = ev.owned_by("EVAL")
    # NOT A STUB, AND THE FOUR SIBLINGS ARE NOT EITHER -- DOM.manage_period, FAB.manage_period,
    # MEM.rekey_period and CKPT.save_period, each verified stub-free. This comment said THREE, which
    # is the same off-by-one docs/04_CONTRACT.md corrected in its own sentence about these five
    # accessors on 2026-09-03, one row over and for the same reason it gave: the number is spelled
    # as a WORD and tests/test_contract.py's K13 reads digits, so nothing in the tree could see it.
    # A period accessor is one
    # construction over one declared lever, and its whole job is that Cadences.due REFUSES a
    # bare int while Config hands one back for all 35 levers that declare a Clock unit
    # (ISSUES P1-H51). Leaving it a stub kept spine.compose._periods -- and therefore
    # RUN.cadence_audit, the one statement that makes ISSUES P1-C11 visible -- unreachable
    # until P4, for no reason but symmetry with entry points that have real work to do.
    return U.Windows(int(ev.curve_every))


def curve_probe(ev: Config, *, units_by_domain, logits_fn, step, rng):
    """One learning-curve probe. Returns CurveReading.

    THE SAMPLE SIZE IS ev.windows AND NOT A HARDCODED 16 (Q-EVAL-5, RESOLVED 2026-09-02 -- read the
    lever). The old probe drew `range(16)` at :6396 while the lever's own help text quotes that 16
    as if it were declared -- an undeclared second default INSIDE THE SENTENCE DESCRIBING THE LEVER,
    which is the L1 shape arriving through the document written to end it. The old EVAL_N was
    UNRAISABLE -- five of its six readers wrapped it as min(24, EVAL_N) or min(48, EVAL_N), so
    EVAL_N=256 drew 24, the untrippable-guard shape -- and hardcoding 16 here would rebuild it. An
    operator who wants the old cost sets EVAL_WINDOWS=16 and gets exactly it, which is what makes
    reading the lever strictly better than the literal rather than merely tidier.

    THE COST, WITH THE NUMBER AND THE CONDITION ON IT. `ev.windows` resolves to 64, so the multiplier
    is 64/16 = 4x, and it belongs on P9's list of numbers expected to move. BUT IT IS 4x OF ZERO AT
    THE SHIPPED DEFAULTS AND THE P9 ENTRY MUST SAY SO: curve_every=2000 against a default run of
    506-937 windows (DATA.stream_bytes=120000, LM.ctx=128, RUN.epochs=1) means this probe NEVER
    FIRES, which is ISSUES P1-C11. An unconditional "the default probe cost rose 4x" is a number nobody
    can reproduce -- the failure P9 exists to prevent -- so the entry reads "4x on runs long enough
    to probe; does not exist at the shipped defaults". If the C11 run-length ruling raises
    stream_bytes or epochs, this question should be re-read, not carried.

    `step` IS RUN'S WINDOW COUNTER AND IT ARRIVES AS AN ARGUMENT, ADDED 2026-09-04 (Q-EVAL-11).
    CurveReading carries `step` -- it is what makes a curve a curve, and what CKPT's Retention
    compares one reading against another by -- and until this edit the signature had no channel for
    it: EVAL owns no clock, `units_by_domain` carries material rather than position, and a probe
    that stamped its own reading from a counter it invented would be a second source of truth for
    RUN.RunClock. A WIRE COULD NOT HAVE CARRIED IT: spine/assemble.py::COUPLINGS computes from
    FROZEN Configs and a window counter is runtime state, which is the ground NOT_WIRES already
    refuses d_curve_bpb and d_shift_at on. The composition root passes RunClock's window index when
    P5 writes the row; the value is RUN's, and it is stamped, never derived here.

    LEVERS READ: windows
    WIRES READ: none
    DID IT FIRE: CurveReading.windows_drawn PER DOMAIN -- a domain that yielded zero windows is
                 REPORTED, not skipped (the recorded case: CAN A DOMAIN PREDICT needed 16 and drew
                 min(48, EVAL_N), so at EVAL_N=4 it collected 4, produced nothing, and DOM_PRIOR
                 was accumulated and never read) -- AND THE TOTAL THIS PROBE SPENT, windows_drawn
                 summed across domains times LM.ctx, so the sample size is a knob whose cost is
                 VISIBLE as well as raisable and lowerable. That asymmetry is what EVAL_N failed:
                 it could only ever be lowered, and nothing printed what it bought.
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.curve_probe: P5 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def holdout_probe(ev: Config, *, units_by_domain, logits_fn, rng):
    """The retention probe: held-out bits/byte per domain, KEYED BY DOMAIN NAME so adding a domain
    does not shift the comparison. This is the R matrix's resolution and the entire error bar on
    "did adding an area damage what was already known".

    WINDOW STARTS ARE DRAWN IN BYTE COORDINATES from DATA's held-out block and tokenize() is
    applied to the fixed byte windows. ISSUES P1-H20: :5087-5088 drew them as
    `randint(0, len(_v) - WIN - 2)` where `_v` is the TOKENISED validation text, whose length
    shrinks over a run under online minting and differs between parent and child -- so `prev` and
    `now` were measured on DIFFERENT WINDOWS, on the one number the file calls "the ONLY number
    that spans the run boundary". Segmentation.byte_pos exists precisely so every coordinate that
    must survive a re-segmentation can be a byte offset.

    `units_by_domain` carries DATA's Areas.holdout_bytes with it, and the SIZE is recorded on the
    Sample: ISSUES P1-M82 is precisely the case where two configurations covered different amounts of
    text and neither report said so.

    THE COMPARISON IS PAIRED, AND THE PAIRING IS PINNED HERE RATHER THAN LEFT TO P5 (Q-EVAL-9,
    RESOLVED 2026-09-02: holdout_windows STAYS AT 32, and this clause is what earns that).
    Each domain's window starts are drawn ONCE, from rng_for("eval.holdout." + domain_name, seed) --
    the domain's stable NAME normalised to spine/rng.py's charset, exactly as DATA derives one
    "data.holdout.<area>" child per area for the same reason -- and are IDENTICAL at every probe of
    the run and across a resume. The 2-sigma verdict is then computed on the PAIRED per-window
    differences and the Reading carries the paired SD.
    WHY THAT IS THE WHOLE ARGUMENT FOR n=32. H20's repair above fixes WHICH windows are scored (byte
    coordinates, so a re-segmentation cannot move them); pinning the DRAW fixes that `prev` and `now`
    are the SAME windows, and on the same windows the per-window difficulty term CANCELS in the
    difference. Window-to-window bpb spread in text is large (order 0.3-0.5 b/B); the spread of a
    paired difference on fixed windows is far smaller. So n=32 PAIRED is a materially stronger
    instrument than n=32 unpaired, and research_continual_memory.md:743-745's warning that the
    2-sigma rule at n=32 reports "HELD (inside the noise)" for real effects -- and its 128-256
    recommendation -- is calibrated for the UNPAIRED case.
    NOTHING IN THE TREE PINS IT TODAY, WHICH IS WHY IT IS WRITTEN HERE: this function takes an `rng`,
    and spine/rng.py's frozen_rng protects the GLOBAL streams and explicitly does not cover streams
    handed out by rng_for(). If P5 lets that stream advance between probes the pairing is lost
    SILENTLY, no check in the tree sees it, and the number reverts to the unpaired power the research
    doc warns about.
    THE ORDER OF OPERATIONS, so it cannot be got wrong: PIN THE PAIRING, then let G2 measure this
    machine's noise floor, then decide n. Raising n before pairing buys the smaller of the two
    available variance reductions at 8x the cost. And the DOMINANT error bar is neither: PLAN 3.8
    records a between-seed spread of 0.066-0.131 b/B, which exceeds every architectural difference
    this project has ever claimed, and the renderer already refuses a verdict on n=1.
    THE HONEST CAVEAT, per C11: at the shipped defaults 32 windows x LM.ctx=128 is about 7.6 kB of
    text per domain, a sample smaller than one splice segment, against a run of 506-937 windows. If
    the owner raises DATA.stream_bytes, re-ask this question with the noise floor in hand.

    LEVERS READ: holdout_windows
    WIRES READ: none
    DID IT FIRE: windows drawn per domain, and the SEED COUNT carried on the Reading; plus the
                 PAIRED SD and, per domain, whether its "eval.holdout.<name>" stream had already
                 been drawn (rng.issued() makes "this domain's holdout stream was never drawn" a
                 reportable state rather than a silence, and a probe whose starts moved between two
                 calls is the one failure this whole clause exists to make visible)
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.holdout_probe: P5 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def null_excess(ev: Config, *, real, permute, rng):
    """The permutation null every 2-sigma verdict is judged against. Returns NullReading.

    REFUSES draws < 2 AT CONSTRUCTION. ISSUES P1-L44: null_draws=0 gives an empty list and
    `sum(_nl)/len(_nl)` is a ZeroDivisionError that takes the whole remainder of the report with it
    (compose_test at :8949 has no try/except while the very next section does). L45: at 1 draw the
    sd is exactly 0.0 and `real - null > 2*sd + 1e-9` reduces to "any excess above 1e-9" -- a
    rubber stamp. `choices=` cannot express "any integer >= 2", so the floor belongs here, as a
    refusal. Two runs of the SAME configuration once printed opposite conclusions at excess +0.010
    and +0.013 against a 0.010 cutoff.

    LEVERS READ: null_draws
    WIRES READ: none
    DID IT FIRE: NullReading.draws, and verdict_allowed=False WITH A REASON when the floor bites
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.null_excess: P5 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


# ==================================================================================================
# THE P6 INSTRUMENTS. Declared here so their levers have a named reader; P6 writes the bodies.
# ==================================================================================================

def generate(ev: Config, *, logits_fn, prompts_by_domain, rng):
    """Sampled continuations, per domain, for the text judgements. Returns a Sample.

    EVERY TEXT JUDGEMENT IN THIS PROJECT'S HISTORY RESTED ON A SINGLE 200-TOKEN CONTINUATION: 91%
    vs 71% "real words" were three or four words apart. gen_samples x gen_domains is the sample the
    Sample records, and prompt.py:168 declares its OWN GEN_LEN default and a GEN_TEMP of 0.6
    against the registry's 0.7 -- a live L1 violation in the one script that exercises the
    deliverable by hand, which is why prompt.py receives this frozen Config instead of re-reading
    the environment.

    LEVERS READ: generate, gen_samples, gen_domains, gen_len, gen_temp
    WIRES READ: none
    DID IT FIRE: Sample.size and the per-domain counts; `generate` off is unreachable, not zero
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.generate: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def coherence(ev: Config, *, logits_fn, units_by_domain, encode, rng):
    """The coherence Reading over its OWN seeded sample, not over the printed generations.

    It was scored on the four printed GENERATION samples, ~2 windows each, so every coherence
    number ever printed landed on 0.25/0.50/0.75/1.00 -- a four-sample mean with SE 0.25. "memory
    HELPS (0.50 -> 0.75)" was ONE SAMPLE FLIPPING, reported as a finding twice, in opposite
    directions on consecutive runs. coh_seeds and coh_len size a sample this instrument draws for
    itself.

    THE PARAMETER WAS `sample` UNTIL 2026-09-02 AND THAT IS WHAT LET THE DEFECT HAPPEN
    (Q-EVAL-10, RESOLVED). A `Sample` is the object EVAL.generate returns -- the printed
    generations -- so the signature invited exactly the argument the sentence above forbids, and
    the old code passed it. What this instrument needs is MATERIAL, not a measurement:

      units_by_domain  the same per-domain unit stream curve_probe and holdout_probe take, in the
                       same shape and under the same name, because ONE CALLABLE OR ONE RECORD
                       DECLARED TWICE WITH TWO SHAPES is how a signature width came out 614 on one
                       path and 1 on the other. coh_seeds seeds are drawn FROM it, one per domain
                       in rotation, and the CEILING -- real text of the same length scored the same
                       way -- is cut from it too. The per-domain keys are load-bearing: HOME is the
                       key of the bucket a seed came from, so the strict arm needs no lookup.
      encode           SIG.encode bound to the SigState -- the SAME callable DOM.rekey takes, and
                       the composition root already forms it (_sig_encode_fn). It is here because
                       the measurement IS an encoding: "which centroid is this window of the
                       CONTINUATION nearest" is evaluated per generated window on BOTH arms, and
                       EVAL may not import SIG. Without it this function cannot be written at all.
                       It also builds the TRUE-CORPUS centroids from units_by_domain, which is the
                       stricter reference: scoring against DOM's assembled partition instead would
                       be the self-referential arm, and shipping only that arm would silently
                       downgrade the metric to "the encoder is self-consistent".

    `rng` was always the tell that this instrument draws: a function that only SCORES a handed-in
    sample has no draw to seed, and G7 says every probe draws from its own named stream.

    THE SELF-REFERENTIAL ARM IS STILL P6'S, AND IT NEEDS NOTHING FURTHER FROM THIS SIGNATURE. On a
    run with fewer than two labelled buckets there are no true-corpus centroids; the fallback is
    the partition the system assembled, and HOME is then MEASURED per seed by encoding it and
    taking the nearest centroid (eval/levers.py, coh_seeds) -- with `encode` in hand that is this
    function's own arithmetic. It must be LABELLED as the weaker claim wherever it is printed.

    LEVERS READ: coh_seeds, coh_len, gen_temp
    WIRES READ: none
    DID IT FIRE: Sample.size, and the Reading's seed count. The arm is part of the record: strict
                 (true-corpus centroids) or self-referential, never silently one of the two.
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.coherence: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def verdicts(ev: Config, *, domain_sizes, silhouettes, affiliation, coherence_reading):
    """The genuineness and affiliation verdicts, each as a Reading with its own null.

    The predecessor genuineness test was `coh >= 0.5 AND sep >= 0.10`, A CONJUNCTION WHERE ONE
    CLAUSE COULD NEVER BE FALSE; and the sizes it tested came from THE REPORT LOG, so a domain of
    ~2100 members printed as "size 134" -- 1/BATCH_W of the truth. `domain_sizes` therefore arrives
    from DOM.census(), never from a log line.

    LEVERS READ: genuine_min, genuine_sil, aff_min
    WIRES READ: none
    DID IT FIRE: each verdict's Reading with its sample size and its null; a verdict refused for
                 n=1 is a reported state, not a missing line
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.verdicts: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def wrongness_probe(ev: Config, *, store_copy, scorer, rng):
    """The injected-wrongness precision/recall Reading, ON A COPY OF THE STORE.

    THE OLD BLOCK MUTATED WHAT IT MEASURED -- force-writes injected entries, runs selfcheck,
    deletes src 99, then `mem.selfcon.fill_(-1.0)` -- so every later section scored a store the
    report had edited. It must be a Sample on a COPY with the G7 digest asserted around it. It is
    also UNDEFINED BELOW TWO SOURCE DOMAINS: the unguarded version raised IndexError and took the
    whole battery down AFTER training and checkpointing completed, which is why the guard is a
    declared Gate and not a try/except.

    Injected entries carry src = -2, which MEM reserves for non-domain provenance, so the harness
    can never collide with a real domain id (H30 -- the old one used src=99).

    LEVERS READ: wrongness, wrong_inject
    WIRES READ: none
    DID IT FIRE: Sample.size, precision, recall, and the Gate that says "unreachable (fewer than
                 two source domains)" with the count
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.wrongness_probe: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def verification_fit(ev: Config, *, store_copy, verify_mode, rng):
    """Fit the Reconstructor POST HOC on a SETTLED store and report its precision.

    The joint in-loop fit trained against a churning, re-tokenized, re-keyed store -- its targets
    moved while it fit -- and reached 0.3% precision. Post hoc the target is fixed. `verify_fit_steps`
    is genuine units.Steps: optimizer steps of a small separate model, in a loop with no windows
    and no flushes in it. THIS IS THE ONE PLACE IN THIS FILE WHERE units.Steps IS LITERALLY WHAT IS
    COUNTED, and it must never be compared against curve_every.

    `verify_mode` IS MEM'S `verify` LEVER, ARRIVING AS AN ARGUMENT, ADDED 2026-09-04 (Q-EVAL-11).
    It exists for the Gate below and for nothing else: the post-hoc fit is a reading ABOUT the
    judge the run actually used, and at MEM_VERIFY=off the run judged nothing, so the precision
    this function reports is the precision of a mechanism no run consulted. That has to be on the
    line, not inferred by whoever reads it. It is an ARGUMENT and not a wire: EVAL declares no
    wires and receives none, a value consumed to render a Gate never reaches a mechanism, and the
    composition root already passes another package's frozen lever this way for
    MEM.open_store(vocab_slots=LM.vocab_slots, lm_kind=LM.arch) and
    DOM.open_partition(sig_dim=SIG.d). IT MAY NOT BE RECOVERED FROM `store_copy`: memory/api.py::
    Store's __slots__ are the entry arrays, the block partition and the census, with no verify
    field -- and inferring the mode from whether Store.recon or Store.selfcon holds values would
    read a configuration off the data, which is the shape this whole file exists to refuse.

    LEVERS READ: verify_fit_steps
    WIRES READ: none
    DID IT FIRE: the fit's step count, its precision, and the Gate on `verify_mode != "off"` --
                 which is MEM's lever, so the gate is rendered from the value the composition root
                 passed rather than from a read of MEM's Config, which owned_by refuses. THE GATE
                 IS BUILDABLE AS OF 2026-09-04: it was declared against a signature with no channel
                 for its input from 2026-09-03, recorded rather than deleted, and the channel is
                 now the `verify_mode` parameter above. The Gate stays declared either way: an
                 instrument that silently omits a reading because its input was never wired is the
                 armed-and-inert failure with the evidence removed.
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.verification_fit: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")
