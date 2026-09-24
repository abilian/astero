# Reference overview

## Concepts

**Grammar.** A set of productions, each with named fields.

**Production.** One node type: `Assign`, `BinOp`, an SSA instruction. It has a name, a list of fields, and optionally a class that constructs it.

**Field.** One named slot in a production, carrying a shape, a sort and a role.

**Shape.** How many values the slot holds: `ONE`, `OPT` (zero or one), `SEQ` (a list), or `UNKNOWN` when the source did not report it. Python supplies shapes from each AST class's `_field_types`, which exists from 3.13; on 3.11 and 3.12 every shape is `UNKNOWN`. Roles, identifier sorts and the queries built on them are unaffected.

**Sort.** What the slot holds: another production, a bare identifier string, or plain data.

**Role.** What the position does with what it holds: see [Roles](roles.md).

**Namespace.** Which family of names a role refers to, as a string. `def(vals)` and `def(slots)` keep a pass over SSA values away from a mutable slot even though both fields hold the same type. Python's grammar uses `VARS` for variables. The [caml-prépa example](../caml/middle.md) declares five, because OCaml keeps values, constructors, record labels, type names and type variables apart: a record with a field `x` and a variable `x` are unrelated names, and renaming the variable must leave `r.x` alone.

**Condition.** `Present(field)` or `Absent(field)`, and nothing else. A field or a scope may carry one, so a role can depend on a sibling field: `import a.b` binds `a`, while `import a.b as c` binds `c` alone.

**Trait.** A free-form label on a production, for facts no field determines: `pure`, `terminator`.

## The queries

| question | call |
| --- | --- |
| which fields have a given role? | `positions(kind, ns)` |
| which fields read a name? | `operands(ns)` |
| which fields introduce one? | `definitions(ns)` |
| which fields hold a bare identifier? | `ident_slots(ns)` |
| which fields does a traversal descend into? | `children(prod)` |
| which productions can actually appear? | `concrete(base)` |
| which productions carry a trait? | `with_trait(name)` |
| what does *this node* read? | `reads(node, ns)` |
| what does *this node* bind? | `binds(node, ns)` |
| which class builds this production? | `constructor(name)` |
| is the declaration well formed? | `check()` |
| a grammar restricted to these productions | `subset(names)` |

## Static queries and instance queries

`positions`, `operands`, `definitions` and `ident_slots` describe **every node** of a production at once. They return field names. A field whose role is conditional is reported under *both* of its roles, because both are possible somewhere.

`reads` and `binds` take **one node**, evaluate the conditions against it, and return the values in the matching slots.

Use the first to build a table; use the second when you are holding a node. If you are writing a walk that consults a static table and then re-inspects the node to decide which role applies, the instance query already does that.
