# Roles

A **role** says what a field position does with the value it holds. Shapes and sorts describe the *structure* of a tree; roles describe its meaning for names. Every query in astero is computed from them.

| role | meaning |
| --- | --- |
| `child` | structural containment; a traversal descends into it |
| `attr` | plain data; never traversed |
| `def(ns)` | introduces a name in namespace `ns` |
| `use(ns)` | refers to a name in `ns` |
| `defuse(ns)` | both, for read-modify-write positions |
| `del(ns)` | removes a name |
| `declare(ns)` | `global` and `nonlocal`: names a binding that lives elsewhere |

ASDL, the formalism Python's own AST definition is written in, has the structure but not the roles. Adding them lets the declaration answer which fields bind a name.

## A role belongs to the parent's field

This is the decision that makes `ctx` derivable. Understand it before you declare a grammar of your own.

In Python's AST, a `Name` node carries `ctx=Store()` or `ctx=Load()`. Whether a name is being written or read is a property of *where the name sits*. `x` in `x = 1` and `x` in `y = x` are the same node type in two different positions.

So astero puts the role on the position:

```
Assign.targets   def(vars)
Assign.value     use(vars)
BinOp.left       use(vars)
BinOp.right      use(vars)
```

`ctx` then leaves the declaration entirely. It becomes something astero computes when it builds a tree, from the field the node is going into.

The practical consequence is that a rewrite rule cannot mention a context, so it cannot set the wrong one. `b[1] += 5` and `x += 5` go through one rule even though the target must end up `Store` in one place and `Load` in the other.

## Namespaces separate positions that look alike

A **namespace** is a string naming a family of names. Every name-related role carries one; so does every query that asks about names.

It exists because two fields can hold the same type and mean unrelated things.

**In an SSA IR**, a value and a mutable stack slot may both be `Value`-typed fields. Declaring them `def(vals)` and `def(slots)` means a pass sweeping over values never reaches a slot, even though nothing in the type distinguishes them.

**In Python**, `Name.id` and `Attribute.attr` are both plain identifier strings. `ident_slots()` with no namespace reports both, and a renamer built on that list rewrites `x.foo` into a different attribute when you rename `x`. `ident_slots(VARS)` asks the narrower question and reports only variables.

The general rule when declaring a grammar is this: if two positions would be confused by a pass that only knows types, give them different namespaces.

## A field may carry a condition

A field's role can depend on another field of the same production:

```python
"target": ((defines(VALS), Present("declare")),
           (uses(VALS),    Absent("declare"))),
```

One slot, two roles, decided by a sibling: a declaring assignment defines its target, a re-assignment reads it.

`Field.applies(node)` evaluates the condition for a given node. The instance queries `reads` and `binds` do it for you. Static queries cannot. They describe every node of a production at once, so they report the field under both roles.

**Two words only.** The condition language is `Present(field)` and `Absent(field)`; a condition cannot be a callable. One that could run arbitrary code would put host logic back inside the declaration, which would then stop being readable as data. The limit is real: PEP 649 annotation scopes depend on a block's *contents*, which these two words cannot describe.

## What roles do not say

Roles are structural. They say nothing about types, effects, costs, or whether an operand is provably constant. Those are properties of a *program*, not of its grammar, so `emit_rules` guards stop at the same line.
