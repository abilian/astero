# Getting started

This page runs four things against real Python code. Each snippet is complete: paste it into a file and run it.

## Install

```bash
pip install abilian-astero        # or: uv add abilian-astero
```

The distribution is called **abilian-astero**, because PyPI already had `astero`. The import name is `astero`:

```python
from astero.python import PY, VARS
```

Python 3.11 through 3.15. No runtime dependencies.

## Two names you will import constantly

```python
from astero.python import PY, VARS
```

`PY` is Python's grammar, declared once and shipped with the library. It knows every production in the `ast` module of the interpreter you are running on.

`VARS` is a **namespace**: the string `"vars"`. Most queries take one, because a grammar can track several independent families of names that would otherwise be confused. Python's grammar declares two, both exported by `astero.python`:

- `VARS` (`"vars"`) for variables;
- `ATTRS` (`"attrs"`) for attribute names and keyword-argument names.

Passing a namespace is how you say which one you mean.

## 1. Ask where variable names live

```python
from astero.python import PY, VARS

slots = PY.ident_slots(VARS)
print(len(slots))  # 15 on Python 3.12+, 12 on 3.11
print(slots["FunctionDef"])  # ('name',)
print(slots["arg"])  # ('arg',)
print(slots["alias"])  # ('name', 'asname')
```

`ident_slots` returns `{production name: (field names,)}` for every position that holds a bare identifier string. That is exactly the table a renamer needs to walk.

Before you use it, know two things:

**The namespace changes the answer.** Called with no argument, `PY.ident_slots()` also includes `Attribute.attr` and `keyword.arg` (17 productions on 3.12 and later, 14 on 3.11). Those hold identifiers, but they name attributes and keyword arguments. A renamer built on the unnamespaced list also rewrites the `.foo` in `x.foo`.

**The answer depends on the interpreter.** Python 3.12 added `TypeVar`, `ParamSpec` and `TypeVarTuple` (PEP 695). Because `PY` is built from the running `ast` module, the query reports what actually exists for the interpreter you are on.

## 2. Rewrite a tree

```python
import ast
from astero.python import Pass, rules
from astero.python import PY

DESUGAR = Pass(
    "desugar",
    rules("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"),
    eliminates=(ast.AugAssign,),
    grammar=PY,
)

tree = DESUGAR(ast.parse("b[1] += 5"))
print(ast.unparse(tree))  # b[1] = b[1] + 5
```

A rule is `pattern => result`. Names beginning with `_` are pattern variables: `_t`, `_o` and `_v` capture the target, the operator and the value. The right-hand side puts them where it wants them. A `Pass` applies its rules bottom-up over the whole tree.

Note what the rule does *not* say. Python's AST tags each `Name` and `Subscript` with `ctx=Load()` or `ctx=Store()` according to the position it sits in, so a hand-written version of this rewrite has to set `Store` on the assignment target and `Load` on the copy inside the `BinOp`. astero reads the roles of `Assign.targets` and `BinOp.left` from the grammar and sets both for you, which is why the same rule handles `x += 5` and `b[1] += 5`.

`eliminates=(ast.AugAssign,)` is a postcondition checked after the pass runs. If any `AugAssign` is still in the tree, the pass raises before handing a half-desugared tree to the next stage.

## 3. Ask what a scope binds

```python
import ast
from astero.python import PY, VARS, BINDING_SCOPES
from astero.scopes import scope_tree

tree = ast.parse("def f(a, *rest, **kw):\n    x = 1\n    return x\n")


def show(block, depth=0):
    print(" " * depth, block.kind, block.name, sorted(block.bound))
    for child in block.children:
        show(child, depth + 2)


show(scope_tree(tree, PY, BINDING_SCOPES, VARS))
```

```
 module top ['f']
   function f ['a', 'kw', 'rest', 'x']
```

`scope_tree` returns a `Block`: a `kind`, a `name`, the set of names it `bound`, and its `children`. `rest` and `kw` appear because both are `arg` nodes and `arg.arg` is a binding position in the grammar; nothing enumerated `args`, `vararg` and `kwarg` by hand.

**Two scope tables.** `scope_tree` takes one explicitly, because they answer different questions.

- `SCOPES` describes what CPython's `symtable` module calls a block.
- `BINDING_SCOPES` describes what a name binds *over*.

They were the same thing until Python 3.12, when PEP 709 inlined comprehensions. A list comprehension no longer opens a `symtable` block. Its iteration variable is still local to it. Pass the table that matches your question: `SCOPES` when you compare against `symtable`, `BINDING_SCOPES` when you decide where a name is visible.

The derivation is checked against `symtable` itself over the standard library, on every supported interpreter: 99.98% of blocks agree.

## 4. Check that you handle every production

```python
from astero.coverage import Coverage
from astero.python import PY

cover = Coverage(handled=frozenset({"Assign", "Return"}), expected=PY.concrete("stmt"))
print(cover.missing)  # every statement you have no handler for
print(cover.explain())  # the same, formatted for an assertion message
```

`concrete(base)` lists the productions of a sort that can actually appear in a tree, so this compares your dispatch table against the language. In a real project you would build the `handled` set from your `singledispatch` registry with `coverage.dispatch`, or read it out of a `match` statement with `coverage.match_arms`, and assert `not cover.missing` in a test.

## Where to go next

- The **[tutorial](tutorial.md)** builds a complete compiler for a Python subset with two back ends, and marks the points where you have to write code yourself.
- The **[user guide](guides/user-guide.md)** covers each module's API in full.
- **[Adopting astero](guides/adopting.md)** is the path to follow if you already have a compiler and want to introduce astero into it a piece at a time.
- **[caml-prépa](caml/index.md)** is the larger worked example: a compiler for an OCaml subset, with five namespaces, binding positions that are whole patterns, and the real `ocaml` as its oracle.
