"""The description of the tree that everything about names is derived from.

This is the file the whole example exists to show. It is 40 lines of
declaration, and from it come the scope tree, the name resolution, the
renaming, and four separate checks that no part of the compiler has
forgotten a kind of node.

The idea, which is [astero](https://astero.lab.abilian.com)'s, is that a
compiler asks the same handful of questions about names over and over —
which positions introduce a name, which refer to one, which open a new
scope — and that those questions have one answer per language. Write the
answer down once and the passes follow from it. Write it out in each pass
and they drift.

So each field of each kind of node gets a **role**:

    def(ns)   this field introduces a name
    use(ns)   this field refers to one
    child     an ordinary subtree
    attr      plain data, not a name at all

`from_dataclasses` reads the field names, sorts and shapes off the
annotations in `syntax.py`, so the only thing written by hand here is the
roles and the scopes.

Three things this language shows that a smaller one cannot:

* **Five namespaces**, where the PL/0 example has two. In OCaml a record
  label `x` and a variable `x` are unrelated, so renaming the variable must
  not touch `r.x`. Keeping `vals` and `fields` apart is what makes that
  impossible to get wrong. `exception E` and `type t = E` both declare a
  constructor and OCaml lets the later shadow the earlier, so both are
  `def(cons)` and shadowing needs no special case anywhere.

* **A pattern is a tree, and every variable in it binds.** In
  `match l with h :: t -> ...`, both `h` and `t` are new names, and they
  are two levels down inside the pattern. The role goes on the leaf —
  `PVar.name` is `def(vals)` — and the scope entry says the pattern field
  is evaluated inside the new scope. The binding then lands in the right
  block with no library change at all.

* **A production opens a scope only where it has something to bind.**
  `Present("params")` gives `let f x = e` a scope for `x` and leaves
  `let x = e` without one.

Two things it gets *wrong*, both found by running it, and both worth
knowing because they are the honest edge of the idea. `README.md`, *Two residuals*,
has the long version.

1. **`let` and `let rec` look the same to this.** In OCaml a plain
   `let p = e in b` evaluates `e` in the scope *around* the `let`, so
   `let x = x + 1 in ...` reads the outer `x`. Saying that needs a
   binding's pattern routed inside the new scope and its value routed
   outside, and both live in the same field of `LetIn`. `Scope.inside`
   names a field, so it can put both in or both out and nothing else.

2. **A bare identifier on a scope-opening production always binds
   outside it**, which is what Python needs for `def f`. OCaml's
   `for i = a to b do ... done` needs the opposite, so `For.var` holds a
   `PVar` node rather than a plain string: a node can be routed, a string
   cannot.
"""

from __future__ import annotations

from astero.grammar import Present, defines, defuse, from_dataclasses, uses
from astero.scopes import Scope
from ocaml import syntax

#: The five families of names OCaml keeps apart.
VALS = "vals"
CONS = "cons"
FIELDS = "fields"
TYPES = "types"
TYVARS = "tyvars"

NAMESPACES = (VALS, CONS, FIELDS, TYPES, TYVARS)

#: The sort that marks a field as holding a name. `syntax.Ident` is `str`
#: under a different name, which is what separates an identifier from data
#: that merely happens to be a string, such as `BinOp.op`.
IDENT = "Ident"

ROLES = {
    # Values. Only a pattern binds one, and every pattern variable does.
    "PVar": {"name": defines(VALS)},
    "PAlias": {"name": defines(VALS)},
    "Var": {"name": uses(VALS)},
    # Constructors. `exception E` and a variant `E` share the namespace,
    # because OCaml shares it: both declare a constructor, and the later one
    # shadows the earlier.
    "Variant": {"name": defines(CONS)},
    "ExnItem": {"name": defines(CONS)},
    "Construct": {"name": uses(CONS)},
    "PConstruct": {"name": uses(CONS)},
    # Record labels.
    "FieldDef": {"name": defines(FIELDS)},
    "FieldBind": {"label": uses(FIELDS)},
    "PField": {"label": uses(FIELDS)},
    "GetField": {"label": uses(FIELDS)},
    "SetField": {"label": uses(FIELDS)},
    # Type names and type variables.
    "TypeDef": {"name": defines(TYPES), "params": defines(TYVARS)},
    "TCon": {"name": uses(TYPES)},
    # `defuse`: in `(l : 'a list)` a type variable declares itself, as
    # OCaml quantifies it implicitly. In `type t = 'a list` it has to be a
    # parameter, and `infer._only_parameters` holds that, because a role
    # belongs to the field and this field is the same in both positions.
    "TVar": {"name": defuse(TYVARS)},
}

OCAML = from_dataclasses(
    "ocaml",
    syntax.CLASSES,
    roles=ROLES,
    namespaces=NAMESPACES,
    ident_sorts=(IDENT,),
    # `Span` is a type alias for a pair of offsets, so it reads as a sort
    # this grammar never declares. Without saying so, an unroled field of an
    # unknown sort becomes a `child`, and every traversal would descend into
    # a tuple. Naming it data is what keeps `span` out of the tree.
    data_sorts=("str", "int", "bool", "float", "object", "Span"),
)

#: Which productions open a scope, and which of their fields are evaluated
#: inside it. Every other field is evaluated in the enclosing scope, which is
#: what puts a `let`'s right-hand side outside the `let` and a `match` arm's
#: pattern inside the arm.
SCOPES: dict[str, tuple[Scope, ...]] = {
    "Fun": (Scope("fun", inside=("params", "body")),),
    "Case": (Scope("case", inside=("pattern", "guard", "body")),),
    # `let x = e` binds nothing over `e`, so it opens nothing. `let f x = e`
    # binds `x` over it, so it does.
    "Binding": (Scope("binding", inside=("params", "value"), when=Present("params")),),
    "For": (Scope("for", inside=("var", "body")),),
    # One layer, and not two conditioned on `recursive`. Residual 1 above is
    # why: the difference between `let` and `let rec` is not in which fields
    # of `LetIn` are inner.
    "LetIn": (Scope("let", inside=("bindings", "body")),),
}
