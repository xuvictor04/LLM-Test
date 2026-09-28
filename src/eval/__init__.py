"""EVAL -- the instruments and the report. Package marker only; the declarations live in levers.py.

`spine` next door is an implicit namespace package with no __init__.py, so this file is not strictly
required for the import to work. It is here for the same reason src/memory/__init__.py is: an implicit
namespace package silently MERGES with any other directory of the same name earlier on sys.path, and this
tree's root, which held the old tree's loose scripts until 2026-09-28, could grow an `eval/` of its own.
An explicit package refuses that merge instead of half-importing something nobody chose.
"""
