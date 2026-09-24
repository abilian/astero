# <img src="https://astero.lab.abilian.com/assets/astero.svg" alt="astero" width="320">

**The middle end, without writing it.**

Parser generators took the front end fifty years ago; lexers are no longer written by hand. The middle never got the same treatment. Every compiler and every analyser still rolls its own symbol table, binder, renamer, fresh-name supply, capture-avoiding substitution and bracketing, each working out the same facts about the language to do it.

You declare which positions bind a name, which read one, and which open a scope. The passes above follow from that. For Python you declare nothing, because the grammar ships with the library.

The library ships the part that costs weeks to find out. That comprehensions stopped opening a scope in 3.12. That PEP 695 blocks are spelled `type parameter` on 3.12 and `type parameters` from 3.13. That 3.14 adds annotation blocks unless the module carries `from __future__ import annotations`. You find each one by hitting it, bisecting it, and reading a PEP.

```bash
pip install abilian-astero        # or: uv add abilian-astero
```

The distribution is called **abilian-astero**, because PyPI already had `astero`. The import name is `astero`:

```python
from astero.python import PY, VARS
```

Python 3.11 through 3.15. No runtime dependencies. Apache-2.0.

## The problem it solves

Twenty-two positions in Python bind a variable name (eighteen on 3.11, before PEP 695 added four). Here are four of them:

```python
def f(x):                      # a parameter
    import os as x             # an import alias
    try:
        pass
    except E as x:             # an exception name
        pass
    return [x for x in xs]     # a comprehension target
```

A renamer written with `ast.NodeTransformer` and a `visit_Name` method reaches one. That is not a hypothetical: it is the shape of a defect found in three separate compilers. None of the three crashed. One never bound `**kwargs`, one inlined a call so that `[99 for 99 in xs]` came out, one set an assignment context by hand and produced JavaScript that computed `NaN` where Python gave `5`.

With astero the list is a query, which serves every pass that needs it:

```python
from astero.python.hygiene import rename
from astero.python import PY, VARS

rename(tree, {"x": "y"}, PY, VARS)      # reaches all of them
```

Python releases change the set: PEP 695 added four positions in 3.12. Code written against the query follows the language without being edited.

## What it is not

astero does not parse, and does not replace `ast`. CPython already declares the shape of every node, which astero reads: `Assign.targets` is `list[expr]` and `Assign.value` is `expr`, both straight from the interpreter.

`ast` cannot tell you that the first of those two introduces a name and the second does not. To `ast` they are both `expr`. That fact lives in the language reference and in the head of whoever writes the pass. astero ships it: of Python's 176 fields across 124 productions on 3.13, 138 are plain subtrees with nothing to say, while the other 38 carry a **role**. Those counts move with the language (3.11 has 163 fields and 3.15 has 183), which is why astero reads them off the interpreter.

## What you get

Declare a **role** for each field of each production: whether it introduces a name, refers to one, or holds a subtree. Six modules read that declaration.

| module | what it gives you |
| --- | --- |
| `grammar` | which fields bind a name, which read one, which hold a bare identifier, which a traversal must enter, which productions can appear |
| `rewriting` | tree rewriting from `pattern => result` rules, with every `Name`'s context recomputed for you |
| `scopes` | the scope tree of a module, and the names each scope binds |
| `hygiene` | renaming, and substitution that cannot capture a name |
| `emit_rules` | a code generator written as templates, with brackets derived from a precedence table |
| `coverage` | a test that fails when your dispatch table misses a production |

Add a binding form to your language and edit the declaration: all six follow.

### Rewriting, without touching contexts

A rule is one string with `=>` between pattern and replacement:

```python
from astero.python import Pass, rules

fold = Pass("fold", rules("""
    _x + 0 => _x
    _x * 1 => _x
"""))
```

Identifiers spelled `_name` are metavariables, `_` matches anything without binding, and `*_xs` splices the rest of a list. Rules never mention `ctx` or source positions, because both are recomputed from the shape of the result. That is what makes the `AugAssign` defect above impossible to write.

### Your own IR, as well as Python's

A grammar carries each production's constructor, so a rewrite builds your node classes. If your AST is generated from CPython's, the whole declaration is one line:

```python
PRESCRYPT = astero.python.build(module=prescrypt.front.ast.ast, name="prescrypt")
```

If your IR is annotated dataclasses, `from_dataclasses` reads the fields and sorts off the annotations, leaving you only the roles to write. The [PL/0 tutorial](https://astero.lab.abilian.com/tutorial-pl0/) builds a complete compiler that way, for a language with no relationship to Python.

## Why you can rely on it

Every derivation is compared against an independent source of truth, over the whole Python standard library, on Python 3.11 through 3.15.

| derived | compared against | result |
| --- | --- | --- |
| assignment contexts | what CPython's parser produces | every position in the standard library, no disagreements |
| scopes and their names | CPython's `symtable` | 99.98% of blocks agree |
| emitted source | reparsing the emitted text | 1,797 modules, 2,266,043 expressions |
| operand positions of an SSA IR | that compiler's own declaration | exact match |

For assignment contexts that is ten authored role entries reconstructing all 1,457,931 positions across the 1,761 files of the 3.13 standard library. The tests hold the ratio as measured. A regression fails; an improvement does not have to be chased.

The rewrite engine was first validated by reimplementing all six of [latexify_py](https://github.com/google/latexify_py)'s tree transformations as rule sets. Differential testing against the originals found 121 output differences, each of them a latent bug in the hand-written version.

Three compilers are built on it: a Python-to-C compiler, a Python-to-WebAssembly compiler, and a Python-to-JavaScript transpiler.

## What astero is not

- **Not a parser.** Bring your own AST. astero starts from a tree.
- **Not a code generator you run.** Nothing is written to disk; there is no build step. Every entry point is a function call at run time.
- **Not a framework.** It does not own your pipeline, your IR, or your `main`. Adopt one query in one function and leave the rest alone.

Lowering and cost models stay yours. astero answers questions about a declaration; it does not decide what your compiler should do with the answers.

## Documentation

- **[Getting started](https://astero.lab.abilian.com/getting-started/)**: install it and run three queries against real code.
- **[TinyPy tutorial](https://astero.lab.abilian.com/tutorial/)**: a working compiler for a Python subset with two back ends, in 357 lines of which 266 are code: the compiler is 189, each back end under 100.
- **[PL/0 tutorial](https://astero.lab.abilian.com/tutorial-pl0/)**: the same, for a language that is not Python.
- **[User guide](https://astero.lab.abilian.com/guides/user-guide/)**: every module, its API, and when to reach for it.
- **[Adopting astero](https://astero.lab.abilian.com/guides/adopting/)**: fitting it into a compiler you already have.
- **[API reference](https://astero.lab.abilian.com/api/grammar/)**: generated from the source.

## Status

Version 0.2.x. The API may still change between minor versions; the changelog says what moved. 0.2.0 split the package by language: everything Python-specific is under `astero.python`, with no shims. Every derivation is checked against CPython on five interpreters. Three compilers are built on it.

## Development

```bash
make test     # pytest
make lint     # ruff, ruff format, ty, pyrefly, zuban, mypy
make docs     # build the documentation site
```

This code is version-sensitive, so a green run on one interpreter says little about the others. `nox` runs the suite on each:

```bash
nox -s tests            # 3.11 through 3.15
nox -s check            # everything `make lint` runs
```

Contributions are welcome. `docs/src/guides/developer-guide.md` describes how the library is organised and what a new derivation has to prove before it lands.
