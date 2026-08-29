"""DOM -- the self-assembling partition: where the stream is cut, what the pieces are called, and
which of those names survive.

Package marker only; the declarations live in domains/levers.py. Empty of code on purpose -- anything
importable from here would be a second place a DOM value could come from, and the whole point of the
lever spine is that there is exactly one.

It is an EXPLICIT package rather than an implicit namespace one (which would also import, since
`spine` next door has no __init__.py) because this tree already contains a module whose name collides
with what this package will grow into: self_organize.py holds the DomainAssembler at :3440-3705, and
an implicit namespace package silently merges with any other `domains` directory that turns up
earlier on sys.path. A silent merge of two partitions is the exact failure the partition exists to
prevent, one level up.
"""
