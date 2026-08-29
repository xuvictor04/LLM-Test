"""SIG -- the signature encoder.

Deliberately empty of code. The package's declarations live in sig/levers.py, and an __init__ that
imported them would make `import sig` register the lever set as a side effect of touching the
package at all -- which is how the old tree ended up with a module whose import order decided what
was read from the environment. spine/assemble.py imports the lever set explicitly, by name.
"""
