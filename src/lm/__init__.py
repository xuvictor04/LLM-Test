"""LM -- the base language model. Package marker; the declarations live in levers.py.

Empty by design: a package __init__ that imports its own submodules makes `import lm` resolve
lm.levers, which would run the LeverSet declaration -- and therefore the registry registration --
as a side effect of touching the package name. tests/test_ownership.py walks src/ and imports what
it needs by module path, and spine.assemble collects lever sets from the registry, so nothing here
needs to be re-exported. The sibling packages (fabric, sig, memory, domains, eval, tok) are empty
for the same reason.
"""
