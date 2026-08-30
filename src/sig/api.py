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
from spine.lever import Config


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
    the encoder optimizer's moment shapes -- which is ISSUES H24 from the other side.

    positive_radius_units = round(sig.positive_radius_windows * width_units), frozen here.

    RETURNS: SigState.

    LEVERS READ: mode, space, d, bigram_dim, positive_radius_windows
    WIRES READ: none
    DID IT FIRE: sig.width_units and sig.alphabet_size as one-shot facts on the ledger, plus
                 sig.encoder_built (mode='learned') or sig.bigram_built (mode='bigram'). Any later
                 call that observes a width other than sig.width_units RAISES.
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.build: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


def encode(sig: Config, st, windows):
    """Signatures for N windows in one call. (N, width_units) ints -> (N, sig.d) unit vectors.

    THE ONLY WAY TO OBTAIN A SIGNATURE, on every path -- training, eval, generation, checkpoint
    replay, instruments. There is no eval variant, no gist placeholder and no fallback: a caller
    that cannot supply width_units units gets an EXCEPTION, never a narrower window and never a
    zero vector. This is the whole of the C4/C5 repair.

    Runs under no_grad and never touches the optimizer, so an instrument calling it cannot move the
    encoder (the G7 digest holds across it).

    LEVERS READ: mode, d, bigram_dim
    WIRES READ: none
    DID IT FIRE: sig.encode_calls, sig.encode_windows, and sig.encode_width_seen asserted equal to
                 st.width_units on EVERY call -- a nonzero sig.encode_width_mismatch is the C4
                 alarm and is a HARD FAILURE, not a warning
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.encode: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


def cadence_due(sig: Config, st, *, step_windows, windows_since_boundary):
    """The shift gate: is a contrastive step due at this window?

    Dense (train_every) while the stream is within dense_window of the last detected boundary,
    throttled (train_every_idle) once it has been stable. All three thresholds are Windows and are
    compared against a Windows clock; windows_since_boundary is supplied by the caller from DOM's
    last boundary -- SIG DOES NOT REACH FOR IT. sig/levers.py:385 calls it "d_last_boundary"; it is
    RUNTIME STATE and cannot be a build-time wire, which is a correction to that comment and not a
    disagreement with L2: the value still arrives from outside and the reader still never names the
    foreign lever.

    LEVERS READ: mode, train_every, train_every_idle, dense_window
    WIRES READ: none
    DID IT FIRE: sig.cadence_dense, sig.cadence_idle, sig.cadence_checks. sig.cadence_idle == 0 for
                 a whole run means the gate never left the dense arm; sig.cadence_dense == 0 after
                 step dense_window means no boundary was ever detected and the gate is stuck open
                 on idle -- two different findings the report must be able to separate.
    """
    sig = sig.owned_by("SIG")
    raise NotImplementedError(
        "SIG.cadence_due: P4 (sig) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section SIG.")


def train_step(sig: Config, st, *, stream, seen_units, opt, reservoir=None):
    """One InfoNCE step. Returns StepOutcome(loss, stepped, why, n_prototype).

    `stream` is the unit stream this package's alphabet is over (bytes under space="bytes", token
    ids under space="tokens") as a device tensor; `seen_units` bounds the anchor draw to material
    the loop has actually reached. `opt` is the ENCODER OPTIMIZER, BUILT BY OPT AND HANDED IN --
    SIG never names a learning rate. `reservoir`, when given, is a list of (window, window) pairs
    drawn from ONE domain's reservoir by DOM.

    ANCHORS AND POSITIVES ARE DRAWN AT st.width_units, NOT AT THE LOOP WINDOW. The old tree drew
    them at WIN (:3323, :3326 -- `torch.arange(WIN)`) while applying the encoder to `_sigw` bytes
    (:6646), so the encoder was trained on 128-byte windows and used on 614-byte ones. No crash --
    a GRU accepts any length -- and no report line. This is C4's other half, on the side nobody
    looked at: the encoder's learned invariance was never measured on the material it is used on.

    The positive offset is drawn in [width_units//2, positive_radius_units], and the radius MAY GO
    BELOW ONE WINDOW: the old `max(2*WIN, ENC_POS_MAX)` clamp (:3311) could only WIDEN it, while
    the file's own diagnosis says narrowing is the fix (ISSUES L15).

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
    widening (ISSUES H24).

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
