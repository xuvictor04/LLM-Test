"""TOK -- the online byte-BPE. Package marker only; the declarations live in tok/levers.py.

Empty of code on purpose, for the same reason as fabric, sig, memory and domains: an __init__ that
imported levers.py would make `import tok` register a LeverSet as a side effect, and registration order
would then depend on import order rather than on spine.assemble naming the packages it builds. It is kept
as a file rather than relying on namespace packages so that this note has somewhere to live.
"""
