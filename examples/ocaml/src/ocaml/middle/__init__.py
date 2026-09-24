"""The middle end: working out what the tree means.

The front end knows the programme is well-formed. It does not know that the
`x` on line 9 is the one bound on line 3, or that adding it to a string is
a mistake. That is this part.

`grammar` is a description of the tree, written for
[astero](https://astero.lab.abilian.com), and `analyze` derives the scopes
and the name resolution from it rather than walking the tree by hand.
`unify`, `prelude` and `infer` are type inference: the algorithm, the
initial environment, and one rule per kind of node.

Nothing here imports the back end, and that is deliberate. What a name
refers to and what type it has are settled before anything runs, which is
why `prelude` holds the names and their types while `back/runtime.py` holds
their values.
"""

from __future__ import annotations
