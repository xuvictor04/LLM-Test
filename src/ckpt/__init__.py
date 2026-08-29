"""CKPT -- checkpointing. Package marker only; the declarations live in ckpt/levers.py.

Empty of code on purpose, for the same reason as tok, fabric, sig, memory and domains: an __init__ that
imported levers.py would make `import ckpt` register a LeverSet as a side effect, and registration order
would then depend on import order rather than on spine.assemble naming the packages it builds.
"""
