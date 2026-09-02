"""OPT -- the frozen public surface. Signatures only; P4 writes the bodies.

OPT owns every rate the system applies and the size of the batch that rate acts on. Every rate is
`lr` times a multiplier in 0..1, and OPT owns the peak, the multiplier's shape, the decoupled
weight decay handed to both AdamW instances, and the two counts whose product is the effective
batch.

ON GOAL A it is the leading standing hypothesis for why language production has not worked yet:
all 17 pilots bottom in held-out bits/byte at ~2.4 around step 6000 and then RISE to ~3.8-4.1 by
48,000 -- across GRU and transformer, fabric and FABRIC=0, every routing variant (:7003-7011). A
cause common to every arm cannot be the fabric or the router. A constant 2e-3 on AdamW for 48k
steps is exactly that shape, and lr_sched="none" is the one-flag ablation for it.

ON GOAL B three levers are about forgetting rather than convergence. lr_min_frac exists because a
schedule that anneals to nothing cannot learn anything that ARRIVES LATE, and the add-area entry
point is the late-arrival case. lr_shift_warm is the schedule's half of note_shift(): growth is
already told "this jump is OURS, not the data's" while the learning rate meets the same fresh text
at 96-99% of peak. weight_decay is a forgetting term THE OPTIMISER introduces -- decoupled decay
is applied every step to every parameter regardless of gradient, so a dormant expert loses ~71% of
its magnitude over a 62.5k-step run.

THE COUNTER IS OPTIMIZER STEPS AND THAT IS THE UNIT REPAIR. OPT maintains its OWN counter of
optimizer steps, advanced only inside maybe_step, and hands THAT to lr_at, so units.Steps becomes
literally true for the counter. At the shipped defaults batch_windows=1, accum=1 the two counters
coincide, so no recorded result moves; at fetch_big.py's own recommended heavy-run command
(WIN=256 BATCH_W=16 ACCUM=4) they differ by 64x.

AND THE HORIZON STILL NEEDED A CONVERSION, WHICH THIS PARAGRAPH USED TO DENY. It said "no
conversion function is needed -- which matters, because spine/derive.py has no Windows->Steps
function today (verified)", and then the horizon four lines below did

    run_steps = max(1, run_windows // d_effective_batch_windows)

which IS a Windows->Steps conversion: a window count divided by windows-per-optimizer-step, inline,
on bare ints, in a package body. A reviewer found the assertion and the line together. Nothing was
numerically wrong at the defaults -- that is what made it survive -- but units.py:86 is explicit
that the point is naming: "There is no implicit path between kinds ... call the named function in
spine.derive that already knows the rate, so the conversion exists in one place with a name." It
was the only unnamed cross-kind conversion left in the tree.

It is now derive.opt_steps_from_windows(Windows(run_windows), effective_batch_windows) -> Steps,
which refuses a non-Windows at one end and a divisor below 1 at the other. The divisor spans BOTH
boundaries at once -- batch_windows is windows per flush, accum is flushes per optimizer step -- so
the answer is in optimizer steps, which is the only kind units.py allows an LR horizon. Dividing by
batch_windows alone would give Flushes and is a different function, flush_period_windows, on
purpose.

RECORD TYPES RETURNED (P4 defines them):
  OptState     base (the AdamW over param_groups["base"]), encoder (the AdamW over
               param_groups["encoder"]) -- THE TWO FIELDS ARE NAMED, AS OF 2026-09-02, Q-OPT-7:
               this line said "both AdamW instances" and named neither, so SIG.warm_up and
               SIG.train_step were handed the whole state with no expression for "the encoder one",
               and WORLD.manage's `add_param_group` deferral cited the identical hole. One
               vocabulary, and the words are build()'s own param_groups keys. K11 resolves a
               `produces` token against this block, so `encoder` is now a CHECKABLE provenance
               token rather than a comment;
               n_backward (Backwards), opt_step (Steps), lr_prev, restart_amp, cycle_best,
               cycle_index, horizon, param_group_shape, counters
  Horizon      run_steps, warmup, wavelength, n_cycles
  StepOutcome  stepped, lr, restart, damped
  LoadReport   restored, refused, reason

`param_group_shape` IS IN THAT LIST BECAUSE load_state REFUSES ON IT (Q-OPT-4). state_dict wrote
every other field and not that one, so ISSUES L50's refusal -- the one thing standing between a
resume and AdamW moments attached positionally to the wrong tensors -- compared against a value
nothing produced. An untrippable guard reads exactly like a guard that never had to fire.
"""
from spine.lever import Config
from spine import derive


