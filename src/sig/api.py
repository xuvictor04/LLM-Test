"""SIG -- the frozen public surface. Signatures only; P4 writes the bodies.

SIG owns the single function from a window of the stream to a unit vector of width SIG_D, and the
online contrastive objective that trains it. It serves GOAL B DIRECTLY: "do not overwrite what the
old material needs" is only actionable if the system can tell that new material IS different, and
every statement of that kind in this tree -- the domain boundary test, the fabric's routing
cosine, the centroid, the separability instruments -- is a distance in the space this package
produces. It serves GOAL A indirectly but not weakly: the signature is the router's only input, so
a collapsed encoder routes every window to the same experts.

ONE WIDTH, EVERYWHERE. The whole architecture of the rework turns on the fact that the old tree
resolved this width in two places -- self_organize.py:5675-5680 gave 614 bytes for training and
:3919 gave `max(1, SIG_WIN)` = ONE BYTE for every eval-path routing decision -- and nothing
failed, because every window still produced A signature. `encode` is the only way to obtain one on
any path, and it asserts the width it was handed on every call.

RECORD TYPES RETURNED (P4 defines them):
  SigState      encoder (or the frozen bigram table), width_units, positive_radius_units,
                alphabet_size, space, mode, d, counters, warmup_curve, rng, gates
                `gates` IS A NAME-KEYED MAP AND NOT A TUPLE, which is the one place this record
                departs from its siblings and the departure has a reason. memory/api.py::Store,
                capacity/api.py::Valve and tok/api.py::Vocabulary each carry a `gates` TUPLE built
                once by one constructor. SIG's gates are declared by FOUR entry points at four
                different moments -- encoder_parameters at assembly, warm_up before the loop,
                cadence_due and train_step once per window -- so a tuple appended to on the loop
                path would hold one entry per window and the report would read the last one as the
                run. Keyed by the gate's own name, a re-declaration REPLACES rather than
                accumulates, which is the only shape that survives a per-window declaration.
  StepOutcome   loss, stepped, why, n_prototype
  WarmupReport  verdict ("plateau" | "collapsing" | "budget"), curve, separation_peak,
                separation_final, steps, probes
"""
import dataclasses
import math

import torch
from torch import nn

from spine import units as U
from spine.gate import Gate
from spine.lever import Config


class _Encoder(nn.Module):
    """The learned signature encoder: an alphabet embedding, a mean over the window, a projection.

    SMALL ON PURPOSE. The signature is a ROUTING key, not a representation -- FAB keys on it, DOM
    partitions on it -- and a signature model with capacity to memorise the window would make the
    router's decision a function of content it should be abstracting over. What it must have is a
    FIXED input width, which is why width_units is frozen on SigState and every call reads it from
    there.
    """

    def __init__(self, alphabet_size, d, generator, *, device=None):
        super().__init__()
        self.emb = nn.Embedding(alphabet_size, d, device=device)
        self.proj = nn.Linear(d, d, device=device)
        with torch.no_grad():
            self.emb.weight.uniform_(-0.1, 0.1, generator=generator)
            self.proj.weight.uniform_(-0.1, 0.1, generator=generator)
            self.proj.bias.zero_()

    def forward(self, units):
        # MEAN OVER THE WINDOW, then project, then L2-normalise. The normalisation is here and not
        # at the call site because every consumer compares signatures by cosine, and a caller that
        # forgot to normalise would get a comparison weighted by window content length.
        h = self.emb(units).mean(dim=1)
        v = self.proj(h)
        return v / v.norm(dim=-1, keepdim=True).clamp_min(1e-8)


@dataclasses.dataclass
class SigState:
    """The encoder and THE ONE WINDOW WIDTH FOR THE RUN.

    NOT FROZEN, because the encoder trains and the counters advance -- but `width_units` is written
    once, here, and every later call in this package reads it FROM THIS OBJECT. There is no second
    place a width can come from and no recompute as the vocabulary grows. That is the whole of the
    C4/C5 repair: the old tree resolved the same quantity at two sites, 614 bytes in training and
    ONE BYTE in eval, so every eval-path routing decision in every report was made on a one-byte
    signature and nothing failed.
    """
    encoder: object
    width_units: int
    positive_radius_units: int
    alphabet_size: int
    space: str
    mode: str
    d: int
    counters: dict
    warmup_curve: list
    rng: object
    # DECLARED WITH A DEFAULT SO build() DOES NOT HAVE TO PASS IT, and keyed by name for the reason
    # in this module's RECORD TYPES block: four entry points declare gates here, two of them once
    # per window, and a tuple appended to on the loop path holds one entry per window.
    gates: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class WarmupReport:
    """What the pre-loop warm-up did, and WHICH OF THE THREE THINGS IT SAW -- never a binary.

    `verdict` is one of "plateau", "collapsing", "budget". The three exist because the old stop
    test could not tell the first from the second: `_sep <= _prev_sep * (1 + eps)` is true when the
    curve is FLAT and equally true when it is FALLING, so a single-corpus run whose separation went
    0.16 -> 0.05 was told it had converged, stopped early, found 0 boundaries and 1 domain, and
    printed every downstream line. "collapsing" is a RUN-LEVEL FAILURE and NO signature in this
    tree takes it as an argument: this record is what the composition root has to act on itself.

    `curve` IS THIS CALL'S CURVE, not the concatenation of every warm-up the run ever did. A resume
    that restored a previous run's curve and appended to it would make one curve out of two
    measurements, which is C4's shape one level up -- so warm_up REPLACES SigState.warmup_curve
    rather than extending it, and `separation_peak` / `separation_final` are taken over this call.
    """
    verdict: str
    curve: list
    separation_peak: object
    separation_final: object
    steps: int
    probes: int


