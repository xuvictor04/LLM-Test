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
from spine.lever import Config, LeverError


# ==================================================================================================
# WHAT A NON-FINITE VALUE OF EACH FLOAT LEVER WAS MEASURED TO DO
# ==================================================================================================
#
# One entry per float lever this package declares, in sig/levers.py::SIGLevers's own order. It is a
# MODULE CONSTANT and not a sentence inside the refusal because the refusal renders only the levers
# an operator actually set, and a reader wanting to know what the other six do should not have to
# provoke them. Every string below is a MEASUREMENT taken through spine.assemble.build in a fresh
# process at the widths sig/api.py's own harness uses (width_units=64, alphabet_size=256, a 6000-byte
# stream, seen_units=6000, AdamW over encoder_parameters, the shipped SIG_WARMUP=800) -- not a
# reading of the source.
_NONFINITE_MEASURED = {
    "SIG_TEMP":
        "the divisor on the cosine logits, `logits = (za @ zp.t()) / temp` in "
        "sig/api.py::_contrastive_loss. At nan the refusal three lines above it (`if temp <= 0.0`) is "
        "FALSE, every logit is nan, cross_entropy is nan and ONE backward() puts nan in all three "
        "encoder tensors: measured at step 1, loss=nan with emb.weight, proj.weight and proj.bias "
        "grads all non-finite; after the full 800-step warm-up every encoder parameter is non-finite "
        "and WarmupReport comes back verdict='budget' steps=800 probes=1 peak=nan final=nan "
        "curve=[nan]. At +inf every logit is EXACTLY 0.0, the InfoNCE term is exactly "
        "ln(48) = 3.8712007 -- which sig/levers.py::SIGLevers calls 'the loss of a model that has "
        "learned nothing' -- its gradient is exactly 0.0, and the contrastive objective, which is the "
        "whole purpose of this package, is deleted while only the variance hinge trains: the warm-up "
        "then reports separation 0.9927 against 0.5238 at the default, i.e. BETTER than a working "
        "encoder, with every parameter finite. AT -inf THIS CHECK NOW FIRES FIRST AND DISPLACES A "
        "REFUSAL THAT WAS ALREADY CORRECT: sig/api.py::_contrastive_loss's `if temp <= 0.0` names "
        "SIG_TEMP and explains that a negative divisor INVERTS the objective, and the sweep filed "
        "SIG_TEMP=-inf as one of its five REFUSED_BY_NAME cells. It is displaced deliberately and "
        "only in TIME -- that one fires at the first warm-up step, with an encoder built and an "
        "optimizer over it, and this one fires before either exists -- and the inversion sentence "
        "is carried here so nothing is lost with it. Every FINITE negative and 0 still reach that "
        "refusal and it keeps its full force there",
    "SIG_POSITIVE_RADIUS_WINDOWS":
        "the multiplier that freezes positive_radius_units in build() below, "
        "`round(float(sig.positive_radius_windows) * width)`. At nan that round() raises a bare "
        "`ValueError: cannot convert float NaN to integer` and at +/-inf a bare OverflowError, both "
        "from inside the SigState constructor at sig/api.py::build, naming neither the lever nor the "
        "value -- in the one function that already carries two by-name refusals. At 0 the package "
        "does refuse by name, in sig/api.py::_draw_pairs, so the gap was exactly the three "
        "non-finite spellings",
    "SIG_PROTOTYPE_FRAC":
        "the share of the InfoNCE batch drawn from one domain's reservoir. NO LIVE READER TODAY: "
        "sig/api.py::train_step is the only function that names it and it is a NotImplementedError "
        "stub, so at every value this lever passes through build, encode, cadence_due and warm_up "
        "untouched. It is refused here anyway, and the reason is the one this package states about "
        "the same lever elsewhere -- the value FREEZES INTO THE CONFIG at startup and the report "
        "prints it, so a nan sits in the run of record until the day the body lands and then sizes a "
        "slice of the batch",
    "SIG_VAR_WEIGHT":
        "the weight on the variance hinge, guarded by `if var_weight > 0.0` in sig/api.py::_var_cov "
        "-- which +inf PASSES. `inf * clamp(1-std, min=0).mean()` is inf, the loss is inf, and one "
        "backward() through it produces nan in all three encoder tensors (measured at step 1: "
        "loss=inf, grads non-finite). After the full warm-up every encoder parameter is non-finite "
        "and the report reads verdict='budget' peak=nan final=nan curve=[nan]. At nan the same "
        "`> 0.0` guard is FALSE, so the hinge is silently switched OFF and is bit-identical to the "
        "declared SIG_VAR_WEIGHT=0.0 arm while the report prints nan as the weight that ran -- the "
        "anti-collapse term this package's own header calls a certainty rather than a risk, absent, "
        "with a number beside it. At -inf the guard is False too and the same off-and-misreported "
        "shape stands",
    "SIG_COV_WEIGHT":
        "the weight on the covariance term of the same regulariser, one branch down in the same "
        "function and guarded the same way (`if cov_weight > 0.0 and n > 1`). Identical arithmetic "
        "and identical outcome: at +inf the term is inf, the loss is inf, the gradients are nan, "
        "every encoder parameter is non-finite after warm_up and the report still reads "
        "verdict='budget' peak=nan. Listed separately from var_weight because VICReg weights the two "
        "terms independently and a fix on one does not cover the other",
    "SIG_WARMUP_MIN_FRAC":
        "the share of the budget that must be spent before the plateau stop may fire. THIS ENTRY IS "
        "A MEASUREMENT OF A CLAUSE THAT NO LONGER EXISTS AND IS KEPT AS THE RECORD OF WHY IT WAS "
        "WRITTEN, not as a description of a live line: warm_up carried `if frac < 0.0: raise "
        "ValueError(...)` until 2026-09-15, when it was retired into "
        "sig/levers.py::SIGLevers's domain=(0.0, 1.0) because no environment could reach it any "
        "more. What was measured while it stood: it was the one place in this surface where a "
        "correct by-name refusal EXISTED, was entered, and died formatting its own message -- "
        "`frac < 0.0` is True for -inf, warm_up started raising the ValueError that names "
        "SIG_WARMUP_MIN_FRAC, and the f-string interpolated `int(frac * budget)` = int(-inf), which "
        "raises `OverflowError: cannot convert float infinity to integer` from inside the raise "
        "statement -- the operator got the OverflowError instead of the paragraph written for them. "
        "At nan and +inf `frac < 0.0` was False, the by-name refusal was skipped entirely, and the "
        "same expression one line down (`floor = int(frac * budget)`) raised a bare ValueError or "
        "OverflowError out of warm_up, after build() had succeeded and the encoder had been "
        "constructed. WHERE THE THREE SPELLINGS STAND NOW: refused in build() below, by the "
        "finiteness sweep, before an encoder or an optimizer exists -- and every FINITE negative "
        "is refused one layer earlier still, by the declared domain, at the first read",
    "SIG_WARMUP_PLATEAU_EPS":
        "the ONLY threshold the adaptive warm-up stop has, tested in sig/api.py::_stop_verdict as "
        "`abs(sep - prev) <= eps * abs(prev)`. THREE VALUES, THREE DIFFERENT WRONG ANSWERS. At +inf "
        "the test is true for ANY pair of probes, so the warm-up stops at the first moment two "
        "probes exist and returns verdict='plateau' -- the false-convergence stop _stop_verdict was "
        "rewritten to remove -- while Gate sig.adaptive_stop prints fired=True with reason='' : "
        "measured at SIG_WARMUP_PROBE_EVERY=200, stopped at step 400 of 800 on a RISING curve "
        "[0.453574, 0.534715]. At nan every comparison is False and at -inf likewise, so the stop "
        "can NEVER fire at any curve, and the gate prints reachable=True fired=False reason='' -- "
        "which in this tree's own three-state vocabulary reads 'armed, did not fire' for a mechanism "
        "that is structurally unreachable (measured at the same cadence: 4 probes, curve "
        "[0.453574, 0.534715, 0.469582, 0.42657], stop never eligible). At the SHIPPED "
        "SIG_WARMUP_PROBE_EVERY=500 against SIG_WARMUP=800 only one probe lands and this lever is "
        "not consulted at all, which is why all three cells above are stated with their cadence",
}


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

    THIS IS ALSO WHERE THIS PACKAGE'S LEVER DOMAIN IS REFUSED, AND THE REFUSAL IS NARROWER THAN IT
    LOOKS. Three checks stand at the top of the body, all raising spine.lever.LeverError by the
    lever's OWNED environment name: every float lever must be FINITE (unconditional); SIG_D must be
    at least 1 (unconditional -- it is the width of the space every router reads); and, on the arm
    that reads it and only there, SIG_CONTRASTIVE_BATCH >= 1 on 'learned' and SIG_BIGRAM_DIM >= 1 on
    'bigram'. WHAT IS CLOSED AND WHAT IS NOT, stated here rather than left to be inferred: the
    finiteness check closes THREE SPELLINGS of seven levers -- nan, +inf and -inf -- and closes
    NOTHING ELSE. It does not bound any lever, it does not validate any lever, and it does not make
    the mechanisms behind them safe. Measured in this package: SIG_TEMP=1e30 deletes the contrastive
    objective exactly as +inf does, to the last bit of the loss (4.845168113708496), of the three
    gradient sums and of the 800-step separation (0.9927038550376892); SIG_VAR_WEIGHT=1e38 leaves
    every encoder parameter non-finite with the report reading verdict='budget' peak=nan, which is
    bit-for-bit the critical the check was written for; and SIG_VAR_WEIGHT=1e30 prints an ordinary
    loss and an ordinary separation over gradient sums of 5.3e31. All three are finite and all three
    are admitted. A declared per-lever DOMAIN is the general answer to that and it is the owner's
    open question (.rework/audits/ruling_nonfinite.json), not this function's to settle.
    THE INT LEVERS ARE NOT IN THE FINITENESS SWEEP AND ARE NOT EXEMPT EITHER:
    spine/lever.py::Lever.coerce resolves an int lever as `int(float(raw))`, which raises ValueError
    at 'nan' and OverflowError at 'inf', and both are caught there and re-raised as a LeverError
    naming the lever -- verified, SIG_D='inf' and SIG_D='nan' and SIG_CONTRASTIVE_BATCH='inf' all
    fail inside spine.assemble.build before any Config exists. A second finiteness check here would
    be an untrippable guard. That accounts for all 18 of this package's declarations: 7 float here,
    9 int in coerce, 2 str (mode, space) in choices=.

    RETURNS: SigState.

    LEVERS READ: mode, space, d, bigram_dim, positive_radius_windows, contrastive_batch, temp,
                 prototype_frac, var_weight, cov_weight, warmup_min_frac, warmup_plateau_eps
                 -- the last seven are read for the DOMAIN REFUSAL above and for nothing else, and
                 they are named here because a read this function makes must be visible to
                 tests/test_contract.py::check_k4_levers_have_readers whatever its purpose. They
                 are not consumed: the values
                 that survive the refusal are used by sig/api.py::_contrastive_loss,
                 sig/api.py::_var_cov, sig/api.py::_draw_pairs and sig/api.py::warm_up, whose own
                 blocks declare them, and nothing here derives anything from them except
                 positive_radius_windows.
    WIRES READ: none
    DID IT FIRE: sig.width_units and sig.alphabet_size as one-shot facts on the ledger, plus
                 sig.encoder_built (mode='learned') or sig.bigram_built (mode='bigram'). Any later
                 call that observes a width other than sig.width_units RAISES.
    """
    sig = sig.owned_by("SIG")

    # ==============================================================================================
    # THE LEVER DOMAIN REFUSALS, AT THIS PACKAGE'S FIRST ENTRY POINT AND BEFORE ITS FIRST DERIVATION
    # ==============================================================================================
    #
    # WHY HERE AND NOT AT THE READER. The tree's refusal idiom is to raise spine.lever.LeverError
    # naming the LEVER and the VALUE at the FIRST read, before anything is derived from it, and
    # LeverError's own docstring says what that buys: "Always fatal, always at startup, never
    # mid-run." SIG.build is the first SIG entry point the composition root calls
    # (spine/compose.py's ASSEMBLY_ORDER row "signature"), so a refusal here is a startup failure;
    # the same refusal at the reader is a failure in sig/api.py::warm_up, several thousand
    # optimizer steps into a process that has already tokenized a corpus and built a model, and the
    # operator sees a torch-shaped stack rather than a configuration message. That difference is
    # measured, not asserted: SIG_WARMUP_MIN_FRAC=nan reached `floor = int(frac * budget)` inside
    # warm_up and produced a bare "ValueError: cannot convert float NaN to integer" naming no lever,
    # and SIG_WARMUP_MIN_FRAC=-inf entered the by-name refusal that then stood in warm_up and
    # raised OverflowError from inside that refusal's own f-string. Both are gone because neither
    # value now reaches that function. THE SECOND HALF OF THAT HISTORY, so it is not read as still
    # standing: the warm_up clause itself was retired on 2026-09-15 into
    # sig/levers.py::SIGLevers's `domain=(0.0, 1.0)`, which reaches every negative before this
    # function does -- so the OverflowError is closed twice over and the sentence above is a
    # record of what was, not a description of a live line.
    # THE PRICE, STATED RATHER THAN HIDDEN: build() now reads levers it does not use. That is a real
    # cost -- sig/levers.py::SIGLevers spends a paragraph on why an EAGER read is not free ("a
    # default that reads another knob is not a small sin here: it reads that knob EAGERLY, which is
    # how MAX_DOMAINS = _i(...) put FAB_NMAX into the 'this run read it' audit on every run") -- and
    # it is paid deliberately: what that paragraph refuses is a read that CHANGES a value, and these
    # reads change nothing and produce no default. The reads are declared in this function's LEVERS
    # READ block, which is what makes them visible to
    # tests/test_contract.py::check_k4_levers_have_readers rather than hidden.
    _nonfinite = []
    for _field in sig.keys():
        if _field.startswith("d_"):
            continue                    # a wire is another package's number arriving, not a lever
        _decl = sig.lever(_field)       # spine/lever.py::LeverView -- default, unit, OWNED env name
        if not isinstance(_decl.default, float):
            continue
        _v = float(getattr(sig, _field))
        if not math.isfinite(_v):
            _nonfinite.append((_decl.env_name, _v))
    if _nonfinite:
        # UNCONDITIONAL, AND NOT GATED ON THE ARM THAT READS THE LEVER -- which is a departure from
        # what this same file does one function down, so it is argued rather than assumed.
        # sig/api.py::cadence_due declares SIG_TRAIN_EVERY, SIG_TRAIN_EVERY_IDLE and
        # SIG_DENSE_WINDOW INERT under SIG_MODE='bigram' and states the rule as "a lever the report
        # calls inert cannot also be the lever that stops the run" -- a rule about a LEGAL value on
        # an arm that never reads it. SIG_TRAIN_EVERY=0 is a legal integer and the bigram arm never
        # divides by it. A nan is not a legal value on any arm: it is not a magnitude, a share, a
        # temperature or a tolerance, it freezes into the Config for the whole run, the report
        # prints it as the number that ran, and the day the operator flips SIG_MODE to 'learned' it
        # is the critical above. The count floors below ARE gated by arm, for exactly the reason
        # cadence_due gives, and the two are different questions.
        raise LeverError(
            f"SIG: non-finite lever(s) {', '.join(f'{k}={v}' for k, v in _nonfinite)}. This package "
            f"declares seven float levers and NONE of them gives a nan or an infinity a meaning: "
            f"every declared sentinel in sig/levers.py::SIGLevers is a ZERO -- var_weight=0.0 and "
            f"cov_weight=0.0 are the two halves of the anti-collapse regulariser off, "
            f"prototype_frac=0.0 is the prototype arm off, warmup_min_frac=0.0 is no floor and "
            f"warmup_plateau_eps=0.0 is the strictest flatness test there is. WHAT EACH ONE WAS "
            f"MEASURED TO DO: "
            + " || ".join(f"{k}={v}: " + _NONFINITE_MEASURED[k] for k, v in _nonfinite)
            + ". REFUSED AT STARTUP AND NOT DESCRIBED BY A GATE, because a Gate reason is a REPORT "
              "and the mechanism still runs: at SIG_TEMP=nan the sig.adaptive_stop gate rendered "
              "its full unreachable-arm paragraph, correctly, over an encoder whose every parameter "
              "was already nan, and WarmupReport returned verdict='budget' with separation nan. "
              "WHAT THIS REFUSAL DOES NOT DO, AND IT MUST NOT BE READ AS MORE: it closes THREE "
              "SPELLINGS (nan, +inf, -inf) on seven levers. It does NOT bound them, validate them "
              "or make them safe, and the values that do the identical damage are ordinary finite "
              "numbers this check admits. MEASURED IN THIS PACKAGE, at the widths above: "
              "SIG_TEMP=1e30 gives the same all-zero logits as +inf, the same loss to the last bit "
              "(4.845168113708496), the same gradient sums (emb 265.2186584472656, proj.weight "
              "134.94387817382812, proj.bias 274.1432800292969) and the same 800-step separation to "
              "the last bit (0.9927038550376892) -- the contrastive objective deleted at a number "
              "no check here refuses. SIG_VAR_WEIGHT=1e38 is bit-for-bit the critical this refusal "
              "was written for: verdict='budget' peak=nan final=nan curve=[nan] with all three "
              "encoder tensors non-finite. And SIG_VAR_WEIGHT=1e30 is the WORSE shape -- a printable "
              "loss (1.9479e29) and a printable separation (0.7904255390167236) over gradient sums "
              "of 5.3e31, which is an ordinary-looking report over an encoder already off its "
              "scale. A DECLARED PER-LEVER DOMAIN is the general answer and it is the owner's open "
              "question (.rework/audits/ruling_nonfinite.json), not this function's to settle.")

    # ---- THE ONE WIDTH OF THE SIGNATURE SPACE ----------------------------------------------------
    # SIG_D=0 IS FAB_RANK=0 AND FAB_DK=0 REACHED THROUGH THE OTHER GEOMETRY LEVER, and this function
    # already refuses that class one branch down: SIG_MODE=bigram at width_units=1 is refused BY NAME
    # because it "returns a well-formed all-zero signature for every window, which collapses FAB's
    # routing and DOM's boundary test with no error anywhere". A width of zero does the same thing
    # through `d` and did it on BOTH arms. It is read before `width` because it is the lever, and the
    # width is an argument.
    d = int(sig.d)
    if d < 1:
        raise LeverError(
            f"SIG_D={d}: a signature space of {d} dimension(s) is no signature space. This is the one "
            f"width every router "
            f"in the tree reads -- spine/compose.py hands it to FAB.build as signature_dim, DOM's "
            f"centroids and boundary test are distances in it, and sig/api.py::state_dict records it "
            f"as checkpoint geometry -- and a count below one is not a smaller signature space, it "
            f"is the space removed while every type check still passes. MEASURED AT SIG_D=0, on both "
            f"mode arms: build() returns a SigState whose learned encoder holds THREE PARAMETERS "
            f"WITH ZERO ELEMENTS ((alphabet_size, 0), (0, 0), (0,) -- total numel 0), or on the "
            f"bigram arm a (SIG_BIGRAM_DIM, 0) table; encode() then returns a well-formed (N, 0) "
            f"'unit vector' for every window forever, with no error. AND THE INSTRUMENT AGREES IT IS "
            f"HEALTHY, which is what makes it worse than a crash: `z @ z.t()` over width-0 rows is "
            f"the all-zero matrix INCLUDING ITS DIAGONAL -- a window is not even similar to itself -- "
            f"so sig/api.py::_separation returns mean(1 - 0) = EXACTLY 1.0, the best separation the "
            f"probe can produce, and the full 800-step warm-up reports verdict='budget' peak=1.0 "
            f"final=1.0 curve=[1.0] over a contrastive loss that was nan at every one of those 800 "
            f"steps. The two guards that would have caught it both pass: _separation's own "
            f"`z.shape[1] != d` check is 0 != 0, and every parameter is 'finite' because there are no "
            f"numbers in it. IT INTERACTS WITH THE SLOT CEILING AND MAKES IT VACUOUS: "
            f"spine/compose.py::_alphabet_size sizes this encoder's embedding at LM.vocab_slots "
            f"rather than the live vocab_size so that a mid-run vocabulary widen does not change the "
            f"encoder optimizer's moment shapes -- measured at SIG_SPACE=tokens, SIG_D=0 gives "
            f"emb.weight (4096, 0) and FAB's routing key buffer pop.cent (4096, 0), so the moment "
            f"shapes are indeed stable across a widen and stably EMPTY, and every warm encoder row "
            f"sig/api.py::encoder_embedding hands LM.on_mint for a newly minted id is a row of no "
            f"numbers. Nothing an operator can ask for is lost by this floor: SIG_D=1 is the "
            f"narrowest signature space this package has and it still has one.")

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
        # ---- THE CONTRASTIVE BATCH, REFUSED ON THE ARM THAT DRAWS IT AND NOWHERE ELSE ------------
        # GATED BY ARM, WHICH THE NON-FINITE SWEEP ABOVE DELIBERATELY IS NOT. `contrastive_batch` is
        # read by sig/api.py::warm_up's loop and by sig/api.py::train_step, both of which run only on
        # this arm -- warm_up's whole loop sits inside `if mode == "learned"` and cadence_due returns
        # False for 'bigram' before the modulo is ever evaluated -- so on the frozen-table arm B is
        # inert in exactly the sense sig/api.py::cadence_due states for its own three levers: "a
        # lever the report calls inert cannot also be the lever that stops the run." Zero is a legal
        # integer that arm never reads. It is refused HERE rather than at warm_up's first read for
        # the reason the block at the top of this function gives: this is the startup, and warm_up is
        # 800 optimizer steps into a built process.
        # WHAT B=0 WAS MEASURED TO DO, and it is silent rather than loud: warm_up runs its FULL 800
        # optimizer steps on an EMPTY batch. _draw_pairs returns (0, 64) and (0, 64), the InfoNCE
        # loss over a 0x0 logit matrix is nan, the gradients are FINITE ZEROS so the parameters
        # survive intact, and the separation probe -- 2*0 = 0 encodings, the mean of an empty triu --
        # is nan. The report is verdict='budget' steps=800 probes=1 peak=nan final=nan curve=[nan]:
        # 800 steps that trained nothing, reported as a budget spent. BOTH ARMS OF THE COLLAPSE
        # VERDICT ARE NaN COMPARISONS AND THEREFORE FALSE (verified: _stop_verdict([nan], 0.015)
        # returns None, `nan < 0.15` is False, `nan < 0.7*nan` is False), so the RUN-LEVEL FAILURE
        # verdict this module was rewritten to keep reachable on a one-point curve cannot be produced
        # at all. B is also the collapse reference ln(B) that sig/levers.py::SIGLevers calls part of
        # the diagnostic rather than a throughput setting; at 0 that reference is ln(0).
        batch = int(sig.contrastive_batch)
        if batch < 1:
            raise LeverError(
                f"SIG_CONTRASTIVE_BATCH={batch} on SIG_MODE='learned': the InfoNCE step has no "
                f"anchor/positive pairs to draw, so there is no contrastive objective. This does "
                f"not fail loudly -- measured at the shipped SIG_WARMUP=800, sig/api.py::warm_up "
                f"runs all 800 optimizer steps on an EMPTY batch: _draw_pairs returns (0, "
                f"width_units) twice, the loss over a 0x0 logit matrix is nan, the gradients are "
                f"finite ZEROS so every parameter survives unchanged, the separation probe is the "
                f"mean of an empty upper triangle and is nan, and WarmupReport comes back "
                f"verdict='budget' steps=800 probes=1 peak=nan final=nan curve=[nan] -- a spent "
                f"budget that trained nothing. Worse, every arm of the 'collapsing' verdict is then "
                f"a nan comparison and therefore False (_stop_verdict([nan], "
                f"{float(sig.warmup_plateau_eps)}) returns None), so the RUN-LEVEL FAILURE verdict "
                f"sig/api.py::_stop_verdict was rewritten to keep reachable on a ONE-PROBE curve "
                f"cannot be reached on any curve. B is also the collapse reference ln(B) and the "
                f"K-floor ln(1 + (B-1)/SIG_FLOOR_KINDS), and at 0 the first of those is ln(0). "
                f"SIG_CONTRASTIVE_BATCH=1 is the narrowest batch this objective has and is not "
                f"refused -- it is one pair with no negatives, which is a different (and visible) "
                f"complaint. This lever is INERT under SIG_MODE='bigram' and is NOT refused there.")
        encoder = _Encoder(int(alphabet_size), d, gen, device=device)
    elif mode == "bigram":
        # THE FROZEN TABLE ARM. A random projection of bigram counts -- no parameters that train,
        # which is what makes it the control arm the learned encoder is read against.
        # ---- ITS WIDTH, REFUSED ON THE ARM THAT ALLOCATES IT ------------------------------------
        # THE SECOND HALF OF A REFUSAL THIS FUNCTION ALREADY MAKES. Four lines up, SIG_MODE=bigram
        # at width_units=1 is refused BY NAME, and a reader of that refusal would reasonably conclude
        # this arm's build-time geometry is checked. It was not: at SIG_BIGRAM_DIM=0 build() returns
        # a SigState holding an EMPTY (0, SIG_D) table with no warning, and the FIRST encode() then
        # dies inside the hash with `RuntimeError: ZeroDivisionError` from `% st.encoder.shape[0]`,
        # naming no lever and no value. Every window of the run fails, so this one is loud -- but it
        # is loud in the wrong place and in the wrong words, which is the same defect class as the
        # zero signature, not a different one. Gated to this arm because the lever's own help text
        # says it is "inert unless mode='bigram'" and cadence_due's rule applies: a lever the report
        # calls inert cannot also be the lever that stops the run.
        bigram_dim = int(sig.bigram_dim)
        if bigram_dim < 1:
            raise LeverError(
                f"SIG_BIGRAM_DIM={bigram_dim} on SIG_MODE='bigram': the frozen hashed-bigram table "
                f"is the modulus of the bigram hash and the row count of the projection it indexes, "
                f"and a width below one is not a smaller control arm -- it is no table. Measured: "
                f"build() accepts it today and returns a SigState holding an empty (0, SIG_D="
                f"{d}) table, and the first sig/api.py::encode call raises `RuntimeError: "
                f"ZeroDivisionError` from `(units[:, :-1] * 31 + units[:, 1:]) % st.encoder."
                f"shape[0]` -- naming neither this lever nor its value, in a function whose sibling "
                f"refusal four lines above names SIG_MODE=bigram and SIG_WIDTH_UNITS in full. This "
                f"lever is INERT under SIG_MODE='learned' and is NOT refused there.")
        table = torch.empty(bigram_dim, d, device=device)
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
        space=str(sig.space), mode=mode, d=d,
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
    both numbers instead of clamping them together. THE OTHER END IS NOT REFUSED HERE AND NO LONGER
    PRETENDS TO BE: spine/lever.py::Lever carries `domain=` as well as `choices=` now, the
    declaration reads domain=(0.0, 1.0), and spine/lever.py::Lever.coerce raises LeverError naming
    SIG_WARMUP_MIN_FRAC and its value at the first read. The `if frac < 0.0` clause that stood at
    this function's one multiplying site was retired into that declaration on 2026-09-15 rather
    than kept beside it, because nothing could reach it any more; what it knew -- that a negative
    fraction is not a lower floor but no floor at all -- moved with it, MEASURED: at
    SIG_WARMUP=20 / SIG_WARMUP_PROBE_EVERY=2 on a collapsing stream, frac=0.25 puts the floor at 5
    and the run-level failure verdict is reached at step 6, while frac=-0.5 puts it at -10 and the
    same verdict is reached at step 2, on the FIRST probe, with Gate sig.adaptive_stop printing
    reachable=True, a value of -10 against a threshold of 20 and an empty reason.

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
    # THE NEGATIVE END IS REFUSED ONE LAYER EARLIER AND NOT AGAIN HERE. A `if frac < 0.0: raise`
    # stood on this line until 2026-09-15 and was RETIRED, not deleted: what it argued now sits on
    # the declaration in sig/levers.py::SIGLevers beside `domain=(0.0, 1.0)`, which is the rule
    # that answers. Retired because it can no longer run -- spine/lever.py::Lever.coerce raises
    # LeverError naming SIG_WARMUP_MIN_FRAC and the value at the FIRST read, so no environment
    # reaches this function with a negative frac -- and a guard nothing can trip is a line a
    # future reader trusts and a future edit silently breaks, which is this repository's
    # most-recorded defect (60 of the survey's 475 records).
    # WHICH OF THE TWO WAS WIDER, DRIVEN AND NOT READ, one fresh process per cell against the
    # real spine.assemble.build at SIG_WARMUP=20 / SIG_WARMUP_PROBE_EVERY=5, with the pair in
    # place and then neutralised in a copy of the tree outside the repository:
    #   the clause covered exactly (-inf, 0.0)  -- -1e-320 refused, -0.0 and 0.0 built
    #   the pair covers (-inf, 0.0) U (1.0, inf) -- the same negatives refused BY NAME, and
    #                                               1.0000000000000002, 1.5, 2.0, 1e9 and 1e308
    #                                               refused as well, none of which this clause
    #                                               ever looked at
    # With the pair neutralised, SIG_WARMUP_MIN_FRAC=1e9 BUILT with floor=20000000000 against a
    # budget of 20 -- the untrippable-guard shape this whole lever was made a fraction to remove,
    # walked straight back in -- and 1e308 died at the line below with a bare `OverflowError:
    # cannot convert float infinity to integer` naming no lever. Dropping the pair to keep the
    # clause would have removed a working refusal to make a check green.
    # BOTH LAYERS AGREE AT EVERY ENDPOINT, which is why this is pre-emption and not the one-point
    # disagreement OPT_LR_MIN_FRAC turned out to be: -0.0, 0.0 and 1.0 all build under either
    # rule alone. 1.0 is the value with the history and it is ADMITTED on purpose -- see the
    # `floor >= budget` arm below, which is selected there and nowhere under it.
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
    enc = getattr(st, "encoder", None)
    out = {
        # THE ENCODER, OR THE FROZEN BIGRAM MODULUS. Both arms come through `st.encoder`; only one
        # of them is an nn.Module, so the branch is on what is there rather than on a lever -- the
        # lever already chose, and re-reading it here would be a second answer to one question.
        "encoder": enc.state_dict() if hasattr(enc, "state_dict") else enc,
        "counters": dict(st.counters),
        # THE WARMUP CURVE AND ITS VERDICT. The curve is what SIG.warm_up built and what a reader
        # uses to tell a converged plateau from a collapse; without it a resumed run reports a
        # warmup it cannot show.
        "warmup_curve": list(getattr(st, "warmup_curve", ()) or ()),
        "warmup_verdict": st.counters.get("sig.warmup_verdict"),
        # THIS PACKAGE'S RNG STREAM, so a resume does not replay the draws the first run already
        # spent. spine/rng.py::Rng wraps random.Random, and the pair (its state, the draw count) is
        # the whole of the stream's position.
        "rng": (st.rng._r.getstate(), int(st.rng._draws)) if getattr(st, "rng", None) else None,
        # THE SIDECAR. SIG.load_state_dict refuses a resume that disagrees about any of these, BY
        # FIELD -- the old tree recorded sig_space and enc_v and checked neither on three consumers
        # (ISSUES:677), and a width that differs between the run that WROTE the centroids and the
        # run that READS them makes every centroid a mean of two different measurements.
        "sidecar": {
            "width_units": int(st.width_units), "alphabet_size": int(st.alphabet_size),
            "space": st.space, "d": int(st.d), "mode": st.mode,
        },
    }
    # NOT IN IT AND DELIBERATELY RE-EARNED: the lookahead queue (the old `_sigq`), which any
    # boundary invalidates anyway. The encoder optimizer's moments belong to OPT and are
    # checkpointed there; this package asserts only that a resized alphabet_size invalidates them
    # -- which the old tree got wrong in the OPPOSITE direction, dropping the encoder's moments for
    # a FABRIC widening (P3-H24).
    st.counters["sig.state_written"] = st.counters.get("sig.state_written", 0) + 1
    return out


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
    st.counters["sig.resume_geometry_checked"] = st.counters.get(
        "sig.resume_geometry_checked", 0) + 1
    # THE SIDECAR IS THE AUTHORITY AND THE LEVERS ARE THE COMPARISON, never the other way round.
    # LEVERS READ says "compared against the sidecar; never overriding it": if they disagree the
    # resume is REFUSED, because silently preferring either one produces a run whose centroids were
    # measured in a space its own report does not describe.
    live = {"width_units": int(st.width_units), "alphabet_size": int(st.alphabet_size),
            "space": st.space, "d": int(st.d), "mode": st.mode}
    for field, was in (sidecar or {}).items():
        if field in live and was != live[field]:
            st.counters["sig.resume_refused"] = st.counters.get("sig.resume_refused", 0) + 1
            raise LeverError(
                f"SIG resume refused on {field}: the checkpoint was written at {was!r} and this "
                f"run resolves {live[field]!r}. This fails HERE, by name, rather than late with a "
                f"torch shape dump -- a width that differs between the run that WROTE the "
                f"centroids and the run that READS them makes every centroid a mean of two "
                f"different measurements, and nothing downstream can detect that.")
    enc = getattr(st, "encoder", None)
    saved_enc = sd.get("encoder")
    if saved_enc is not None and hasattr(enc, "load_state_dict"):
        enc.load_state_dict(saved_enc)
    if sd.get("counters"):
        st.counters.update(sd["counters"])
    if sd.get("warmup_curve") is not None:
        st.warmup_curve = list(sd["warmup_curve"])
    if sd.get("rng") and getattr(st, "rng", None) is not None:
        state, draws = sd["rng"]
        st.rng._r.setstate(state)
        st.rng._draws = int(draws)
    return st


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