def build(opt: Config, *, param_groups, run_windows):
    """Construct both optimizers, resolve the schedule horizon, and refuse the illegal settings.
    Returns an OptState.

    THERE IS NO `resume` PARAMETER, AS OF 2026-09-02 (Q-OPT-4, and A FROZEN SIGNATURE MOVED). It
    used to take `resume=None` and the root passed Snapshot.payload into it AND into load_state --
    one object, two entry points, adjacent rows. The overlap could not be resolved by documenting
    it, because the work the parameter would do does not exist: the live param-group structure is
    fully determined BEFORE this call (spine/compose.py restores LM, FAB and WORLD "STRICTLY BEFORE
    OPT.build", and the root assembles param_groups from those already-restored objects), so the
    checkpoint's influence on group shape arrives through the module restores, not through OPT.
    A second restore path would also move optimizer state past opt.ckpt.loaded / opt.ckpt.refused,
    which live on load_state -- counters describing one path while the state travels another.
    OPT.load_state IS THE WHOLE RESTORE PATH. The CAP analogue argues the same way and not the
    other: new_valve(restored=) takes the LIFTED CAP ALONE because Valve.origin must record where
    the starting cap came from, a fact the constructor cannot get any other way. build() has no
    equivalent fact.

    param_groups is {"base": [...Parameter], "encoder": [...Parameter]} -- plain lists another
    package's constructor returned. THOSE TWO KEYS ARE THE OptState FIELD NAMES (Q-OPT-7): the
    optimizer built over param_groups["encoder"] is st.encoder, which is what the root hands
    SIG.warm_up and SIG.train_step, and what WORLD.manage's add_param_group addresses. OPT DOES NOT WALK ANYBODY'S MODULE TREE and does not know what
    an encoder is; it knows that both get lr=opt.lr, weight_decay=opt.weight_decay (:4748/:4750)
    and that both get their param_groups' lr rewritten on every step. The old alias
    `WD = WEIGHT_DECAY` at :4329 -- one number, two names, the audit seeing only the first -- has
    no home here because the env name is generated from the field.

    THE HORIZON IS RESOLVED ONCE, HERE, IN OPTIMIZER STEPS, AND PRINTED:
        run_steps  = derive.opt_steps_from_windows(run_windows, d_effective_batch_windows)
        wavelength = opt.lr_wavelength or run_steps          # the 0 sentinel, in ONE visible place
        warmup     = min(opt.lr_warmup, max(1, run_steps // 10))
        n_cycles   = max(1, round((run_steps - warmup) / max(1, wavelength - warmup)))
                     if opt.lr_restarts else 1
    Two defects die here. The old tree resolved the sentinel by READING ANOTHER KNOB
    (`if LR_STEPS: return LR_STEPS`, else project through LR_EPOCHS, :6371) -- a computed default,
    which lever.py refuses by construction -- and the projection machinery carried its own faults:
    the cosine reached only p=0.760 on E8 and p=0.730 on E18 because the projected horizon overran
    the run, and on a resume `_ep_start` started at 0 while `step` started at the checkpoint's
    step, so the first epoch length was inflated and every remaining epoch was priced at half the
    last, latched and never revised upward (ISSUES H17). And the WARMUP CLAMP is a fix that must
    survive: at LR_WARMUP=1000 a 360-step run NEVER LEAVES WARMUP and trains at a third of peak
    throughout, which reads as the schedule hurting when it is the schedule never having run.

    REFUSES AT STARTUP, because every one of these was a clamp at the old read site:
      * lr_restart_damp > 1.0 -- NOTHING catches it today and it INVERTS the mechanism: the damping
        multiplies the restart amplitude CUMULATIVELY, so above 1.0 it AMPLIFIES every failed
        restart -- the ratchet the lever exists to stop, driven by the lever that stops it. The old
        `min(1.0, max(0.0, ...))` at :4739 was the only thing standing there.
      * lr_restart_damp < 0.0; lr <= 0; weight_decay < 0; lr_min_frac outside [0.0, 1.0);
        lr_decay outside [0.0, 1.0]; lr_warmup < 0; lr_wavelength < 0.
      * accum < 1 -- LOUDLY. derive.accum_due does `k = max(1, int(accum))` and clamps in SILENCE,
        which is where a typo hides; batch_windows < 1 already raises UnitError in
        derive.flush_period_windows, and this one must not be quieter than that one.
      * batch_windows < 1, for the same reason and because build() divides by it.
      * grad_clip < 0.0. Zero is OFF and is the shipped default; a negative max-norm is a typo that
        would clip every step to nothing.

    IT ALSO RECORDS param_group_shape ON THE OptState, because load_state refuses against it and
    state_dict has to be able to write it. The shape is whatever P4 makes it -- the group order and
    each group's tensor count and shapes -- but it must be computed HERE, from the live groups,
    since that is the only moment the "live" side of load_state's comparison exists.

    RECEIVES: run_windows <- RUN/DATA, resolved once after the stream and the tokenizer exist. It
    CANNOT be a build-time Coupling: the stream length in windows depends on the tokenization,
    which has not happened when build() freezes -- the same rejection assemble.NOT_WIRES gives the
    SIG width, and a DIFFERENT one from the RUN.epochs -> d_lr_horizon rejection. Both grounds are
    now rows in that table rather than prose here and in the contract (Q-OPT-1, RESOLVED).

    LEVERS READ: lr, weight_decay, lr_warmup, lr_wavelength, lr_restarts, lr_restart_damp,
                 lr_decay, lr_min_frac, lr_sched, accum, batch_windows, grad_clip
    WIRES READ: d_effective_batch_windows
    DID IT FIRE: opt.build.calls (exactly 1), opt.build.wavelength_from_sentinel,
                 opt.build.warmup_clamped (with both numbers), opt.build.cycles_fitted (n_cycles --
                 "armed" for a restart means > 1, NOT lr_restarts == 1),
                 Gate opt.build.grad_clip -- "off (0.0)" or the resolved max-norm, printed either
                 way, because "no clipping" is a run-level fact the report must state rather than
                 leave to be inferred from a missing line
    """
    opt = opt.owned_by("OPT")
    _ = opt.d_effective_batch_windows            # WIRE READ HERE -- the horizon's divisor
    raise NotImplementedError(
        "OPT.build: P4 (opt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section OPT.")


