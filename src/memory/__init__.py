"""MEM -- the editable store. Package marker only; the declarations live in levers.py.

`spine` next door is an implicit namespace package with no __init__.py, so this file is not required for
the import to work. It is here because a package that will hold the store, its eviction rules and its
read path should be an explicit package from the start: an implicit namespace package silently merges
with any other `memory` directory that turns up earlier on sys.path, and this tree already has a
memory.py at the repo root.
"""
