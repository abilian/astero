# A compiler for PL/0

The [TinyPy tutorial](tutorial.md) compiles a subset of Python. That leaves one question open: how much of astero assumed a Python syntax tree?

This page answers it by compiling **PL/0**, Niklaus Wirth's teaching language and the one most compiler courses build first. PL/0 is not Python and shares nothing with it: constants, variables, nested parameterless procedures, `begin`/`end`, `if`, `while`, `call`, and integer arithmetic.

The code is in `examples/pl0/`: 972 lines, 637 of them code, including a parser, a P-machine and an interpreter. The three files that talk to astero, `grammar.py`, `analyze.py` and `codegen.py`, are 313 lines of that. It differs from TinyPy in these ways:

| | TinyPy | PL/0 |
| --- | --- | --- |
| the tree | Python's `ast` | plain dataclasses |
| the grammar | `PY.subset(...)` | `from_dataclasses(...)` |
| scope rules | `astero.python.SCOPES` | one `Scope` written here |
| binding | `x = 1` introduces `x` | `var x` introduces it; `x := 1` writes to it |
| namespaces | variables | variables **and** procedures |
| the oracle | CPython | a tree-walking interpreter |

---

## 1. Bring a tree

astero does not parse. `examples/pl0/parser.py` is an ordinary recursive-descent parser for Wirth's grammar, and `syntax.py` holds what it builds:

```python
@dataclass
class Assign(Stmt):
    name: Ident
    value: Expr
```

Nothing in either file imports astero. `Ident` is the one piece of foresight: `str` under another name.

```python
Ident = str
```

That is enough for the declaration to separate fields holding a *name* from fields holding data that happens to be a string, such as `BinOp.op`.

## 2. Declare it

`from_dataclasses` reads the field names, sorts and shapes off the annotations. Only the roles are written:

```python
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
```

Six entries. Every field not listed gets a default: plain data becomes `attr`; anything else becomes `child`, which keeps traversal complete.

**`Assign.name` is a use.** In Python `x = 1` introduces `x`; in PL/0 `var x` introduces it and `x := 1` writes to something already declared. Ask the two grammars the same question and they answer differently, because the declarations differ and for no other reason:

```
PY.definitions(VARS)["Assign"]    ('targets',)
PL0.definitions(VARS)             {'Const': ('name',), 'Var': ('name',)}
PL0.operands(VARS)                {'Name': ('name',), 'Assign': ('name',)}
```

**Two namespaces.** A procedure name and a variable name are both identifiers. `defines(PROCS)` keeps them apart, so a pass over variables never renames a `call`, and `PL0.definitions(VARS)` never mentions `Procedure`.

## 3. Declare the scopes

PL/0's entire scope structure is one entry:

```python
SCOPES: dict[str, tuple[Scope, ...]] = {
    "Procedure": (Scope("procedure", inside=("block",), name_field="name"),),
}
```

A procedure's *name* belongs to the block that encloses it; its *block* is a new scope. That one distinction is what makes `call` resolve outwards and a local `var` shadow an outer one. `scope_tree` then answers for any program:

```
program   main             {n, r}
  procedure o                {k}
    procedure i                {}
```

## 4. Ask the grammar, not a list of field names

Slot allocation needs the declarations of a block, in source order. Nothing below names `Const`, `Var` or `Procedure`:

```python
def declarations(block: syntax.Block, ns: str) -> list[syntax.Node]:
    """The nodes in `block` that declare a name in `ns`, in source order.

    Derived twice over: `children` says which fields of a `Block` hold
    nodes, and `names_bound_by` says which of those nodes declare anything
    in this namespace. A procedure declares in `procs` and not in `vars`, so
    asking for `vars` skips it without a special case.
    """
    out: list[syntax.Node] = []
    for slot in PL0.children("Block"):
        value = getattr(block, slot.name, None)
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, syntax.Node) and names_bound_by(item, PL0, ns):
                out.append(item)
    return out
```

