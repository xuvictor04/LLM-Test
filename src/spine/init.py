"""Which 1-D parameters are additive and which are multiplicative — the one rule, in one place.

WHY THIS IS SHARED VOCABULARY AND NOT A HELPER IN EACH PACKAGE. Three packages allocate modules and
initialise them (LM's network, FAB's routing and identity modules, WORLD's encoder and projections),
and every one of them has to answer the same question about every 1-D tensor: is this a BIAS, which
starts at zero, or a normalisation SCALE, which starts at one? torch marks neither -- nn.LayerNorm
calls its scale `weight`, exactly as nn.Linear calls its matrix `weight`, and at 1-D the only thing
separating them is the name.

THE COST OF GETTING IT WRONG IS MEASURED, IN THIS TREE, BY THIS PROJECT. LM.build_model's first
version zeroed every 1-D tensor. That zeroes each LayerNorm's scale, which MULTIPLIES the normalised
activation, so every residual branch in the transformer output zero and half its tensors received no
gradient -- and the loss still came out at exactly ln(vocab_slots), because a uniform distribution is
what a dead network produces. A plausible number from a broken model is this project's whole subject,
and it was caught by counting which tensors received a gradient, not by reading the loss.

So the rule is asymmetric in consequence, which is why it is decided once rather than defaulted three
times: a SCALE initialised to 0 is a branch that outputs zero forever, while a BIAS initialised to 1
is merely a small offset. Three private copies would be three chances for one of them to omit a
normalisation spelling and reproduce the dead branch in a package nobody thought to check.

It reads no lever, holds no state, and imports nothing -- the same standard `gate` met when O10's
allowlist last grew.
"""

# The spellings torch and this tree actually use for a normalisation module's scale. Matched on the
# DOTTED PATH from named_parameters(), not on the leaf alone, because the leaf is always `weight`:
# "body.layers.0.norm1.weight" is a scale and "body.layers.0.linear1.weight" is not, and only the
# path tells them apart.
_SCALE_MARKERS = (".norm", "norm.", "_norm", "layernorm", "groupnorm", "rmsnorm", ".ln", "ln_")


def is_scale(name):
    """Is the 1-D parameter at this dotted path a multiplicative scale rather than an additive bias?

    Call it ONLY for tensors with dim() < 2; a 2-D `weight` is a matrix and neither branch applies.
    A name that ends in `bias` is never a scale, checked first, because "norm1.bias" contains a
    marker and is emphatically additive -- that single line is the difference between this function
    and the naive substring test.
    """
    n = str(name).lower()
    if n.endswith("bias"):
        return False
    return n.endswith("weight") and any(m in n for m in _SCALE_MARKERS)