def build(sig: Config, *, width_units, alphabet_size, device, generator):
    """Construct the signature encoder and FREEZE THE ONE WINDOW WIDTH FOR THE RUN.

    `width_units` is the answer of derive.signature_width_bytes(LM.ctx, measured bytes_per_token),
    computed ONCE by the composition root and handed here. It is NOT a lever and NOT a wire:
    assemble.NOT_WIRES rejects it because bytes_per_token is MEASURED on a corpus the tokenizer has
    not seen when build() freezes, and a Config that can still be written after startup is a Config
    the report cannot claim the run used. This function records it on SigState and every later call
    in this package reads it FROM THERE; there is no second place a width can come from and no
    recompute as the vocabulary grows. Under space="bytes" it is a byte count; under
    space="tokens" a token count.

    `alphabet_size` is the encoder embedding's row count: 256 under space="bytes", LM.vocab_slots
    under space="tokens". It is an ARGUMENT, not a read of LM. Under space="tokens" it is sized at
    the SLOT CEILING and not at the live vocab_size, because widening an embedding mid-run changes
    the encoder optimizer's moment shapes -- which is ISSUES P3-H24 from the other side.

    positive_radius_units = round(sig.positive_radius_windows * width_units), frozen here.

    RETURNS: SigState.

    LEVERS READ: mode, space, d, bigram_dim, positive_radius_windows
    WIRES READ: none
    DID IT FIRE: sig.width_units and sig.alphabet_size as one-shot facts on the ledger, plus
                 sig.encoder_built (mode='learned') or sig.bigram_built (mode='bigram'). Any later
                 call that observes a width other than sig.width_units RAISES.
    """
    sig = sig.owned_by("SIG")
    width = int(width_units)
    if width < 1:
        raise ValueError(
            f"SIG.build was handed width_units={width}. The signature window cannot be empty, and "
            f"this is the quantity C4/C5 are about: the old eval path resolved it to ONE BYTE from "
            f"max(1, SIG_WIN) while training used 614, so every eval-path routing decision in "
            f"every report was made on a one-byte signature and nothing failed.")

    # ON THE TARGET DEVICE: torch's in-place random ops require the generator and the tensor to
    # share one, so a cpu Generator filling a table allocated on cuda raises on every GPU run.
    gen = torch.Generator(device=device)
    gen.manual_seed(generator.randint(0, 2 ** 31 - 1))
    mode = str(sig.mode)
    if mode == "bigram" and width < 2:
        # A REFUSAL, NOT THE ZERO VECTOR THIS USED TO PRODUCE. encode()'s bigram arm hashes
        # consecutive PAIRS of units (`units[:, :-1] * 31 + units[:, 1:]`); at width_units=1 that
        # slice is empty, index_add_ adds nothing, and `v / v.norm(...).clamp_min(1e-8)` returns an
        # exact, well-formed all-zero unit vector on every call -- reproduced: SIG_MODE=bigram,
        # SIG_WIDTH_UNITS=1 (reachable at LM_CTX=1) gave every window an identical zero signature,
        # so FAB's routing cosine was identical for every expert and DOM's boundary test could never
        # fire, with nothing anywhere raising. That is exactly the C4/C5 failure this package's own
        # docstring says encode() may never produce ("a caller that cannot supply width_units units
        # gets an EXCEPTION, never a narrower window and never a zero vector"). The learned arm has
        # no such hole -- its embedding mean is well-defined at width 1 -- so this refusal is
        # bigram-only and fires at build time, before any window is ever encoded.
        raise ValueError(
            f"SIG_MODE=bigram needs at least two units to form a bigram; SIG_WIDTH_UNITS={width} "
            f"cannot produce one. A bigram encoder run at width_units=1 does not fail loudly -- it "
            f"returns a well-formed all-zero signature for every window, which collapses FAB's "
            f"routing and DOM's boundary test with no error anywhere. Raise SIG_WIDTH_UNITS to at "
            f"least 2, or use SIG_MODE=learned, which has no width floor.")
    if mode == "learned":
        encoder = _Encoder(int(alphabet_size), int(sig.d), gen, device=device)
    elif mode == "bigram":
        # THE FROZEN TABLE ARM. A random projection of bigram counts -- no parameters that train,
        # which is what makes it the control arm the learned encoder is read against.
        table = torch.empty(int(sig.bigram_dim), int(sig.d), device=device)
        with torch.no_grad():
            table.uniform_(-0.1, 0.1, generator=gen)
        encoder = table
    else:
        raise ValueError(f"SIG_MODE={mode!r} has no constructor here. choices= admits only the "
                         f"spellings this function builds.")

    return SigState(
        encoder=encoder,
        width_units=width,
        positive_radius_units=round(float(sig.positive_radius_windows) * width),
        alphabet_size=int(alphabet_size),
        space=str(sig.space), mode=mode, d=int(sig.d),
        counters={"sig.width_units": width, "sig.alphabet_size": int(alphabet_size),
                  "sig.encoder_built": 1 if mode == "learned" else 0,
                  "sig.bigram_built": 1 if mode == "bigram" else 0,
                  # FOUR SEPARATE SURFACES, SEEDED HERE SO A REPORT READ BEFORE THE FIRST encode()
                  # CALL SEES ZEROS AND NOT A MISSING KEY. encode_calls counts INVOCATIONS,
                  # encode_windows counts the units-of-work inside them (they collapsed into one
                  # number -- the window count stored under the "calls" name -- until this repair;
                  # a report reading that row printed N windows-per-call as N calls). width_seen is
                  # the last-observed width for the report to eyeball against width_units, and
                  # width_mismatch is the C4 alarm: nonzero means encode() detected a width other
                  # than st.width_units and RAISED rather than reshaping around it.
                  "sig.encode_calls": 0, "sig.encode_windows": 0,
                  "sig.encode_width_seen": 0, "sig.encode_width_mismatch": 0,
                  "sig.train_steps": 0},
        warmup_curve=[], rng=generator)


def encode(sig: Config, st, windows):
    """Signatures for N windows in one call. (N, width_units) ints -> (N, sig.d) unit vectors.

    THE ONLY WAY TO OBTAIN A SIGNATURE, on every path -- training, eval, generation, checkpoint
    replay, instruments. There is no eval variant, no gist placeholder and no fallback: a caller
    that cannot supply width_units units gets an EXCEPTION, never a narrower window and never a
    zero vector. This is the whole of the C4/C5 repair.

    Runs under no_grad and never touches the optimizer, so an instrument calling it cannot move the
    encoder (the G7 digest holds across it).

    LEVERS READ: none (nothing off `sig` directly -- everything comes off SigState: st.mode,
                 st.d, st.width_units, st.encoder, which build() froze from mode, d and bigram_dim
                 once)
    WIRES READ: none
    DID IT FIRE: sig.encode_calls, sig.encode_windows, and sig.encode_width_seen asserted equal to
                 st.width_units on EVERY call -- a nonzero sig.encode_width_mismatch is the C4
                 alarm and is a HARD FAILURE, not a warning
    """
    sig = sig.owned_by("SIG")
    units = windows if torch.is_tensor(windows) else torch.as_tensor(windows, dtype=torch.long)
    if units.dim() != 2 or int(units.shape[1]) != st.width_units:
        # AN EXCEPTION, NEVER A NARROWER WINDOW AND NEVER A ZERO VECTOR. This is the whole of the
        # C4/C5 repair: the eval path used to resolve its own width and got one byte, and because
        # a one-byte signature is a perfectly well-formed vector nothing anywhere failed. The
        # mismatch is counted BEFORE the raise so a process that dies here still leaves the ledger
        # holding a nonzero sig.encode_width_mismatch -- the C4 alarm -- for the report to find.
        st.counters["sig.encode_width_mismatch"] += 1
        got = tuple(units.shape)
        raise ValueError(
            f"SIG.encode was handed windows of shape {got} against the width frozen at build, "
            f"{st.width_units} unit(s) of {st.space!r}. There is no eval variant, no gist "
            f"placeholder and no fallback -- a caller that cannot supply the frozen width gets "
            f"this, because the alternative measured a whole project's routing on one byte.")

    # sig.encode_calls counts INVOCATIONS and sig.encode_windows counts the units of work inside
    # them; these used to be the same counter (encode_calls incremented by the window count), so a
    # report printing "sig.encode_calls" after one call on a batch of 512 windows read 512, and the
    # two quantities the contract wants separated -- how often the encoder was invoked vs how many
    # windows were characterised -- collapsed into one number that was neither's label.
    st.counters["sig.encode_calls"] += 1
    st.counters["sig.encode_windows"] += int(units.shape[0])
    st.counters["sig.encode_width_seen"] = int(units.shape[1])

    # RUNS UNDER no_grad, AND THIS IS THE WHOLE OF THE REPAIR. Without it, this arm built an
    # autograd graph through _Encoder.emb/.proj -- both live in OPT's "encoder" param group
    # (compose.py's opt_api.build param_groups={"encoder": sig_api.encoder_parameters(...)}) -- so
    # ANY caller that computed a signature for routing and later called .backward() on the LM/FAB
    # loss accumulated gradient into the signature encoder, and the next optimizer step applied it:
    # the router's only input moved under a loss that is not its own contrastive objective, and
    # sig.train_steps counted none of it. Reproduced before this fix: encode(...).sum().backward()
    # left a non-None grad on st.encoder.emb.weight. Training already has its own entry points
    # (train_step, warm_up); no_grad here costs this function nothing it was using.
    with torch.no_grad():
        if st.mode == "bigram":
            # Bigram counts hashed into the frozen table, then normalised the same way the encoder
            # normalises, so the two arms produce comparable vectors.
            idx = ((units[:, :-1] * 31 + units[:, 1:]) % st.encoder.shape[0]).long()
            v = torch.zeros(units.shape[0], st.d, device=st.encoder.device)
            v.index_add_(0, torch.arange(units.shape[0], device=v.device).repeat_interleave(idx.shape[1]),
                         st.encoder[idx.reshape(-1)])
            return v / v.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        return st.encoder(units.to(next(st.encoder.parameters()).device))


