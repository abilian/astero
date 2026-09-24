"""A compiler for the OCaml subset taught in French *classes préparatoires*.

It reads a programme, works out what the names in it refer to and what type
everything has, and then either runs it or turns it into Python. You can
watch each of those steps happen: `python -m ocaml --types yours.ml` prints
the types it worked out, `--names` prints the scopes, `--python` prints the
code it would generate.

The layout is the one a compiler course uses, and each part is a directory:

* **`front/`** turns text into a tree. Lexer, parser, and a printer that
  turns the tree back into text.
* **`middle/`** works out what the tree *means*: which name refers to which
  definition, and what type each expression has.
* **`back/`** runs it. There are two back ends, `interpret` and `compile`,
  and they share one runtime, so comparing them tests the compiler rather
  than comparing two languages.

`syntax.py` sits above all three, because the tree is the thing they all
talk about.

This is a worked example inside [astero](https://astero.lab.abilian.com),
which is a library for deriving a compiler's middle end from a declaration
rather than writing it out. `middle/grammar.py` is that declaration, and
`middle/analyze.py` is what it buys.
"""

from __future__ import annotations
