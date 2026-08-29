"""CAP -- the earned-capacity valve: when a run may become bigger than it was.

Empty on purpose, like every other package's __init__. The levers live in capacity/levers.py and are
resolved by spine.assemble; importing anything here would give a second place for a CAP value to come
from, which is the one thing the ownership spine exists to prevent.
"""