def lr_at(opt: Config, st, opt_step):
    """The rate at optimizer step `opt_step`. PURE: no closure reads, no globals, no measurement.

    lr_sched == "none" returns opt.lr flat. Otherwise linear warmup to peak over st.horizon.warmup,
    PAID ONCE and not per cycle -- the point of warmup is that the optimizer state is COLD, which
    is only true the first time (:4762-4765) -- then a cosine from peak to lr_min_frac. Under
    lr_restarts the cosine wraps into a WHOLE NUMBER of cycles fitted to the run, so every cycle
    completes and the run always ENDS annealed; truncating instead left a 30-epoch run with 2
    cycles and a THIRD of its length parked at the floor. At exactly one fitted cycle the schedule
    is bit-identical to lr_restarts=off (:4785), which keeps every earlier result reproducible.

    Three modifiers, each gated, each in this ONE function:
      * restart damping, `st.cycle_index > 0 and st.restart_amp < 1.0`: damps the SWING above the
        floor, never below it.
      * self-inflicted-shift re-warm, `opt.lr_shift_warm and 0 <= opt_step - st.shift_at <
        opt.lr_shift_warm`: an ATTENUATION (a multiply), never a replacement. Returning `lr * ramp`
        would RAISE the rate whenever a shift lands late in the anneal.
      * the monotone envelope, GATED ON n_cycles > 1: without that gate it multiplied a single
        cycle's cosine by a second cosine that also bottoms at the floor, so a run that should end
        at lr_min_frac ended at lr_min_frac SQUARED -- 0.0025 of peak. That is why LR_DECAY sat at
        0.0 from the day it was written, and three documents still say it is inert after the
        default flipped 0.0 -> 1.0.

    THE PROPERTY THE TEST MUST ASSERT, which the compounding defect above makes non-obvious: the
    schedule's minimum over a whole run equals lr * lr_min_frac at EVERY restart count,
    single-cycle included.

    LEVERS READ: lr, lr_sched, lr_min_frac, lr_restarts, lr_restart_damp, lr_decay, lr_shift_warm,
                 lr_warmup, lr_wavelength (the last two through st.horizon)
    WIRES READ: none
    DID IT FIRE: opt.lr.in_warmup, opt.lr.damped_this_step, opt.lr.shift_warm_applied,
                 opt.lr.envelope_applied (the n_cycles > 1 gate, the old _nenv)
    """
    opt = opt.owned_by("OPT")
    raise NotImplementedError(
        "OPT.lr_at: P4 (opt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section OPT.")


