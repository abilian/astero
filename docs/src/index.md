# astero

**The middle end, without writing it.**

Parser generators took the front end fifty years ago; lexers are no longer written by hand. The middle never got the same treatment. Every compiler and every analyser still rolls its own symbol table, binder, renamer, fresh-name supply, capture-avoiding substitution and bracketing, each working out the same facts about the language to do it.

You declare which positions bind a name, which read one, and which open a scope. The passes above follow from that. For Python you declare nothing, because the grammar ships with the library.

The library ships the part that costs weeks to find out. That comprehensions stopped opening a scope in 3.12. That PEP 695 blocks are spelled `type parameter` on 3.12 and `type parameters` from 3.13. That 3.14 adds annotation blocks unless the module carries `from __future__ import annotations`. You find each one by hitting it, bisecting it, and reading a PEP.

That claim is narrower than it sounds. astero does not parse, and does not replace `ast`. CPython already declares the shape of every node, which astero reads: `Assign.targets` is `list[expr]` and `Assign.value` is `expr`, both straight from the interpreter.

`ast` cannot tell you that the first of those two introduces a name and the second does not. To `ast` they are both `expr`. That fact lives in the language reference and in the head of whoever writes the pass. astero ships it: of Python's 176 fields across 124 productions on 3.13, 138 are plain subtrees with nothing to say, while the other 38 carry a **role**. Those counts move with the language (3.11 has 163 fields and 3.15 has 183), which is why astero reads them off the interpreter. Twenty-two of them introduce a variable name.

```bash
pip install abilian-astero        # or: uv add abilian-astero
```

The distribution is called **abilian-astero**, because PyPI already had `astero`. The import name is `astero`:

```python
from astero.python import PY, VARS
```

Python 3.11 through 3.15. No runtime dependencies. Apache-2.0.

## The problem, in one example

Rename a variable throughout a module. This is the version that gets written:

```python
import ast

NEW = {"x": "y"}
SOURCE = "def f(x):\n    import os as x\n    try: pass\n    except E as x: g(x)\n    return x\n"


class Renamer(ast.NodeTransformer):
    def visit_Name(self, node):
        node.id = NEW.get(node.id, node.id)
        return node

    def visit_arg(self, node):
        node.arg = NEW.get(node.arg, node.arg)
        return node


print(ast.unparse(Renamer().visit(ast.parse(SOURCE))))
```

```
def f(y):
    import os as x          # not renamed
    try:
        pass
    except E as x:          # not renamed
        g(y)                # now reads a name nothing binds
    return y
```

Two of the four binding positions were missed. The result still parses. It means something else.

Here is the same job with astero:

```python
from astero.python.hygiene import rename
from astero.python import PY, VARS

print(ast.unparse(rename(ast.parse(SOURCE), NEW, PY, VARS)))
```

```
def f(y):
    import os as y
    try:
        pass
    except E as y:
        g(y)
    return y
```

**Sixteen identifier slots**, across fifteen productions, hold a bare variable name; **twenty-two positions** introduce one, counting the targets that hold an expression, such as `a[i]`. The sets move between releases: PEP 695 added three slots and four positions in 3.12. `rename` reaches all of them because a declaration lists them.

## Why that generalises

Renaming is the smallest visible case. The *same* fact, which fields introduce a name, is needed in several other places. Hand-writing it means several enumerations that have to agree with each other and with the language:

| what needs it | what a missed position does there |
| --- | --- |
| the scope or symbol table | a name that is never bound, so a parameter silently disappears |
| capture-avoiding substitution, in an inliner | inlining produces `[99 for 99 in xs]`, which does not parse |
| `ctx` on a rewritten tree | `b[1] += 5` compiles to JavaScript computing `NaN` where Python gives `5` |
| a test that every binding position is exercised | nothing, which is why the other three went unnoticed |

The first three are defects that shipped, in three different compilers: `**kwargs` never bound, an inliner substituting at every `Name`, and an `AugAssign` rewrite setting the context by hand. None of them crashed.

In astero they are one query, `positions(Kind.DEF, ns)`, read by four modules: `scopes`, `hygiene`, `rewriting` and `generate`. Add a binding form to the language, edit the declaration; the four follow.

**That is the shape of the library.** Structural facts are declared once and consumed many times. Names are the clearest case; the same holds for which fields a traversal must enter, which productions can appear in a tree, and how tightly each operator binds.

## What a declaration buys

You declare a **role** for each field of each production: whether it introduces a name, refers to one, or merely holds a subtree. For Python that declaration ships with the library; for your own IR it is one table, read off your dataclasses.

What reads it:

