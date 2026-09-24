"""The back ends, of which there are two.

`interpret` walks the tree and does what each node says. `compile` turns
the tree into Python source instead, through `patterns` for the pattern
tests and `pyast` for the node building.

Both run over the same `runtime`, and that is the arrangement worth
copying. Because the values and the standard library are shared, running a
programme both ways and comparing the output tests *the compiler*. If they
were two separate implementations, a disagreement would only tell you that
two programs differ.
"""

from __future__ import annotations