def scaled_backward(opt: Config, st, total):
    """Scale the composed loss by accum, call .backward() on it, advance the Backwards clock, and
    return that clock. THE SCALING AND THE COUNTING ARE THE SAME FUNCTION, ON PURPOSE.

    `(total / accum).backward()` is not optional and not separable from the gate: an accumulation
    that gates the step WITHOUT scaling the loss trains at ACCUM times the rate the operator asked
    for, which is the same defect class as the gate itself and would be invisible in exactly the
    same way. In the old tree the scaling was at :7065 and the gate at :7193, 128 lines apart.

    st.n_backward is units.Backwards, never a bare int, so it cannot be handed to a Windows
    comparison and a Windows counter cannot be handed to accum_due.

    LEVERS READ: accum
    WIRES READ: none
    DID IT FIRE: opt.backward (the Backwards count -- the DENOMINATOR of the effective batch, and
                 the number the report must print instead of the configured one)
    """
    opt = opt.owned_by("OPT")
    raise NotImplementedError(
        "OPT.scaled_backward: P4 (opt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section OPT.")


def maybe_step(opt: Config, st, *, best_bpb=None, shift_at=None):
    """Take an optimizer step if one is due. Returns StepOutcome(stepped, lr, restart, damped).

    Due-ness is derive.accum_due(st.n_backward, opt.accum), which REQUIRES a Backwards clock and
    refuses Windows(55) and bare 55. The measurement this repairs: the old gate was
    `(step + 1) % ACCUM == 0` keyed on the WINDOW counter while the body ran per flush, so it
    accumulated NOTHING at any value -- 55 om.step() calls against 13 due, over ~52 backward passes
    at BATCH_W=4 ACCUM=4 (ISSUES H29). Every learning-rate result taken against that configuration
    is filed under a batch size it was not taken at.

    When due, IN THIS ORDER:
      1. advance st.opt_step (units.Steps) -- the schedule's counter, and the ONLY thing that
         advances it;
      2. lr = lr_at(opt, st, st.opt_step);
      3. the restart detector: `st.lr_prev > 0 and lr > 1.5 * st.lr_prev and lr > 0.5 * opt.lr`.
         The second condition is not decoration -- the warmup ramp climbs from zero, so every early
         step multiplies the previous rate by far more than 1.5 and each one was logged as a
         "cosine restart" (observed at steps 15 and 31 of an 18-epoch run, at 2% and 3% of peak).
         The FIRST condition is why lr_prev is checkpointed: on a resume the old `_lr_prev` came
         back at 0.0 while `st` came back past warmup, so every resume reported a cosine restart on
         its second step ("x1145648405" -- the tell that it is lr divided by a 1e-12 floor), which
         told the growth controller the loss jump was self-inflicted ON EXACTLY THE STEP A NEW AREA
         ARRIVES;
      4. the closed loop: if a restart fired and the cycle that just ended did not beat the best
         held-out it inherited, st.restart_amp *= opt.lr_restart_damp, cumulatively. best_bpb is
         THE HELD-OUT MEASUREMENT CROSSING BACK INTO A TRAINING DECISION -- the only one in the
         system. PLAN 3.8 forbids a verdict on n=1 and a damped restart IS a verdict, so the
         Reading it comes from must carry its seed count; OPT REFUSES TO DAMP on a seed count of 1
         and records that refusal as a counter rather than damping quietly. The failure it answers
         is measured: best 2.030 @ 252,000, restarts at 263,965 / 504,894 / 756,851, final 2.848 --
         81% of the run spent getting worse, the same losing bet re-taken three times at full
         amplitude;
      5. write `lr` into EVERY param group of BOTH optimizers -- st.base and st.encoder -- then
         READ THE GRADIENT NORM, CLIP IF ASKED, and step and zero_grad THE BASE OPTIMIZER ONLY.
         Writing the rate UNCONDITIONALLY is what kills ISSUES H15: `_lrv` is assigned only inside
         `if LR_SCHED != "none"` (:7094) and read unconditionally by the per-expert path (:7195),
         so LR_SCHED="none" with FAB_LR_OWN=1 dies with a NameError on the FIRST flush. Here the
         rate always exists and always leaves this package AS A RETURN VALUE, never as a local
         another package reads.

         THE ENCODER IS NOT STEPPED HERE, AND THAT IS Q-OPT-6 RESOLVED (a), 2026-09-02. This clause
         said "step and zero_grad both" and it described something that never happened: in 9,859
         lines of self_organize.py the encoder optimizer `oe` appears exactly twice -- :5372
         (state_dict into the checkpoint) and :7154 (`for _g in oe.param_groups: _g["lr"] = _lrv`).
         There is no oe.step() and no oe.zero_grad() anywhere; :7287 is `om.step(); om.zero_grad()`,
         the base optimizer alone. The encoder was stepped only inside contrastive_step (:3401),
         which is SIG's mechanism on SIG's cadence. Stepping it from here as well would step it
         twice -- once by SIG.train_step on its Windows cadence and again by this flush gate -- and
         would destroy three declared mechanisms: SIG's floor gate returns BEFORE touching the
         optimizer when the InfoNCE loss is at the floor (:3399-3401; sig/api.py restates it as
         "the step is SKIPPED, opt untouched"), so a step taken here gates nothing; and
         sig.train_every, sig.train_every_idle and sig.dense_window -- plus the SIG.d_idle_cadence
         wire computed from two of them -- would become armed-but-inert BY CONSTRUCTION, because a
         package's cadence lever is only meaningful if that package's mechanism fires on it.
         The lr WRITE still reaches both, so the encoder runs at the schedule's rate; only the
         step and the zero_grad are the base optimizer's.

         THE GRADIENT NORM IS TAKEN HERE BECAUSE IT CANNOT BE TAKEN ANYWHERE ELSE (Q-OPT-3). A
         global grad norm can only be read while gradients EXIST -- after backward, before the
         zero_grad on this line. OPT.counters used to claim it computed the norm; by the time
         counters runs the grads are zero, so a P4 author following that docstring would have
         reported 0.0 for the whole run with every check green. counters RENDERS the accumulated
         quantiles; this is where they are read. SCOPE: THE BASE GROUP ONLY. The encoder's grads at
         flush time belong to SIG's cadence and folding them into one number makes it
         uninterpretable.

         CLIPPING, WHEN opt.grad_clip > 0, HAPPENS ON THE SAME LINE AND IN THE SAME SCOPE: a global
         max-norm over the base group's parameters, applied AFTER the norm is recorded and BEFORE
         the step, so the reported p50/p99 are the norms the run actually produced rather than the
         clipped ones -- an instrument that measures its own remedy answers nothing. Clip-by-norm,
         never clip-by-value: it preserves gradient direction and rescales magnitude only.
         opt.grad_clip DEFAULTS TO 0.0 = OFF, so nothing in any recorded result moves; see Q-OPT-3
         in docs/04_CONTRACT.md for what measurement settles the default.

    RECEIVES: best_bpb <- EVAL, a Reading carrying (value, seed_count) or None; shift_at <- the
    composition root, the optimizer step of the last self-inflicted shift (epoch resample, retok,
    added area). Both are runtime arguments; the old code read `_shift_at` as a CLOSURE VARIABLE
    written by DATA's resample branch (:6518-6521), which is the L2 violation this replaces. Until
    shift_at is supplied, lr_shift_warm has nothing to fire on and its counter reads "armed but 0"
    -- which is a DIFFERENT statement from lr_shift_warm == 0, and the report must make both.

    LEVERS READ: accum, lr, lr_restart_damp, lr_sched (through lr_at), grad_clip, plus everything
                 lr_at reads
    WIRES READ: none
    DID IT FIRE: opt.step (BASE optimizer steps -- the encoder's are sig.train_stepped and live in
                 SIG), opt.step.not_due, opt.restart.detected, opt.restart.damped,
                 opt.restart.damp_refused_n1,
                 opt.lr.writes.base and opt.lr.writes.encoder (each must equal opt.step -- the
                 rate is written to both optimizers on every step; the old single counter said
                 "must equal opt.step, on BOTH optimizers" and could not distinguish a missing
                 encoder write from a missing step),
                 opt.encoder_steps_here (MUST BE 0 -- the regression counter for Q-OPT-6. A
                 nonzero value is the double-step returning, and without a counter it returns
                 silently because both call sites look correct in isolation),
                 opt.grad_norm.p50 / opt.grad_norm.p99 (base group, read before zero_grad;
                 rendered by counters),
                 opt.clip.applied / opt.clip.armed_no_clip (grad_clip > 0 and no step exceeded it
                 -- a DIFFERENT statement from grad_clip == 0, and the report must make both),
                 opt.shift.notifications (0 means nobody is supplying shift_at)
    """
    opt = opt.owned_by("OPT")
    raise NotImplementedError(
        "OPT.maybe_step: P4 (opt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section OPT.")