| module | what you get |
| --- | --- |
| `grammar` | which fields bind a name, which read one, which hold a bare identifier, which a traversal must enter, which productions can appear |
| `rewriting` | tree rewriting from `pattern => result` rules, with each `Name`'s `ctx` recomputed for you |
| `scopes` | the scope tree of a module, and the names each scope binds |
| `hygiene` | renaming, and substitution that does not capture |
| `emit_rules` | a code generator written as templates, bracketed from a precedence table |
| `coverage` | a test that fails when your dispatch table misses a production |

Three worked compilers ship with the docs. [TinyPy](tutorial.md) is a Python subset with two back ends. [PL/0](tutorial-pl0.md) is Wirth's textbook language, built on a tree of plain dataclasses with no relationship to `ast`. [caml-prépa](caml/index.md) is a compiler for the OCaml subset taught in French preparatory classes. It pushes hardest on the declaration, with five namespaces where Python has one and a half and binding positions that are whole patterns. It also has a reference implementation to check every answer against.

## What astero is not

- **Not a parser.** Bring your own AST. astero starts from a tree.
- **Not a code generator you run.** There is no `astero build`; nothing is generated on disk. It is a library you import; every entry point is a function call at run time.
- **Not a framework.** It does not own your pipeline, your IR, or your `main`. You can adopt one query in one function and leave everything else alone.

This is a narrower scope than compiler toolkits such as Cocktail or Eli, which generate a compiler's components from declarations ahead of time. astero answers questions about a declaration at run time, which is why adoption can be incremental.

## Examples

Each of these runs as written. The outputs in the comments are checked by `tests/a_unit/test_tutorial.py`.

### Ask the grammar for a table

```python
from astero.python import PY, VARS

PY.ident_slots(VARS)["arg"]  # ('arg',)      — every slot a renamer must reach
PY.definitions(VARS)["For"]  # ('target',)   — positions that introduce a name
PY.definitions(VARS)["FunctionDef"]  # ('name',)
```

`ident_slots(VARS)` returns the full mapping, which on Python 3.12 and later covers 15 productions holding a variable name.

### Rewrite a tree without touching `ctx`

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

ast.unparse(DESUGAR(ast.parse("b[1] += 5")))  # 'b[1] = b[1] + 5'
```

In Python's AST every `Name` and `Subscript` carries `ctx=Load()` or `ctx=Store()`. A rewrite that moves a node between positions has to update it. The rule above does not mention `ctx`: astero reads each field's role from the grammar and sets the context to match the position the node ends up in. The same rule therefore handles `x += 5` and `b[1] += 5`, where the target must become `Store` in one place and `Load` in the other.

`eliminates=` is a postcondition. If any `AugAssign` remains after the pass, it raises and will not pass a half-desugared tree downstream.

### Substitute without capturing a name

```python
from astero.python.hygiene import Fresh, substitute

body = ast.parse("[n + k for k in xs]", mode="eval").body
substitute(body, {"n": ast.parse("k", mode="eval").body}, PY, VARS, fresh=Fresh())
# [k + _t1 for _t1 in xs]
```

Replacing `n` with the expression `k` would put a free `k` inside a comprehension that binds its own `k`, silently changing what the code means. `substitute` detects the collision and, given a `Fresh` name supply, renames the comprehension's binder to `_t1` first. It also replaces only *uses* of `n`: a position that binds `n` is left alone, because substituting there produces something that is not a program.

### Write a code generator as a table

```python
from astero.emit_rules import All, Both, Emitter, OpIs


def type_of(node):
    """Your type inference. A stub, so the example runs."""
    return int if isinstance(node, ast.Constant) else None


js = Emitter(PY, typer=type_of)
js.projection("name", str)
js.projection("lit", str)
js.rule("BinOp", "{left} + {right}", All((OpIs((ast.Add,)), Both((int,)))))
js.rule("BinOp", "add({left}, {right})", OpIs((ast.Add,)))
js.rule("Name", "{id:name}")
js.rule("Constant", "{value:lit}")

js.to_text(ast.parse("1 + 2", mode="eval").body)  # '1 + 2'
js.to_text(ast.parse("a + b", mode="eval").body)  # 'add(a, b)'
```

A rule is a production name, a template, and an optional guard. Rules are tried in order and the first whose guard holds wins, so the specialised case sits above the general one. `{left}` emits that field and brackets it if the precedence table says it needs brackets.

`typer` is how the emitter asks your type inference a question; it is the only hook into host analysis.

### Fail the build when a production has no handler

```python
from functools import singledispatch

from astero.coverage import dispatch


@singledispatch
def gen(node: ast.AST) -> str:
    raise NotImplementedError


@gen.register
def _(node: ast.Assign) -> str:
    return "assign"


@gen.register
def _(node: ast.Return) -> str:
    return "return"


