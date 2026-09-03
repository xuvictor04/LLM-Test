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
                alphabet_size, space, mode, d, counters, warmup_curve, rng
  StepOutcome   loss, stepped, why, n_prototype
  WarmupReport  verdict ("plateau" | "collapsing" | "budget"), curve, separation_peak,
                separation_final, steps, probes
"""
import dataclasses

import torch
from torch import nn

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

    LEVERS READ: none directly -- everything comes off SigState (st.mode, st.d, st.width_units,
                 st.encoder), which build() froze from mode, d and bigram_dim once
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
                 on idle -- two different findings the report must be able to separate.
    """
    sig = sig.owned_by("SIG")
    _ = sig.d_idle_cadence           # WIRE READ HERE -- the throttled arm's threshold
    raise NotImplementedError(
        "SIG.cadence_due: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


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


def warm_up(sig: Config, st, *, stream, seen_units, opt):
    """Train the encoder unsupervised before the main loop, AND STOP HONESTLY.

    Runs at most sig.warmup optimizer STEPS (not windows -- this is the pre-loop budget and each
    iteration is one opt.step). Every warmup_probe_every steps it takes a separation probe (mean
    pairwise cosine distance of 2*contrastive_batch random encodings, ENCODED AT st.width_units)
    into a curve. After warmup_min_frac * warmup steps the stop may fire, and it returns ONE OF
    THREE VERDICTS, never a binary:
        "plateau"    separation flat within warmup_plateau_eps and >= 0.85 of its own peak
        "collapsing" separation below 0.7 of its peak, or below 0.15 absolute
        "budget"     the full budget ran with no plateau
    The old test `_sep <= _prev_sep * (1 + eps)` (:5033) is true when separation is FLAT and
    EQUALLY TRUE WHEN IT IS COLLAPSING; on a single-corpus stream running 0.16 -> 0.05 (a 69%
    collapse) it reported a converged plateau, stopped, SHIFT_DIST never fired, the run found 0
    boundaries and 1 domain, and every downstream report line still printed. The post-hoc collapse
    warning at :5049 patches the REPORT, not the STOP, and no value of warmup_plateau_eps fixes it
    -- a smaller eps just stops later. "collapsing" is a RUN-LEVEL FAILURE, surfaced as such.

    The floor is a FRACTION of the budget, so the inverted pair (floor > budget) that made the
    adaptive stop unreachable is UNREPRESENTABLE: `_wfloor = min(_i("ENC_WARMUP_MIN", 200), wu)`
    at :5021 collapses the floor onto the full warmup whenever the absolute floor exceeds the
    budget, and at 3000 against 800 that turned the file's own "#1 startup cost saving" off in
    every default run while telling the run that paid the full budget it had converged.

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
                 floor that cannot fire prints its own arithmetic
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.warm_up: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


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
    raise NotImplementedError(
        "SIG.encoder_parameters: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


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