def cadence_due(sig: Config, st, *, step_windows, windows_since_boundary):
    """The shift gate: is a contrastive step due at this window?

    Dense (train_every) while the stream is within dense_window of the last detected boundary,
    throttled (train_every_idle) once it has been stable. All three thresholds are Windows and are
    compared against a Windows clock; windows_since_boundary is supplied by the caller from DOM's
    last boundary -- SIG DOES NOT REACH FOR IT. sig/levers.py::SIGLevers calls it "d_last_boundary"; it is
    RUNTIME STATE and cannot be a build-time wire, which is a correction to that comment and not a
    disagreement with L2: the value still arrives from outside and the reader still never names the
    foreign lever.

    THE IDLE CADENCE IS THE WIRE, NOT THE LEVER. d_idle_cadence is `max(train_every*6,
    train_every_idle)`, declared in spine/assemble.py, and the throttled arm reads THAT. The relation
    was recorded as "relocated" out of the old computed default
    `_i("ENC_EVERY_IDLE", max(ENC_EVERY * 6, 12))` and into a coupling -- and the coupling was never
    declared, so for six commits train_every_idle sat at a literal 12 with no connection to
    train_every at all (ISSUES P1-H53). At the shipped train_every=1 the two agree exactly, which is
    what let it survive. Reading the wire is what makes "the idle cadence follows the dense one"
    true rather than a sentence in a comment.

    LEVERS READ: mode, train_every, train_every_idle, dense_window
    WIRES READ: d_idle_cadence
    DID IT FIRE: sig.cadence_dense, sig.cadence_idle, sig.cadence_checks. sig.cadence_idle == 0 for
                 a whole run means the gate never left the dense arm; sig.cadence_dense == 0 after
                 step dense_window means no boundary was ever detected and the gate is stuck open
                 on idle -- two different findings the report must be able to separate. BOTH FIRE
                 COUNTERS EXIST FROM THE FIRST CHECK ON EVERY ARM, which is what makes those two
                 readings takeable: they are seeded before the due/not-due branch rather than
                 inside one side of it, because at SIG_TRAIN_EVERY=1 -- the shipped default -- the
                 dense period is 1, every window is due, and a seed on the not-due side never ran
                 at all. A missing key and a zero say different things to a reader and only one of
                 them is a measurement.
    """
    sig = sig.owned_by("SIG")
    idle_period = int(sig.d_idle_cadence)   # WIRE READ HERE -- the throttled arm's threshold
    mode = str(sig.mode)
    dense_period = int(sig.train_every)
    lever_idle = int(sig.train_every_idle)
    dense_for = U.Windows(int(sig.dense_window))
    # BOTH INCOMING CLOCKS ARE PUT THROUGH units.Windows, AND THAT IS THE ONLY REASON THIS FUNCTION
    # CAN BE TRUSTED. Config hands back a bare int for all 35 clock-unit levers, so a kind is
    # metadata at the read site (ISSUES P1-H51) -- but the two values that arrive as ARGUMENTS come
    # from the root, and spine/units.py::Clock refuses to build a Windows out of a Steps. That turns
    # "the caller handed us the optimizer's step counter" from a gate that is always open or always
    # shut into a UnitError at the first window. units.py records four subsystems whose modulo
    # cadences never coincided with the clock they were compared against; this is the one that
    # decides whether the encoder ever notices a real distribution shift.
    step = U.Windows(step_windows)
    since = U.Windows(windows_since_boundary)

    checks = int(st.counters.get("sig.cadence_checks", 0)) + 1
    st.counters["sig.cadence_checks"] = checks
    dense_fires = int(st.counters.get("sig.cadence_dense", 0))
    idle_fires = int(st.counters.get("sig.cadence_idle", 0))
    # BOTH KEYS EXIST FROM THE FIRST CHECK, AND SEEDING THEM ON ONE BRANCH SEEDED NEITHER AT THE
    # SHIPPED DEFAULT. These two lines stood inside the ELSE of `if due:` -- so a run that never
    # entered an arm saw a zero and not a missing key, EXCEPT at SIG_TRAIN_EVERY=1, where the dense
    # period is 1, every window is due, the else never runs and sig.cadence_idle was ABSENT for the
    # whole run. The reading this function's own DID IT FIRE block names -- "sig.cadence_idle == 0
    # for a whole run means the gate never left the dense arm" -- was then a KeyError rather than
    # the 0 it describes, and only on the one configuration the tree ships. Seeded BEFORE the
    # branch, both keys exist from the first check on every arm, learned or bigram, due or not.
    st.counters.setdefault("sig.cadence_dense", dense_fires)
    st.counters.setdefault("sig.cadence_idle", idle_fires)

    # THE ARM SELECTION IS A Windows-AGAINST-Windows COMPARISON, which is what makes the three
    # levers in this function's block one family. `since < dense_for` raises UnitError against any
    # other kind rather than answering.
    # THE PRINTED PAIR ON BOTH GATES IS (this arm's PERIOD vs SIG_DENSE_WINDOW) AND NOT THE LAST
    # CALL'S windows_since_boundary. This function runs once per window, so a gate rebuilt from the
    # latest argument would print whatever the last window happened to be and read as the run; the
    # two configured numbers do not move, and the fire counts live in the reason beside them.
    in_dense = since < dense_for
    period = dense_period if in_dense else idle_period

    # THE INERT ARM IS ANSWERED BEFORE THE CADENCE IS JUDGED, AND THE ORDER IS THE WHOLE POINT.
    # The refusal below and the reason sentence here disagreed: this gate declares
    # SIG_TRAIN_EVERY, SIG_TRAIN_EVERY_IDLE and SIG_DENSE_WINDOW INERT under SIG_MODE=bigram --
    # which is true, `due` short-circuits on the mode and the modulo is never evaluated -- while
    # the `period < 1` refusal stood ABOVE it and took the run down on the first window of a
    # SIG_MODE=bigram / SIG_TRAIN_EVERY=0 run, naming a modulo-by-zero that cannot happen on that
    # arm. A lever the report calls inert cannot also be the lever that stops the run. The refusal
    # keeps its full force on the arm where the division is real, which is the one below.
    if mode != "learned":
        why = (f"SIG_MODE={mode!r}: the frozen hashed-bigram table has no parameters, so there is "
               f"no contrastive step for this gate to be due for. SIG_TRAIN_EVERY={dense_period}, "
               f"SIG_TRAIN_EVERY_IDLE={lever_idle} and SIG_DENSE_WINDOW={int(dense_for)} are inert "
               f"on this arm; a count of 0 fires here is not a cadence that declined to fire. That "
               f"is why an incoherent cadence is not refused here either: this arm never divides "
               f"by it.")
        st.gates["sig.cadence_dense"] = Gate("sig.cadence_dense", False, dense_period,
                                             int(dense_for), reachable=False, reason=why)
        st.gates["sig.cadence_idle"] = Gate("sig.cadence_idle", False, idle_period,
                                            int(dense_for), reachable=False, reason=why)
        return False

    if period < 1:
        raise ValueError(
            f"the {'dense' if in_dense else 'idle'} arm of SIG's shift gate has a period of "
            f"{period} window(s), and a cadence of zero or less is a modulo by zero, not a gate "
            f"that fires every window. The dense arm is SIG_TRAIN_EVERY={dense_period}; the "
            f"throttled arm is SIG.d_idle_cadence = max(SIG_TRAIN_EVERY x 6, "
            f"SIG_TRAIN_EVERY_IDLE={lever_idle}) = {idle_period}, declared in spine/assemble.py "
            f"and NOT the lever, which is the coupling that sat unlanded for six commits.")

    # MODE IS "learned" FROM HERE DOWN -- the other arm returned above -- so the modulo IS
    # evaluated on every call and the refusal above is the guard that makes it safe.
    due = int(step) % period == 0
    if due:
        if in_dense:
            dense_fires += 1
            st.counters["sig.cadence_dense"] = dense_fires
        else:
            idle_fires += 1
            st.counters["sig.cadence_idle"] = idle_fires

    st.gates["sig.cadence_dense"] = (
        Gate("sig.cadence_dense", dense_fires > 0, dense_period, int(dense_for),
             reason=f"dense arm: windows_since_boundary < SIG_DENSE_WINDOW, firing every "
                    f"SIG_TRAIN_EVERY={dense_period} window(s); {dense_fires} fire(s) in "
                    f"{checks} check(s)")
        if int(dense_for) >= 1 else
        Gate("sig.cadence_dense", False, dense_period, int(dense_for), reachable=False,
             reason=f"SIG_DENSE_WINDOW={int(dense_for)}: the dense arm is entered while "
                    f"windows_since_boundary is BELOW it, and no window count is below "
                    f"{int(dense_for)}, so the gate is stuck open on the throttled arm for the "
                    f"whole run no matter how many boundaries DOM reports. SIG_TRAIN_EVERY="
                    f"{dense_period} cannot be reached."))
    st.gates["sig.cadence_idle"] = Gate(
        "sig.cadence_idle", idle_fires > 0, idle_period, int(dense_for),
        reason=f"throttled arm: windows_since_boundary >= SIG_DENSE_WINDOW, firing every "
               f"SIG.d_idle_cadence = max(SIG_TRAIN_EVERY x 6, SIG_TRAIN_EVERY_IDLE={lever_idle}) "
               f"= {idle_period} window(s) -- THE WIRE AND NOT THE LEVER, which is what makes 'the "
               f"idle cadence follows the dense one' true rather than a sentence in a comment; "
               f"{idle_fires} fire(s) in {checks} check(s)")
    return due