Called with `VARS` it returns the constants and variables; called with `PROCS`, the procedures. The code is the same, and neither case lists field names.

## 5. Emit P-code

The target is Wirth's P-machine: a stack, with one frame per active procedure. A frame begins with three words, the static link, the dynamic link and the return address. `LOD 2 4` means "the variable at offset 4, two levels out", which is why the language needs a scope tree at all.

Emission is post-order, so `levels=None` and the operator goes last:

```python
    p.rule("Number", "LIT {value:lit}")
    p.rule("Name", "{name:load}")
    p.rule("Neg", "{value}\nOPR neg")
    p.rule("BinOp", "{left}\n{right}\n{op:op}")
    p.rule("Odd", "{value}\nOPR odd")
    p.rule("Compare", "{left}\n{right}\n{op:rel}")
```

Control flow is a rule like the others, because `{&label}` names a label unique to its node:

```python
    p.rule("If", "{cond}\nJPC {&done}\n{then}\n{&done}:")
    p.rule("While", "{&top}:\n{cond}\nJPC {&done}\n{body}\nJMP {&top}\n{&done}:")
```

### Where a guard cannot reach

`Name` should compile to `LIT 10` when the name is a constant and `LOD 1 3` when it is a variable. That is two rules under a guard, which this vocabulary cannot express. `Is`, `Const`, `OpIs` and `Has` ask about a node's *type and shape*; constant-or-variable is a fact about the *scopes*.

So the resolution happens in a projection, which is host code by design:

```python
    def load(name: str) -> str:
        kind, *rest = frame.lookup(name)
        if kind == "const":
            return f"LIT {rest[0]}"
        return f"LOD {rest[0]} {rest[1]}"
```

This is the guard vocabulary's edge, in a place small enough to see. Widening the guards to reach it would let a rule table call arbitrary code, at which point it stops being a table.

## 6. Gate it against the class hierarchy

```python
def coverage() -> Coverage:
    """Every statement and expression PL/0 has must have a rule.

    `concrete` reads the class hierarchy in `syntax.py`, so adding a
    production there and forgetting its rule fails here by name.
    """
    handled = emitter(Frame(name="probe", level=0)).covered()
    expected = PL0.concrete("Stmt") | PL0.concrete("Expr") | PL0.concrete("Cond")
    return Coverage(handled=handled, expected=expected)
```

`concrete("Stmt")` works because `syntax.py` has abstract bases and `from_dataclasses` was given them. Add a statement class without its rule: the test fails, naming it.

## 7. Check it against something

TinyPy could be checked against CPython. PL/0 has no reference implementation to compare against, so the oracle has to be built: `interpret.py` walks the tree and runs it directly, with an environment chain where the compiler uses static links. It shares the parser with the compiler and nothing else.

```
squares    [1, 4, 9, 16, 25, 36, 49, 64, 81, 100]
nested     [210]
recursion  [720]
gcd        [6]
shadowing  [99, 1]
```

**This is a weaker oracle than CPython.** Two implementations by one author can share a misreading of the language. It catches disagreement between the compiler and a direct reading of the tree, which is most of what goes wrong, and it cannot catch both being wrong the same way.

## What writing this found

**`astero.scopes` was Python-only.** Silently: it iterated fields with `ast.iter_fields` and tested nodes with `isinstance(node, ast.AST)`, so a tree of dataclasses did not raise: it produced a root block with no children and no bound names. Every query above returned an empty answer that looked like a valid one.

The fix reads a node's fields from the grammar instead, which is the information the grammar was already carrying. Two checks stand behind it now: the field order it produces matches `ast.iter_fields` for every node of the standard library, so the Python oracles are unaffected; and `test_pl0.py::test_scopes_over_a_non_python_grammar` checks the scope tree for a nested PL/0 program, the test that would have caught it.

That is the argument for a second worked language. TinyPy exercised the same code every day and could not find this, because a Python subset is still Python.
