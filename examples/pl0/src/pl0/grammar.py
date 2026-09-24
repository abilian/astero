"""PL/0 declared to astero: roles, namespaces, and one scope entry.

This is the whole declaration. Everything the rest of the compiler asks
about names is computed from it.

Three things are worth reading closely, because they are what a Python-only
example cannot show:

* **The AST is not Python's.** `from_dataclasses` reads the field names,
  sorts and shapes off the annotations in `syntax.py`, so the only thing
  authored here is the roles.

* **Declaring binds; assigning does not.** In Python `x = 1` introduces `x`.
  In PL/0 `var x` introduces it and `x := 1` writes to something already
  declared. So `Var.name` is `def(vars)` and `Assign.name` is `use(vars)`.
  The same query answers differently for the two languages because the two
  declarations differ, and for no other reason.

* **Two namespaces.** A procedure name and a variable name are both
  identifiers and live in separate namespaces, so `binds(node, VARS)` never
  reports a procedure and a pass over variables never renames a `call`.
"""

from __future__ import annotations

from astero.grammar import defines, from_dataclasses, uses
from astero.scopes import Scope

from . import syntax

#: The two families of names PL/0 has.
VARS = "vars"
PROCS = "procs"

#: The sort that marks a field as holding a name. `syntax.Ident` is `str`
#: under a different name, which is the whole trick: it lets the declaration
#: separate identifiers from data that merely happens to be a string, such
#: as `BinOp.op`.
IDENT = "Ident"

ROLES = {
    # Declarations introduce a name.
    "Const": {"name": defines(VARS)},
    "Var": {"name": defines(VARS)},
    "Procedure": {"name": defines(PROCS)},
    # Uses refer to one.
    "Name": {"name": uses(VARS)},
    "Assign": {"name": uses(VARS)},
    "Call": {"name": uses(PROCS)},
}

PL0 = from_dataclasses(
    "pl0",
    syntax.CLASSES,
    roles=ROLES,
    namespaces=(VARS, PROCS),
    ident_sorts=(IDENT,),
)

#: Which productions open a scope, and which of their fields are evaluated
#: inside it. PL/0's whole scope structure is this one entry: a procedure's
#: *name* belongs to the block that encloses it, while its *block* is a new
#: scope. That is what makes `call` resolve outwards and a local `var`
#: shadow an outer one.
SCOPES: dict[str, tuple[Scope, ...]] = {
    "Procedure": (Scope("procedure", inside=("block",), name_field="name"),),
}
