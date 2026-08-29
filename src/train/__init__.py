"""RUN -- the training loop. Package marker; the declarations live in train/levers.py.

Empty by design, for the reason src/opt/__init__.py and src/lm/__init__.py record: a package __init__
that imports its own submodules makes `import train` resolve train.levers, which runs the LeverSet
declaration -- and therefore the registry registration -- as a side effect of touching the package name.
Registration would then depend on which name an entry point happened to touch first, a difference
between two runs that no seed controls. tests/test_ownership.py walks src/ and imports by module path,
and spine.assemble collects lever sets from the registry, so nothing here needs re-exporting.

THE DIRECTORY IS `train` AND THE PREFIX IS `RUN`, deliberately and not by oversight. The census names the
owning package RUN (CENSUS.md:40, "RUN | 9 | the loop"), and the environment name is generated from the
PREFIX, never from the directory -- so the operator sets RUN_SEED whatever this folder is called. The
tree already has two of these (capacity/ owns CAP, domains/ owns DOM); nothing reads the directory name.
"""
