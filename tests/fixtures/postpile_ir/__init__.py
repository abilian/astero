"""postpile's IR and runtime tables, declared to astero.

Two read-only mirrors of another project's internals, kept as worked examples
rather than shipped in the package. astero imports nothing from postpile and
postpile does not know about these files; they exist to answer two questions
the Python grammar cannot.

`grammar.py` asks whether the notation that declares a *tree* AST also declares
a flat SSA IR, or whether the core needs a disjunction. `runtime.py` asks what
a `Family` buys over the sixteen hand-keyed dictionaries it mirrors.

They live here, next to `pl0` and `tinypy`, because that is what they are.
A generic library has no business shipping one named consumer's private
instruction set in its public namespace.
"""
