"""OPT -- schedule and optimiser. Package marker; the declarations live in levers.py.

Empty by design, for the reason src/lm/__init__.py records: a package __init__ that imports its own
submodules makes `import opt` resolve opt.levers, which would run the LeverSet declaration -- and
therefore the registry registration -- as a side effect of touching the package name. Registration
would then depend on which name an entry point happened to touch first, which is a difference between
two runs that no seed controls. tests/test_ownership.py walks src/ and imports by module path, and
spine.assemble collects lever sets from the registry, so nothing here needs re-exporting. The eight
sibling packages (fabric, sig, memory, domains, eval, tok, lm, data) are empty for the same reason.
"""