cover = dispatch(
    PY,
    (gen.registry,),
    bases=("stmt",),
    accounted={"desugared": {"AugAssign", "AnnAssign"}},
)

cover.explain().splitlines()[0]  # '2 of 28 productions handled'
sorted(cover.missing)[:3]  # ['Assert', 'AsyncFor', 'AsyncFunctionDef']
```

`dispatch` compares the productions your `singledispatch` registries handle against the productions the grammar declares. In a real project you would `assert not cover.missing, cover.explain()` in a test.

`accounted` names the productions you choose not to handle, with the reason as the key. A stale reason, one whose production no longer exists or has since gained a handler, shows up in `cover.absent` and `cover.redundant`; it never reaches `cover.missing`.

## Where variable names appear in Python's AST

Take one concrete job: renaming a variable throughout a Python module. You need every slot holding a bare name. On Python 3.13 there are sixteen, across fifteen productions:

```
AsyncFunctionDef.name    Global.names        Name.id            TypeVar.name
ClassDef.name            MatchAs.name        Nonlocal.names     TypeVarTuple.name
ExceptHandler.name       MatchMapping.rest   ParamSpec.name     alias.name, alias.asname
FunctionDef.name         MatchStar.name                         arg.arg
```

Three observations a hand-written list tends to miss:

- **The list is version-dependent.** Python 3.11 has twelve of these. `ParamSpec`, `TypeVar` and `TypeVarTuple` arrived with PEP 695 in 3.12. Code that hard-codes the list is correct for one interpreter.
- **The unobvious entries** are the ones omitted. `ExceptHandler.name` is the `e` in `except E as e`. `alias.asname` is the `y` in `import x as y`. `Global.names` holds a list of names. The four `Match*` patterns bind too.
- **Namespaces matter.** `ident_slots()` without one returns two more productions, `Attribute.attr` and `keyword.arg`. Those are identifiers, but renaming them changes `x.foo` into a different attribute and `f(key=1)` into a different call. Passing `VARS` asks the narrower question.

`PY.ident_slots(VARS)` computes the answer from the interpreter you are running on, so all three problems go away together.

## How a grammar is declared

A grammar is a set of **productions**, each with named **fields**. Every field carries three things:

- a **shape**: `ONE`, `OPT` or `SEQ`, i.e. whether the slot holds one node, an optional node, or a list;
- a **sort**: what the slot holds, another production, a bare identifier, or plain data;
- a **role**: what the position *does* with what it holds.

Roles have no equivalent in ASDL, the notation Python's own AST definition is written in. Every query above is computed from them:

```
child       structural containment; a traversal descends into it
attr        plain data; never traversed
def(ns)     introduces a name in namespace `ns`
use(ns)     refers to a name in `ns`
defuse(ns)  both, for read-modify-write positions
del(ns)     removes a name
declare(ns) `global` and `nonlocal`: names a binding that lives elsewhere
```

Two rules govern how roles are written, both explained in [Roles](reference/roles.md). A role belongs to the *parent's field*, describing a position the child node occupies. **Namespaces** then distinguish positions that hold the same type but mean different things.

You can declare a grammar three ways: `astero.python.build()` if your AST subclasses Python's, `grammar.from_dataclasses()` if your IR is annotated dataclasses, or `GrammarBuilder` by hand. All three are in the [API reference](api/grammar.md).

## How the derivations are checked

Each derivation is compared against an independent source of truth over the Python standard library:

| derived | compared against | result |
| --- | --- | --- |
| `ctx` values | what CPython's parser produces | every position in the standard library, no disagreements |
| scopes and their names | CPython's `symtable` module | 99.98% of blocks agree (77,900 of 77,915 on 3.12) |
| emitted source | reparsing the emitted text | all 1,797 modules and all 2,266,043 expressions |
| operand positions of an SSA IR | that compiler's own declaration | exact match |
| names and scopes for a language that is not Python | the real `ocaml`, over `examples/ocaml`'s corpus | all 60 programmes print what OCaml prints |

These are integration tests, run on Python 3.11 through 3.15. The exact counts depend on which standard library you measure, so the tests hold the ratio. A regression fails; an improvement does not have to be chased.

## Where to go next

- **[Getting started](getting-started.md)**: install it and run three queries against real code.
- **[Tutorial](tutorial.md)**: build a working compiler for a Python subset with two back ends, in 357 lines of which 266 are code: the compiler is 189, each back end under 100.
- **[caml-prépa](caml/index.md)**: a larger worked example, for a language with five namespaces and pattern binders, checked against the real `ocaml`.
- **[User guide](guides/user-guide.md)**: every module, its API, and when to use it.
- **[Adopting astero](guides/adopting.md)**: fitting it into a compiler you already have.