def train_step(sig: Config, st, *, stream, seen_units, opt, reservoir=None):
    """One InfoNCE step. Returns StepOutcome(loss, stepped, why, n_prototype).

    `stream` is the unit stream this package's alphabet is over (bytes under space="bytes", token
    ids under space="tokens") as a device tensor; `seen_units` bounds the anchor draw to material
    the loop has actually reached. `opt` is the ENCODER OPTIMIZER, BUILT BY OPT AND HANDED IN --
    `OptState.encoder`, the AdamW over param_groups["encoder"], which is a nameable value as of
    2026-09-02 (Q-OPT-7); until then the root had no expression for one of the two and handed over
    the whole OptState, an object through which this package could have stepped the language model.
    SIG never names a learning rate: OPT.maybe_step writes `lr` into this optimizer's param groups
    on every optimizer step and does NOT step it (Q-OPT-6 (a)) -- THIS FUNCTION IS THE ONLY PLACE
    THE ENCODER IS STEPPED IN THE LOOP, which is what makes the floor gate below and this package's
    three cadence levers load-bearing rather than inert. `reservoir`, when given, is a list of
    (window, window) pairs drawn from ONE domain's reservoir by DOM.

    NOTHING GIVES IT, AND THAT IS THE ANSWER RATHER THAN AN OVERSIGHT (Q-SIG-1, RESOLVED
    2026-09-02, option (c) -- which is what this signature already specified). No DOM entry point
    returns reservoir windows and the LOOP_ORDER row for this call supplies stream, seen_units and
    opt only, so `reservoir` is None on every call the root makes and the prototype arm cannot run.
    WITH prototype_frac > 0 AND reservoir None, sig.prototype_pairs MUST REPORT
    `unreachable (no DOM supplier)` AND NEVER "armed but 0" -- the two are different states and this
    is the purest armed-but-inert shape in the tree, because prototype_frac appears in this
    function's own LEVERS READ list and therefore passes K4 as consumed while being structurally
    unreachable (tests/test_contract.py says it outright: "LEVERS READ: is prose that passes a
    parser"). The lever is NOT dropped: sig/levers.py's group header diagnoses that the positive
    radius is shorter than a splice segment, so the encoder is explicitly taught that two distant
    windows of the same corpus differ and more encoder training makes domain identity WORSE, and
    prototype_frac is the only declared remedy for it. `reservoir=None` being a defaulted keyword is
    what lets a supplier land later with no change to this signature at all.

    ANCHORS AND POSITIVES ARE DRAWN AT st.width_units, NOT AT THE LOOP WINDOW. The old tree drew
    them at WIN (:3323, :3326 -- `torch.arange(WIN)`) while applying the encoder to `_sigw` bytes
    (:6646), so the encoder was trained on 128-byte windows and used on 614-byte ones. No crash --
    a GRU accepts any length -- and no report line. This is C4's other half, on the side nobody
    looked at: the encoder's learned invariance was never measured on the material it is used on.

    The positive offset is drawn in [width_units//2, positive_radius_units], and the radius MAY GO
    BELOW ONE WINDOW: the old `max(2*WIN, ENC_POS_MAX)` clamp (:3311) could only WIDEN it, while
    the file's own diagnosis says narrowing is the fix (ISSUES P1-L15).

    The step is SKIPPED (loss returned, opt untouched) when loss <= ln(1+(B-1)/floor_kinds).

    LEVERS READ: mode, space, contrastive_batch, temp, positive_radius_windows (through
                 st.positive_radius_units), prototype_frac, floor_kinds, var_weight, cov_weight, d
    WIRES READ: none
    DID IT FIRE: sig.train_steps (entered), sig.train_stepped (opt.step actually ran),
                 sig.floor_skips, sig.prototype_pairs (zero here with prototype_frac > 0 means DOM
                 supplied no reservoir -- unreachable, and the gate says so), sig.varcov_applied.
                 sig.train_stepped == 0 with sig.train_steps > 0 is the "encoder is at its floor"
                 state and must be REPORTED AS SUCH, not as "trained".
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.train_step: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


# ==================================================================================================
# THE PRE-LOOP TRAINING PATH'S PRIVATE PARTS
#
# WHY THESE ARE HELPERS AND NOT INLINE IN warm_up. warm_up's own LEVERS READ block names seven
# levers -- mode, warmup, warmup_min_frac, warmup_plateau_eps, warmup_probe_every,
# contrastive_batch, d -- and NOT temp, var_weight, cov_weight or positive_radius_windows. Those
# four are named by train_step's block and by counters'. There is exactly one contrastive objective
# in this package and both steppers use it, so the only reading under which both blocks are true is
# that the objective is a SHARED function whose lever reads are declared once, on train_step. That
# is what these are. train_step is still a stub and its body, when it is written, is this same
# objective plus the prototype arm, the InfoNCE floor gate and its own five counters -- the two
# things warm_up deliberately does not have (its budget is spent in optimizer steps, so every
# iteration is one opt.step; the floor gate belongs to the loop, where sig.floor_skips is declared).
# ==================================================================================================


def _unit_tensor(stream):
    """The unit stream as ONE flat CPU tensor, whatever spelling the root handed over.

    THREE SPELLINGS ARRIVE HERE AND ALL THREE ARE THE ROOT'S. spine/compose.py::_signature_stream
    returns `Stream.bytes` under space="bytes" -- a python `bytes` -- and `Segmentation.ids` under
    space="tokens", which is a python `list`. sig/api.py::train_step's own paragraph says the stream
    arrives "as a device tensor", and today nothing hands one over; accepting all three is what
    keeps that disagreement from being a TypeError at the first warm-up of every run.

    KEPT AS uint8 ON THE BYTE ARM AND NEVER WIDENED WHOLE. A `.long()` over the epoch's bytes is an
    eightfold copy of the entire stream; only the drawn windows are widened, in _windows_at.
    `bytearray(...)` is one pass and buys a WRITABLE buffer, which is what stops torch.frombuffer
    warning on every call about a non-writable one.
    """
    if torch.is_tensor(stream):
        return stream.reshape(-1)
    if isinstance(stream, (bytes, bytearray, memoryview)):
        return torch.frombuffer(bytearray(stream), dtype=torch.uint8)
    return torch.as_tensor(list(stream), dtype=torch.long)


def _windows_at(base, starts, width):
    """(N, width) units, one row per start. THE WIDTH IS AN ARGUMENT AND ITS ONLY SOURCE IS
    SigState.width_units -- there is no second place in this file that decides how wide a window is,
    which is the whole of the C4/C5 repair restated on the training path. Returns long, because
    nn.Embedding takes indices and the byte arm's base tensor is uint8.
    """
    off = torch.arange(int(width), dtype=torch.long)
    return base[starts.reshape(-1, 1) + off.reshape(1, -1)].long()


def _encode_for_training(st, units):
    """The encoder's forward WITH the autograd graph -- the one thing encode() may not do.

    encode() runs under no_grad ON PURPOSE: it is the routing path, and an instrument that computed
    a signature and later called .backward() on a loss that is not this package's objective used to
    accumulate gradient into st.encoder.emb/.proj, which sit in OPT's "encoder" param group. The
    two entry points that are ENTITLED to move the encoder -- warm_up and train_step -- need the
    graph, and this is where they get it. Nothing else in the tree may call it.
    """
    device = next(st.encoder.parameters()).device
    return st.encoder(units.to(device=device, dtype=torch.long))


def _draw_pairs(st, base, seen_units, n, gen):
    """`n` (anchor, positive) window pairs, BOTH DRAWN AT st.width_units.

    C4'S OTHER HALF, ON THE SIDE NOBODY LOOKED AT. The old tree drew anchors and positives with
    `torch.arange(WIN)` -- 128 bytes -- and then applied the encoder to `_sigw` = 614 bytes on the
    live path. Nothing crashed, because a GRU accepts any length, and no report line said so: the
    encoder's learned invariance was never measured on the material it is used on. Here both the
    draw and every later encode take their width from ONE field.

    THE OFFSET RANGE IS [width_units // 2, positive_radius_units] AND IS NEVER WIDENED TO MEET A
    FLOOR. The old `_pmax = max(2*WIN, ENC_POS_MAX)` clamp could only push the radius UP, while the
    file's own diagnosis three lines above it said narrowing was the fix (ISSUES P1-L15) -- so
    ENC_POS_MAX=64 at WIN=128 ran at 256 with no message. A radius that lands below the lower bound
    is refused BY NAME here instead: an empty interval is a configuration the operator has to see,
    and silently restoring the floor is the defect, not the repair.
    """
    width = int(st.width_units)
    lo = width // 2
    hi = int(st.positive_radius_units)
    if hi < lo:
        raise ValueError(
            f"SIG_POSITIVE_RADIUS_WINDOWS puts the InfoNCE positive radius at "
            f"{hi} unit(s) of {st.space!r}, below the lower bound of the offset draw, "
            f"{width} // 2 = {lo}. That is an EMPTY interval, and the one thing this may not do is "
            f"quietly widen it back to {lo}: the old tree's max(2*WIN, ENC_POS_MAX) clamp could "
            f"only ever widen, while the comment three lines above it told the operator that "
            f"NARROWING the radius was the fix for the defect it described. Raise "
            f"SIG_POSITIVE_RADIUS_WINDOWS above {lo / float(width):.3f}, or narrow the signature "
            f"window instead.")
    span = int(seen_units) - width - hi
    if span < 1:
        raise ValueError(
            f"SIG.warm_up was given {int(seen_units)} unit(s) of {st.space!r} to draw anchors from, "
            f"and one anchor/positive pair needs width_units + positive_radius_units + width_units "
            f"= {width} + {hi} + {width}. There is no narrower draw and no wrap-around: a pair the "
            f"stream cannot supply is an exception, for the same reason a window narrower than "
            f"width_units is one.")
    starts = torch.randint(0, span, (int(n),), generator=gen, dtype=torch.long)
    offsets = torch.randint(lo, hi + 1, (int(n),), generator=gen, dtype=torch.long)
    return _windows_at(base, starts, width), _windows_at(base, starts + offsets, width)


def _var_cov(z, var_weight, cov_weight, d):
    """The VICReg anti-collapse pair, RESCALED BY sqrt(d) so the variance hinge is reachable at all.

    THE RESCALE IS THE POINT. These outputs are L2-normalised, so a coordinate's standard deviation
    is on the order of 1/sqrt(d) and a hinge written against 1.0 is satisfied by a collapsed
    encoder as readily as by a healthy one -- which is why the old tree scaled by sqrt(SIG_D)
    before the hinge. sig/levers.py::SIGLevers says this rescale "BECOMES A NAMED derive FUNCTION
    rather than an inline expression, so the weight and its scaling cannot drift apart". There is
    no such function in spine/derive.py today and adding one is a spine edit this package may not
    make, so the expression is written ONCE, here, and that sentence is owed work rather than done
    work. It is recorded at the site rather than in a report nobody greps.

    Both terms are weighted independently and neither is a duplicate off-switch for the other:
    variance stops the representation shrinking to a point, covariance stops it collapsing onto a
    lower-dimensional subspace, which the effective-dimension reading exists to detect and which
    var_weight alone cannot prevent.
    """
    n = int(z.shape[0])
    centred = z - z.mean(dim=0, keepdim=True)
    scale = math.sqrt(float(d))
    term = z.new_zeros(())
    if var_weight > 0.0:
        std = (centred.var(dim=0, unbiased=False) + 1e-8).sqrt() * scale
        term = term + var_weight * torch.clamp(1.0 - std, min=0.0).mean()
    if cov_weight > 0.0 and n > 1:
        cov = (centred.t() @ centred) * (scale * scale) / float(n - 1)
        off_diagonal = cov - torch.diag(torch.diagonal(cov))
        term = term + cov_weight * off_diagonal.pow(2).sum() / float(d)
    return term


def _contrastive_loss(sig: Config, st, za, zp, *, d):
    """One InfoNCE loss over the batch's own negatives, plus the anti-collapse pair.

    THE LEVER READS THIS FUNCTION MAKES ARE DECLARED ON train_step, NOT ON warm_up, and that is
    deliberate rather than an omission -- see the block comment above _unit_tensor. `d` arrives as
    an argument because it is the one geometry number the CALLER is required to name (warm_up's
    LEVERS READ block carries it), and because _var_cov's rescale must be the same sqrt(d) the
    signature space actually has.

    B IS PART OF THE DIAGNOSTIC AND NOT A THROUGHPUT SETTING: the collapse reference is ln(B), and
    a single-corpus run plateauing at 3.83 against ln(48) = 3.871 is how encoder collapse was
    diagnosed at all. Change contrastive_batch and that reference number moves with it.
    """
    sig = sig.owned_by("SIG")
    temp = float(sig.temp)
    if temp <= 0.0:
        raise ValueError(
            f"SIG_TEMP={temp} is the DIVISOR on the cosine logits. At zero it is a division by "
            f"zero and below zero it INVERTS the objective -- the nearest positive becomes the "
            f"least likely -- which trains the encoder to separate a window from its own "
            f"neighbourhood while every loss number stays finite and printable.")
    n = int(za.shape[0])
    logits = (za @ zp.t()) / temp
    target = torch.arange(n, device=logits.device)
    loss = nn.functional.cross_entropy(logits, target)
    var_weight, cov_weight = float(sig.var_weight), float(sig.cov_weight)
    if var_weight > 0.0 or cov_weight > 0.0:
        loss = loss + _var_cov(torch.cat((za, zp), dim=0), var_weight, cov_weight, d)
    return loss


def _separation(sig: Config, st, base, seen_units, n, gen, *, d):
    """The warm-up's ONE instrument: mean pairwise cosine DISTANCE over `n` random encodings.

    IT GOES THROUGH encode(), WHICH IS THE ONLY WAY TO OBTAIN A SIGNATURE ON ANY PATH. An
    instrument with its own encode is exactly the C4/C5 shape -- the old eval path had one, resolved
    its own width, got ONE BYTE, and every routing number in every report was produced by it. Going
    through encode() also means this probe is counted in sig.encode_calls and sig.encode_windows and
    is asserted against st.width_units like everything else, and encode()'s no_grad is what makes
    the probe a measurement rather than a training step.
    """
    sig = sig.owned_by("SIG")
    width = int(st.width_units)
    span = int(seen_units) - width
    if span < 1:
        raise ValueError(
            f"the separation probe needs at least one full window of {width} unit(s) of "
            f"{st.space!r} and was given {int(seen_units)}.")
    starts = torch.randint(0, span, (int(n),), generator=gen, dtype=torch.long)
    z = encode(sig, st, _windows_at(base, starts, width))
    if int(z.shape[1]) != int(d):
        raise ValueError(
            f"the separation probe encoded into {int(z.shape[1])} dimensions against SIG_D={int(d)}. "
            f"Separation is a distance IN THE SIGNATURE SPACE, so a probe measuring it in a "
            f"different width is measuring a different space -- the same class of defect as a "
            f"signature taken at a different width.")
    rows = int(z.shape[0])
    sim = z @ z.t()
    iu = torch.triu_indices(rows, rows, offset=1, device=sim.device)
    return float((1.0 - sim[iu[0], iu[1]]).mean())


def _stop_verdict(curve, eps):
    """"collapsing" | "plateau" | None, from the probe curve. THE ORDER OF THE TWO TESTS IS THE FIX.

    The old test was `_sep <= _prev_sep * (1 + eps)`, which is true when separation is FLAT and
    EQUALLY TRUE WHEN IT IS COLLAPSING. On a single-corpus stream running 0.16 -> 0.05 -- a 69%
    collapse -- it reported a converged plateau and stopped; SHIFT_DIST then never fired, the run
    found 0 boundaries and 1 domain, and every downstream report line still printed. No value of
    warmup_plateau_eps fixes that: a smaller eps just stops later.

    So collapse is tested FIRST and the flatness test is TWO-SIDED (|change| <= eps, not
    change <= +eps) and is additionally required to sit at 0.85 of the curve's own peak. A falling
    curve can therefore only ever leave here as "collapsing", never as "plateau".

    THE TWO ARMS NEED DIFFERENT AMOUNTS OF CURVE AND THIS FUNCTION IS WHERE THAT IS DECIDED. The
    ABSOLUTE collapse arm (`sep < 0.15`) is a statement about ONE probe and needs no history; the
    relative arm and the whole flatness test compare a probe against what came before it. Holding
    the whole function behind "at least two probes" is what put the run-level failure verdict out
    of reach at the shipped SIG_WARMUP=800 / SIG_WARMUP_PROBE_EVERY=500, which admit exactly one
    probe: a fully collapsed encoder measured a separation of -0.000000 against this 0.15 and
    warm_up still returned "budget" -- the historical failure this module was written to remove,
    restored one level up. So a single-probe curve is accepted here, the collapse arms run on it,
    and only the flatness test is skipped for want of a predecessor. On a one-point curve
    `sep < 0.7 * peak` is `sep < 0.7 * sep`, which is False for any non-negative separation and
    True only where the absolute arm already fires, so the relative arm neither gains nor loses a
    verdict by being evaluated there.
    """
    sep, peak = curve[-1], max(curve)
    if sep < 0.7 * peak or sep < 0.15:
        return "collapsing"
    if len(curve) < 2:
        return None                      # the flatness test has no predecessor to compare against
    prev = curve[-2]
    if abs(sep - prev) <= eps * abs(prev) and sep >= 0.85 * peak:
        return "plateau"
    return None


def warm_up(sig: Config, st, *, stream, seen_units, opt):
    """Train the encoder unsupervised before the main loop, AND STOP HONESTLY.

    Runs at most sig.warmup optimizer STEPS (not windows -- this is the pre-loop budget and each
    iteration is one opt.step). Every warmup_probe_every steps it takes a separation probe (mean
    pairwise cosine distance of 2*contrastive_batch random encodings, ENCODED AT st.width_units)
    into a curve. After warmup_min_frac * warmup steps the stop may fire, and it returns ONE OF
    THREE VERDICTS, never a binary:
        "plateau"    separation flat within warmup_plateau_eps and >= 0.85 of its own peak
        "collapsing" separation below 0.7 of its peak, or below 0.15 absolute
        "budget"     no stop fired -- INCLUDING THE ARMS WHERE NO STEP RAN AT ALL, and the
                     record cannot tell those apart, so read it beside the two counters that
                     can. SIG_MODE=bigram and SIG_WARMUP=0 both return "budget" with
                     sig.warmup_steps and sig.warmup_probes at 0 and Gate sig.adaptive_stop
                     UNREACHABLE with the reason; a budget that genuinely ran to its end
                     returns it with steps == SIG_WARMUP. WarmupReport declares exactly these
                     three spellings, so a fourth for "the budget was inert" would be a change
                     to the record type and is the owner's to rule on, not this function's to
                     take: what is written down here instead is that "budget" is the ABSENCE
                     of a stop and not the presence of a spent budget.
    THE TWO STOP ARMS NEED DIFFERENT AMOUNTS OF CURVE, and holding both behind the larger of the
    two requirements is what put the run-level failure out of reach at the shipped defaults. The
    absolute collapse test is a statement about ONE probe; the flatness test compares a probe with
    the one before it and therefore needs TWO. SIG_WARMUP=800 with SIG_WARMUP_PROBE_EVERY=500 puts
    a single probe in the budget, and while `len(curve) < 2` guarded the whole verdict a fully
    collapsed encoder -- separation measured at -0.000000 against this 0.15 -- returned "budget",
    which is the failure below restored one level up. src/sig/api.py::_stop_verdict now takes a
    one-point curve and skips only the flatness test.
    The old test `_sep <= _prev_sep * (1 + eps)` (:5033) is true when separation is FLAT and
    EQUALLY TRUE WHEN IT IS COLLAPSING; on a single-corpus stream running 0.16 -> 0.05 (a 69%
    collapse) it reported a converged plateau, stopped, SHIFT_DIST never fired, the run found 0
    boundaries and 1 domain, and every downstream report line still printed. The post-hoc collapse
    warning at :5049 patches the REPORT, not the STOP, and no value of warmup_plateau_eps fixes it
    -- a smaller eps just stops later. "collapsing" is a RUN-LEVEL FAILURE, surfaced as such.

    The floor is a FRACTION of the budget, which makes the inverted pair (floor >= budget) that
    made the adaptive stop unreachable IMPOSSIBLE EVERYWHERE STRICTLY BELOW 1.0 and REPORTED at 1.0
    and above, rather than impossible outright: `_wfloor = min(_i("ENC_WARMUP_MIN", 200), wu)` at
    :5021 collapses the floor onto the full warmup whenever the absolute floor exceeds the budget,
    and at 3000 against 800 that turned the file's own "#1 startup cost saving" off in every
    default run while telling the run that paid the full budget it had converged. AT exactly 1.0 --
    a legal reading of a lever declared over 0..1 -- the floor IS the budget and the shape is back,
    which is why this function's gate arm for it is selected at 1.0 and not above it, and prints
    both numbers instead of clamping them together. spine/lever.py::Lever has choices and no
    numeric range, so the other end of the interval is refused here at the one site that multiplies
    the fraction by the budget: a negative fraction is not a lower floor but no floor at all.

    The probe draws from this package's own RNG stream, never the global one.

    `opt` is OptState.encoder, the AdamW over param_groups["encoder"] -- a nameable value as of
    2026-09-02 (Q-OPT-7). The composition root passes `sysm.optimizer.encoder`; until that field had
    a name it passed the whole OptState, so this pre-loop routine was handed an object through which
    it could have stepped the language model.

    LEVERS READ: mode, warmup, warmup_min_frac, warmup_plateau_eps, warmup_probe_every,
                 contrastive_batch, d
    WIRES READ: none
    DID IT FIRE: sig.warmup_steps, sig.warmup_probes, sig.warmup_verdict (one of the three
                 strings), sig.warmup_separation_peak, sig.warmup_separation_final, and
                 Gate sig.adaptive_stop with predicate int(warmup_min_frac*warmup) < warmup, so a
                 floor that cannot fire prints its own arithmetic. THE GATE REPORTS THE PLATEAU
                 STOP AND NOT THE COLLAPSE VERDICT -- they have different probe requirements and
                 the gate's own reason says on each unreachable arm whether a collapse is still
                 reachable there, computed from the probe grid rather than promised. A collapse is
                 read off sig.warmup_verdict; the number behind it is
                 sig.warmup_separation_final, which is the surface that carries the truth on any
                 setting where no probe reaches the floor.
    """
    sig = sig.owned_by("SIG")
    mode = str(sig.mode)
    budget = int(sig.warmup)
    probe_every = int(sig.warmup_probe_every)
    eps = float(sig.warmup_plateau_eps)
    pairs = int(sig.contrastive_batch)
    d = int(sig.d)
    if budget < 0:
        raise ValueError(f"SIG_WARMUP={budget}: a budget of optimizer steps cannot be negative.")
    if probe_every < 1:
        raise ValueError(
            f"SIG_WARMUP_PROBE_EVERY={probe_every}: the probe cadence is how often the separation "
            f"curve is sampled and cannot be zero or negative. It is the resolution of the only "
            f"curve that can say whether the encoder separated or collapsed.")
    # THE FLOOR IS A FRACTION OF THE BUDGET, WHICH MAKES THE INVERTED PAIR IMPOSSIBLE STRICTLY
    # BELOW 1.0 AND REPORTED FROM 1.0 UP -- and the first sentence here claimed the stronger thing,
    # that it was unrepresentable full stop, while the `floor >= budget` arm of this function's own
    # gate stood below as the proof that it is not. As an ABSOLUTE step count the inversion was
    # neither reported nor detected: `_wfloor = min(ENC_WARMUP_MIN, ENC_WARMUP)` collapsed the
    # floor onto the whole budget whenever the floor exceeded it, and at the shipped 3000 against
    # 800 that turned the adaptive stop -- the file's own "#1 startup cost saving" -- off in every
    # default run while telling the run that paid the full budget it had converged. As a fraction
    # the SAME shape returns at the TOP of the declared interval, where floor == budget, and it is
    # a gate arm there rather than a clamp: the two numbers are printed and the arm says which
    # values get the stop back.
    frac = float(sig.warmup_min_frac)
    if frac < 0.0:
        # THE OTHER END OF THE SAME RANGE, REFUSED RATHER THAN SILENTLY HONOURED. spine/lever.py
        # ::Lever carries `choices` and no numeric range, so units.FRACTION on the declaration is a
        # LABEL and not a constraint; the refusal has to stand at the one site that multiplies the
        # fraction by the budget. A negative fraction makes a negative floor, which is not a
        # weaker guard but NO guard: `t >= floor` is then true at the very first probe, the stop
        # becomes eligible before any of the budget the floor exists to protect has been spent, and
        # no gate arm below says so -- every one of them reports a floor that is merely low. It is
        # refused here for the reason SIG_MODE=bigram at width_units=1 is refused in build(): the
        # failure is a mechanism quietly doing something other than what it is declared to do.
        raise ValueError(
            f"SIG_WARMUP_MIN_FRAC={frac}: the floor is a SHARE of SIG_WARMUP={budget} and a share "
            f"cannot be negative. It would put the floor at {int(frac * budget)} step(s), which no "
            f"step count is below, so the adaptive stop would be eligible from the first probe "
            f"onward -- the guard removed rather than lowered, and reported by no gate.")
    floor = int(frac * budget)

    # WHERE THE STOP COULD FIRE, COMPUTED FROM THE LEVERS AND BEFORE THE LOOP RUNS. It is a
    # CONFIGURATION fact, not an outcome: reachability that is read off how the run happened to turn
    # out cannot distinguish "this mechanism had no opportunity" from "it had one and declined",
    # which are the two states spine/gate.py::Gate exists to keep apart. A probe is taken at each
    # multiple of the cadence; the plateau test compares a probe against THE ONE BEFORE IT, so the
    # earliest probe it can ever run at is the second, and it may not run before the floor.
    grid = tuple(range(probe_every, budget + 1, probe_every))
    stop_points = tuple(t for i, t in enumerate(grid) if i >= 1 and t >= floor)
    # THE COLLAPSE VERDICT HAS ITS OWN GRID AND IT IS WIDER, which is the whole content of the
    # repair above: _stop_verdict's absolute arm is a statement about ONE probe, so every probe at
    # or after the floor can produce it, while the flatness test the gate below names needs a
    # PREDECESSOR and therefore starts at the second. The gate's unreachable arm asserts in writing
    # which of the two survives its own setting, and that sentence has to be computed rather than
    # believed -- it was written as an unconditional promise, and at the shipped cadence, where the
    # two grids differ by exactly the one probe in the budget, it was false.
    collapse_points = tuple(t for t in grid if t >= floor)

    curve, steps, probes, verdict = [], 0, 0, "budget"
    if mode == "learned":
        # ONE torch GENERATOR, SEEDED ONCE FROM THIS PACKAGE'S OWN DECLARED STREAM -- the same two
        # lines build() uses, and for the same reason. sysm.streams["sig"] is SIG's stream and it is
        # minted once by the root; spine/rng.py::rng_for raises on a re-issue, and every one of the
        # four times this family has bitten began with a second mint. Seeding a LOCAL torch
        # generator from it costs one draw off the declared stream and creates no second name.
        # NOT st.rng.torch_generator(): that derives its seed from the stream's NAME, so warm_up and
        # train_step would both get a generator starting at the same state and draw the same
        # windows -- correlated draws with nothing in the ledger to say so.
        # CPU, because the windows are gathered from a CPU stream tensor and torch's in-place random
        # ops require the generator and the tensor to share a device.
        gen = torch.Generator()
        gen.manual_seed(int(st.rng.randint(0, 2 ** 31 - 1)))
        base = _unit_tensor(stream)
        units = min(int(seen_units), int(base.numel()))
        for t in range(1, budget + 1):
            anchors, positives = _draw_pairs(st, base, units, pairs, gen)
            loss = _contrastive_loss(sig, st, _encode_for_training(st, anchors),
                                     _encode_for_training(st, positives), d=d)
            # EVERY ITERATION IS ONE opt.step(), WHICH IS WHY THE BUDGET IS units.Steps AND NOT
            # units.Windows. There is no InfoNCE floor gate on this path: the floor gate and its
            # sig.floor_skips counter are declared on train_step, which is the loop's stepper, and
            # a skip here would make the budget count something other than optimizer steps.
            # `opt` is OptState.encoder -- the AdamW over param_groups["encoder"] -- and nothing
            # else; until that field had a name (Q-OPT-7) the root handed over the whole OptState,
            # an object through which this pre-loop routine could have stepped the language model.
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            steps = t
            if t % probe_every:
                continue
            curve.append(_separation(sig, st, base, units, 2 * pairs, gen, d=d))
            probes += 1
            # THE FLOOR IS THE ONLY THING THAT HOLDS A VERDICT BACK HERE, AND THE PROBE COUNT IS
            # NOT. `len(curve) < 2` stood beside this test and gated the WHOLE call, including the
            # absolute collapse arm that needs one probe by its own arithmetic -- so at the shipped
            # cadence, which puts a single probe in the budget, the "collapsing" RUN-LEVEL FAILURE
            # verdict could not be produced at all and a fully collapsed encoder returned "budget".
            # _stop_verdict now takes the one-point curve and skips only the flatness test.
            if t < floor:
                continue
            stop = _stop_verdict(curve, eps)
            if stop is not None:
                verdict = stop
                break
        # THE ENCODER IS HANDED TO THE LOOP WITH NO GRADIENT ON IT. Leaving the last backward's
        # .grad in place would let the first optimizer step of the run apply a warm-up gradient at
        # the loop's cadence, under a counter that says the loop trained.
        opt.zero_grad(set_to_none=True)

    peak = max(curve) if curve else None
    final = curve[-1] if curve else None
    # THIS CALL'S CURVE REPLACES WHATEVER WAS THERE. See WarmupReport: appending to a curve restored
    # from a previous run makes one curve out of two measurements, and every number the stop reads
    # -- peak, final, flatness -- would then straddle both.
    st.warmup_curve = curve
    st.counters["sig.warmup_steps"] = steps
    st.counters["sig.warmup_probes"] = probes
    st.counters["sig.warmup_verdict"] = verdict
    st.counters["sig.warmup_separation_peak"] = peak
    st.counters["sig.warmup_separation_final"] = final

    if mode != "learned":
        st.gates["sig.adaptive_stop"] = Gate(
            "sig.adaptive_stop", False, floor, budget, reachable=False,
            reason=f"SIG_MODE={mode!r}: the signature function is a frozen random projection of "
                   f"hashed bigram counts with no parameters, so there is nothing to warm up, no "
                   f"optimizer step to save and no separation curve to stop on. SIG_WARMUP="
                   f"{budget} is inert on this arm and sig.warmup_steps is 0 for that reason, not "
                   f"because a stop fired at step 0.")
    elif budget < 1:
        st.gates["sig.adaptive_stop"] = Gate(
            "sig.adaptive_stop", False, floor, budget, reachable=False,
            reason=f"SIG_WARMUP={budget}: there is no pre-loop budget, so there is nothing for an "
                   f"early stop to save and no probe curve to stop on. The encoder is handed to "
                   f"the loop at its random initialisation, which is a real configuration -- the "
                   f"warm-up's own record says 1-NN corpus accuracy PEAKS around 1000-4000 steps "
                   f"and degrades after -- but it is not this gate declining to fire.")
    elif floor >= budget:
        st.gates["sig.adaptive_stop"] = Gate(
            "sig.adaptive_stop", False, floor, budget, reachable=False,
            reason=f"SIG_WARMUP_MIN_FRAC={frac} of SIG_WARMUP={budget} is a "
                   f"floor of {floor} step(s), which is not below the budget: the stop is allowed "
                   f"to fire only after the floor, and the budget ends first. This is the "
                   f"untrippable-guard shape the fraction was introduced to make unreachable "
                   f"within its declared unit interval, and it is reachable again AT OR ABOVE "
                   f"SIG_WARMUP_MIN_FRAC=1.0 -- at exactly 1.0 the floor IS the budget, this arm "
                   f"is the one selected, and a reader who followed an earlier wording of this "
                   f"sentence to 1.0 to get the stop back would have found it still unreachable. "
                   f"Below 1.0 the floor lands inside the budget and the stop can fire again.")
    elif not stop_points:
        # THE CLAUSE ABOUT THE OTHER MECHANISM IS COMPUTED FROM THIS RUN'S GRID, NOT PROMISED. It
        # was written as an unconditional sentence -- "a collapse can still be declared" -- and at
        # the shipped SIG_WARMUP=800 / SIG_WARMUP_PROBE_EVERY=500 it was false twice over: the
        # collapse test was behind the two-probe guard removed above, and even with that gone the
        # promise only holds while some probe lands at or after the floor. A reason sentence is the
        # operator's instruction for what to read next; one that names a live surface which reads
        # 'budget' on a collapsed encoder is the failure this gate exists to report, one level up.
        still_live = (
            f"WHAT IS STILL LIVE ON THIS SETTING: the 'collapsing' verdict's ABSOLUTE arm "
            f"(separation below 0.15) is a statement about ONE probe and needs no predecessor, and "
            f"the probe(s) at step(s) "
            f"{list(collapse_points) if len(collapse_points) < 6 else list(collapse_points[:5]) + ['...']}"
            f" are at or after the floor -- so a collapse CAN be declared here and "
            f"sig.warmup_verdict is the surface that says so; what cannot fire is the early stop "
            f"this gate names."
            if collapse_points else
            f"WHAT IS NOT LIVE EITHER, SAID HERE BECAUSE THIS IS THE SURFACE THAT WOULD OTHERWISE "
            f"IMPLY IT: the 'collapsing' verdict's ABSOLUTE arm needs only one probe, but no probe "
            f"lands at or after the floor of {floor} step(s), so NO verdict can be reached on this "
            f"setting and sig.warmup_verdict reads 'budget' however the encoder ends up. The "
            f"separation itself is on sig.warmup_separation_final, which is the only surface that "
            f"can show a collapse here.")
        st.gates["sig.adaptive_stop"] = Gate(
            "sig.adaptive_stop", False, floor, budget, reachable=False,
            reason=f"SIG_WARMUP_PROBE_EVERY={probe_every} against SIG_WARMUP={budget} puts "
                   f"{len(grid)} separation probe(s) in the budget, at step(s) "
                   f"{list(grid) if len(grid) < 6 else list(grid[:5]) + ['...']}, and none of them "
                   f"is BOTH the second probe or later AND at or after the floor of {floor} "
                   f"step(s) -- so the flatness test, which compares a probe against the one "
                   f"before it, has nothing to compare. Lower SIG_WARMUP_PROBE_EVERY or raise "
                   f"SIG_WARMUP until at least two probes land inside the budget. " + still_live)
    else:
        st.gates["sig.adaptive_stop"] = Gate(
            "sig.adaptive_stop", verdict == "plateau", floor, budget,
            reason=("the warm-up DID stop early, at step {} of {}, on verdict 'collapsing' -- a "
                    "RUN-LEVEL FAILURE and not a saving. This gate reports the PLATEAU stop, which "
                    "is the mechanism the budget exists to save; a collapse stop is the opposite "
                    "finding and reads off sig.warmup_verdict.".format(steps, budget)
                   if verdict == "collapsing" else ""))

    return WarmupReport(verdict=verdict, curve=list(curve), separation_peak=peak,
                        separation_final=final, steps=steps, probes=probes)


def counters(sig: Config, st):
    """The DID IT FIRE ledger for this package: {name: (state, count, gate_arithmetic)} where state
    is one of fired / armed-but-zero / unreachable. NO MECHANISM IN THIS PACKAGE REPORTS "ON"
    WITHOUT ONE OF THESE THREE.

    LEVERS READ: mode, space, d, bigram_dim, contrastive_batch, temp, positive_radius_windows,
                 prototype_frac, floor_kinds, var_weight, cov_weight, train_every,
                 train_every_idle, dense_window, warmup, warmup_min_frac, warmup_plateau_eps,
                 warmup_probe_every
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.counters: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


def state_dict(sig: Config, st):
    """The encoder's parameters (or the frozen bigram modulus), the counters, the warmup curve and
    its verdict, and this package's RNG stream, plus a SIDECAR carrying width_units,
    alphabet_size, space, d and mode.

    NOT in the checkpoint and deliberately re-earned: the lookahead queue (the old `_sigq`), which
    any boundary invalidates anyway. The encoder optimizer's moments belong to OPT and are
    checkpointed there; SIG asserts only that a resized alphabet_size invalidates them -- which the
    old tree got wrong in the opposite direction, dropping the encoder's moments for a FABRIC
    widening (ISSUES P3-H24).

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: sig.state_written
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.state_dict: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


def load_state_dict(sig: Config, st, sd, *, sidecar):
    """Restore the encoder, REFUSING A SIDECAR THAT DISAGREES ABOUT GEOMETRY.

    The sidecar carries width_units, alphabet_size, space, d and mode. A resume that disagrees
    about any of them does not fail late with a torch shape dump -- it fails HERE, naming the
    field. The old tree recorded sig_space and enc_v and checked neither on three consumers
    (ISSUES:677), and a width that differs between the run that WROTE the centroids and the run
    that READS them makes every centroid a mean of two different measurements.

    LEVERS READ: mode, space, d (compared against the sidecar; never overriding it)
    WIRES READ: none
    DID IT FIRE: sig.resume_geometry_checked, sig.resume_refused
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.load_state_dict: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


def encoder_parameters(sig: Config, st):
    """The encoder's parameters, as a plain list, so OPT can build the encoder optimizer from them.

    THIS IS THE WHOLE OF SIG'S RELATIONSHIP WITH THE OPTIMIZER. The old tree built
    `oe = AdamW(enc.parameters(), lr=LR, weight_decay=WD)` at :4750 using OPT's two numbers inside
    the training file; here OPT builds it from this list and SIG has no opinion about optimizers at
    all. Returns [] on the bigram arm, which is a real answer and not an error: the frozen control
    has nothing to train, and OPT's "encoder" param group is then legitimately empty.

    LEVERS READ: mode
    WIRES READ: none
    DID IT FIRE: sig.encoder_params (the count -- 0 on the bigram arm is unreachable, not
                 armed-but-inert)
    """
    sig = sig.owned_by("SIG")
    # READING THE LEVER HERE IS NOT THE C4 SHAPE, and the distinction is worth one sentence because
    # this file spends four paragraphs refusing the other one. `width_units` may never be resolved
    # twice: it is the answer of spine/derive.py::signature_width_bytes over a bytes/token the
    # tokenizer MEASURED, so a second site computing it gets a second number -- 614 bytes on one
    # path and ONE BYTE on the other. `mode` is a declared literal on a frozen Config; there is one
    # Config per run, it cannot be written after startup, and reading it twice cannot produce two
    # answers. That is why encode()'s block says "LEVERS READ: none directly" while this one names
    # the lever, and why there is no assertion against st.mode below to make the read look safer
    # than it is: an assertion that cannot fail is the guard-shape this tree has 60 records of.
    mode = str(sig.mode)
    # A PLAIN LIST, WHICH IS WHAT OPT'S OWN CONTRACT ASKS FOR: opt/api.py::build declares
    # param_groups as {"base": [...Parameter], "encoder": [...Parameter]} -- "plain lists another
    # package's constructor returned" -- and spine/compose.py wraps this call in list() at the OPT
    # row. Not a generator (OPT reads the group twice, to build the AdamW and to record
    # param_group_shape, and a generator is empty the second time), and not a param-group dict
    # (the KEY is the root's, and this package "has no opinion about optimizers at all").
    params = [] if mode == "bigram" else list(st.encoder.parameters())
    st.counters["sig.encoder_params"] = len(params)
    st.gates["sig.encoder_params"] = (
        Gate("sig.encoder_params", bool(params), len(params), 1)
        if mode != "bigram" else
        Gate("sig.encoder_params", False, 0, 1, reachable=False,
             reason="SIG_MODE='bigram': the signature function is a FROZEN random projection of "
                    "hashed bigram counts, which is what makes it the control arm the learned "
                    "encoder is read against -- it has no parameters that train, so OPT's "
                    "'encoder' param group is legitimately empty and SIG.train_step has nothing "
                    "to step. Reported unreachable rather than as a count of 0, which reads as an "
                    "encoder that was built and then contributed nothing to the optimizer."))
    return params


def encoder_embedding(sig: Config, st):
    """The encoder's input nn.Embedding, or None under space="bytes".

    Handed by the composition root to LM.on_mint as `sig_emb` so that a newly minted token id gets
    a warm encoder row by the SAME rule LM uses for its own. This replaces the inline reach at
    self_organize.py:7702-7705, and SIG needs it MORE than the LM does: a domain centroid is a mean
    of encodings, so one freshly-random token id inside a window perturbs every signature
    containing it and the assembler reads that as a domain shift.

    LEVERS READ: space
    WIRES READ: none
    DID IT FIRE: sig.emb_handed_out (0 under space=bytes is unreachable, with the gate arithmetic)
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.encoder_embedding: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")
