"""A compiler for PL/0, Wirth's teaching language, built on astero.

A package rather than loose modules: a directory of top-level modules put on
`sys.path` shadows any standard one it happens to name, and `syntax`,
`parser` and `types` are all names something in the standard library has
held.
"""

from __future__ import annotations