def counters(opt: Config, st):
    """The DID IT FIRE ledger, plus the one invariant that proves the accumulation defect is dead.

    ASSERTS AND REPORTS: `opt.backward // max(1, opt.accum) == opt.step`. The old tree could not
    make this statement because it counted the wrong thing; a run that violates it is running H29
    again under a new name. The report prints backward, step, accum, batch_windows and
    d_effective_batch_windows TOGETHER, so the batch size a run TRAINED at is a printed number
    rather than a configured one -- ACCUM appeared in no print anywhere in the old tree, while
    fetch_big.py names ACCUM=4 in its recommended heavy-run command and bench_gpu.sh ships ACCUM=2.

    Gates rendered with their own arithmetic (G4): lr_sched, lr_restarts (n_cycles > 1, NOT the
    flag), weight_decay > 0, lr_decay > 0 and n_cycles > 1, lr_shift_warm > 0 and a shift_at ever
    supplied. Two levers are reachable only by arithmetic and every result this project has
    recorded came from a single-cycle schedule, so neither lr_restart_damp nor lr_decay has ever
    fired in anger -- ISSUES.md:2029 files exactly this pair as the canonical "off by arithmetic,
    not armed and inert" case.

    RENDERS -- DOES NOT COMPUTE -- the observed global gradient norm (opt.grad_norm.p50/p99, base
    group). THE DISTINCTION IS THE WHOLE OF Q-OPT-3'S FIRST HALF: this paragraph used to say it
    reported the norm "per optimizer step", but maybe_step step 5 does the zero_grad, so a norm
    read from here is a norm over freshly zeroed gradients -- 0.0 for the entire run, with every
    check in this repository green. The quantiles are accumulated in maybe_step, between the
    gradient's last use and the zero_grad, and this call prints them. A counter that answers "0"
    while meaning "unreachable" is the exact distinction DID IT FIRE exists to preserve.

    Beside them it prints the CLIP gate: opt.grad_clip, and opt.clip.applied against
    opt.clip.armed_no_clip. There is NO gradient clipping anywhere in self_organize.py (verified by
    exhaustive grep: two matches, both prose about the forgetting measure F), so 0.0 is the setting
    every recorded number was taken under; see FOR THE OWNER Q-OPT-3 for the measurement that
    settles whether it should stay there.

    AND IT PRINTS THE HORIZON AGAINST THE RUN THAT ACTUALLY HAPPENED (Q-OPT-5). st.horizon.run_steps
    was resolved ONCE at build() from epoch 0's measured length times RUN.epochs; minting merges
    bytes into tokens, so len(Segmentation.ids) FALLS and every later epoch is SHORTER, which means
    the observed total comes in BELOW the projection and the cosine does not complete -- the run
    ends at a rate above lr x lr_min_frac. That is the same direction as the E8 p=0.760
    under-annealing the once-resolved horizon was introduced to kill: the machinery changed and the
    sign of the residual did not. THE MAGNITUDE IS UNMEASURED and this line is what measures it.
    The comparison is between two units.Steps values and is therefore a subtraction, not a
    UnitError: derive.opt_steps_from_windows(Windows(observed_windows), d_effective_batch_windows)
    against st.horizon.run_steps, where the observed side is RunClock.counters()'s window total,
    joined here by the composition root because neither package may read the other. The residual is
    filed with its sign NAMED (under-anneal), not left as two numbers in two report sections.
    Re-projecting the horizon mid-run is NOT the repair and is refused: it is `_project`/`_lr_total`
    /`_proj_lr` (:6335-6376), which produced E8 p=0.760 and E18 p=0.730 and the H17 resume defect,
    and it would require writing into a horizon resolved from a frozen Config.

    LEVERS READ: accum, batch_windows, lr_sched, lr_restarts, lr_decay, lr_shift_warm,
                 weight_decay, lr_restart_damp, grad_clip
    WIRES READ: d_effective_batch_windows
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    opt = opt.owned_by("OPT")
    _ = opt.d_effective_batch_windows        # WIRE READ HERE -- printed beside opt.backward
    raise NotImplementedError(
        "OPT.counters: P4 (opt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section OPT.")


def state_dict(opt: Config, st):
    """Both optimizers' state, plus everything the closed loop needs to survive a run boundary:
    opt_step, n_backward, lr_prev, restart_amp, cycle_best, cycle_index, the resolved horizon,
    param_group_shape, and the counters.

    param_group_shape WAS MISSING FROM THIS ENUMERATION UNTIL 2026-09-02 (Q-OPT-4) AND load_state
    REFUSES ON IT. A refusal armed against a value nothing writes is untrippable: the L50 guard --
    the one thing that stops AdamW moments being reattached positionally to different tensors after
    the population grew -- would have passed every resume by finding no shape to disagree with.
    It is written here and computed in build(), from the live groups.

    The old checkpoint saved opt_m and opt_e (:5372) and NOTHING ELSE from this package, so
    _rst_amp, _cyc_best, _nrst, _ndamp, _ncyc and _lr_prev all reset on every resume: a schedule
    that had damped itself twice came back at FULL AMPLITUDE, and the DID IT FIRE counters
    restarted at zero so a mechanism that fired 4,000 times read "armed but 0". A continual-learning
    system whose LR controller forgets across the run boundary is answering the wrong goal.

    LEVERS READ: none (everything comes off st)
    WIRES READ: none
    DID IT FIRE: opt.ckpt.saved
    """
    opt = opt.owned_by("OPT")
    raise NotImplementedError(
        "OPT.state_dict: P4 (opt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section OPT.")


def load_state(opt: Config, st, saved):
    """Restore, or refuse by name. Returns a LoadReport.

    REFUSES when saved.param_group_shape differs from the live one: the optimizer moment restore in
    the old tree did not verify that the module composition matched the checkpoint (ISSUES L50),
    and AdamW state is POSITIONAL over param groups, so a changed group order silently attaches one
    tensor's moments to another. REPORTS rather than refuses when the horizon changed (a legitimate
    resume at a different run length), and prints both horizons.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: opt.ckpt.loaded, opt.ckpt.refused (with the reason)
    """
    opt = opt.owned_by("OPT")
    raise NotImplementedError(
        "OPT.load_state: P4 (opt) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section OPT.")
