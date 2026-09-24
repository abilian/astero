"""astero: declared grammars, and the transformations derived from them.

A grammar is declared once, in `astero.grammar`; everything else is computed
from it. `scopes` builds the scope tree, `coverage` fails a test when a
dispatch table misses a production the grammar declares, `emit` is a document
algebra with a bracketing rule, `emit_rules` generates target code from
templates, and `tables` holds the matrices no grammar derives.

Nothing here is about any one language. `astero.python` is the language that
ships with the library: Python's grammar, its emitter, its precedence, and the
two passes that only make sense over a Python tree — `rewriting`, whose
`fix_contexts` computes an expression context that exists nowhere else, and
`hygiene`, whose substitution is over `Name` nodes.

For a language of your own, declare it: `examples/pl0` does it in one table
over annotated dataclasses and imports no Python grammar at all.
"""

from __future__ import annotations
