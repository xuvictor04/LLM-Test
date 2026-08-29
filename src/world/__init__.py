"""WORLD -- the world model. Package marker; the declarations live in levers.py.

Empty by design: a package __init__ that imports its own submodules makes `import world` resolve
world.levers, which would run the LeverSet declaration -- and therefore the registry registration --
as a side effect of touching the package name. tests/test_ownership.py walks src/ and imports what
it needs by module path, and spine.assemble collects lever sets from the registry, so nothing here
needs to be re-exported. The sibling packages (fabric, lm, sig, memory, domains, eval, tok, data)
are empty for the same reason.
"""
