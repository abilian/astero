# caml-prépa

caml-prépa is a compiler for the OCaml subset taught in French preparatory classes: `let rec`, pattern matching, lists, arrays, records, sum types, references, loops, exceptions, and `Printf`. It runs your programme, tells you the types it inferred, shows you which definition each name refers to, and turns the programme into Python.

It is laid out the way a compiler course lays one out: a `front` end that turns text into a tree, a `middle` end that works out what the tree means, and two `back` ends that run it. It is also the largest worked example of [astero](https://astero.lab.abilian.com/), which derives its name resolution from a short declaration; [the last part of this file](#for-compiler-writers) is about that.

## Documentation

The documentation is a site in two editions, English and French, at <https://caml-prepa.lab.abilian.com/>. Its pages are the playground itself, a getting-started guide, a tour of the language, a guide to the playground, a reference card, [the specification](docs/en/src/language/specification.md) and a four-part tutorial on how the compiler works.

To work on it:

```sh
make -C docs serve                # one edition, rebuilt as you save
make -C docs serve EDITION=en     # the English one
make -C docs preview              # both editions, as deployed
make -C docs                      # build both, into docs/site/
```

`serve` shows one edition at its own root, so the language selector hides itself; `preview` shows the site as deployed. From `examples/`, `make ocaml-docs`, `ocaml-docs-serve` and `ocaml-docs-preview` do the same.

The reference card's operators, keywords and standard library are generated from the compiler when the site is built. So are the playground's strings in each language.

## The playground

```sh
make -C .. web-serve
```

Then open <http://localhost:8000/>. The compiler runs in the browser, under [Pyodide](https://pyodide.org), and shows six views of the programme beside its source:

| view | what it answers |
| --- | --- |
| **Run** | what does it print, and do both back ends agree? |
| **Types** | what type did each definition get? |
| **Names** | which scope does each name belong to? |
| **Python** | what does it compile to? |
| **Read back** | how did the compiler read what I wrote? |
| **Step** | what happens, one evaluation at a time, forwards and backwards? |

It is static files and one zip, so any host will serve it. `web/README.md` has the details.

## The command line

Run these from this directory, with `uv run` in front if the workspace environment is not active:

```sh
$ python -m ocaml corpus/fact.ml
120
120
120

$ python -m ocaml --types corpus/tree.ml
val insert : 'a -> 'a tree -> 'a tree
val height : 'a tree -> int
val min_elt : 'a tree -> 'a
val to_list : 'a tree -> 'a list
val summarise : int list -> stats
```

`--run` (the default), `--types`, `--names`, `--python` and `--printed` are the playground's first five views. A programme that does not compile prints why on standard error; the command then exits non-zero.

## From Python

```python
from ocaml.front.parser import parse
from ocaml.middle.infer import signature
from ocaml.back.interpret import run_source
from ocaml.back.compile import compile_source

source = "let rec fact n = if n <= 1 then 1 else n * fact (n - 1)"
signature(parse(source))        # ["val fact : int -> int"]
compile_source(source)          # the Python it emits
run_source(source)              # the top-level scope, after running it
```

`ocaml.pipeline.analyse(source)` runs every stage and returns what each produced; the command line and the playground are both built on it.

## The language

[The specification](docs/en/src/language/specification.md) defines it: lexical structure, the grammar, the precedence table, names, typing, evaluation, the standard library, and every difference from OCaml with the reason for it and the way out.

The subset is chosen by one test: does a first- or second-year programme use it? Modules, functors, objects, GADTs, labelled arguments and polymorphic variants fail it. The compiler is not an OCaml implementation: the specification says where it knowingly differs.

## The corpus

`corpus/` holds sixty programmes, each beside the output it prints (`.expected`) and the signature it infers (`.signature`):

- ten that cover the language, and eight that cover the syllabus one chapter at a time, written in French;
- twenty-three in `corpus/simonet/`, written from the exercise series Vincent Simonet set at the Lycée Janson-de-Sailly;
- nineteen in `corpus/grimaud/`, copied under the GPL-3.0 from the solutions published with the textbook *Informatique MPI*, each file naming its source and listing any change.

Each subdirectory's `README.md` gives the sources. Every construct of the grammar appears in at least one programme. A test fails otherwise, so a construct nothing writes does not belong in the subset.

## How it is checked

`uv run pytest` runs the suite. Each stage is compared against something that is not itself:

| stage | checked against |
| --- | --- |
| parsing | the tree printed and parsed again, which must give the same tree |
| names | every corpus programme resolves; scope trees compared by shape |
| types | `ocamlc -i`, signature by signature |
| running | the real `ocaml`, output compared |
| compiling | the interpreter, over the same runtime |

The two rows that need OCaml skip without it; `brew install ocaml` or `opam switch create 5.2.0` turns them on. With OCaml 5.5.0, all sixty programmes print the same under `ocaml` as under both back ends, and `ocamlc -i` infers the same signatures line for line.

Still owed: checking that `ocamlc` *rejects* what this compiler rejects. Only acceptance is compared today.

## Layout

```
pyproject.toml     a workspace member, with its own dependencies and pytest config
ruff.toml          its own lint waivers, extending the repository's
corpus/            the sixty programmes, with their output and their signatures
docs/              the documentation site, in two editions
tests/             the suite
web/               the playground
src/ocaml/
  syntax.py        the tree, which all three ends speak
  pipeline.py      every stage in one call
  __main__.py      the command line
  oracle.py        the real `ocaml` and `ocamlc`, when installed
  front/           text in, a tree out
    lexer.py       tokens; nested comments; `'a'` against `'a`
    peg.py         a packrat PEG engine
    parser.py      the grammar, as combinators over it
    emit.py        the tree back to source, which is the parser's check
    formats.py     `Printf` format strings, for the checker and the runtime
  middle/          what the tree means
    grammar.py     the astero declaration: roles, namespaces, scopes
    analyze.py     names and scopes, derived from it
    unify.py       types, and unification
    prelude.py     what a programme may use without defining it, with types
    infer.py       type inference, one rule per construct
  back/            two of them, over one runtime
    runtime.py     values and the standard library, shared by both
    interpret.py   walk the tree
    compile.py     emit Python
    patterns.py    a pattern as a test and a list of bindings
    pyast.py       building Python `ast` nodes, tersely
    stepper.py     a run recorded evaluation by evaluation, for the Step view
```

`syntax.py` sits above the three because all three use it. **The middle end does not import the back end**: which names are in scope is decided before anything runs, so it lives in `middle/prelude.py`. A test holds the runtime's values and the prelude's types to the same set of names.

The sources are a package under `src/`. A directory of loose modules on `sys.path` shadows any standard module it happens to name. This one named three, `syntax`, `parser` and `types`, which broke `dataclasses` for everything imported after it. The suite now checks that no module here shares a name with `sys.stdlib_module_names`.

## Design notes

**The parser engine is written here.** PEG suits OCaml: its syntax is full of forms that extend as far right as they can (`let ... in`, `fun`, `match` arms, the dangling `else`), and a greedy, ordered grammar reads all of them correctly with no precedence declarations. The engine is small, and keeps the example free of dependencies. If it grows much further, `lark` is the one to take.

**One runtime, two back ends.** The interpreter and the compiled Python call the same functions in `back/runtime.py`, over the same value representation. A disagreement between them is therefore a defect in one of them. The interpreter curries every function and the compiler emits `def f(x, y)` for `let f x y`, so every higher-order function in the runtime calls through `runtime.apply`, which asks the callee how many arguments it takes.

**What the compiler does not do yet.** An or-pattern is expanded into one case per alternative, which grows with nested `|`; a decision tree is the upgrade, which needs the exhaustiveness check the specification defers. Comparisons and `/` go through `runtime.BINARY_OPS` even where the operands are known to be `int`; using the inferred types to emit Python's own operators is the first optimisation available.

**Stepping records a run.** `back/stepper.py` keeps every evaluation the interpreter performs, so going backwards is an index into a list. The interpreter calls one module-level hook, `interpret.watching`, when it is set; an ordinary run pays one comparison per node for it. Nodes carry a source span, filled in by `peg.act` for whatever a parser action builds; it is excluded from comparison and from `repr`. `grammar.py` names its type as data so that no traversal descends into it. The compiled Python is stepped with `sys.settrace`. The two back ends are lined up on how much each has printed.

---

## For compiler writers

This example exists to exercise [astero](https://astero.lab.abilian.com/) on a language that is not Python.

`middle/grammar.py` is the whole declaration: sixteen roles, five namespaces and five scope layers. Everything the compiler asks about names is a query against it, and `middle/analyze.py` names no construct and lists no binding field.

- **Five namespaces**, where the PL/0 example has two. `exception E` and `type t = E` both declare a constructor, and OCaml lets the later hide the earlier, so both are `def(cons)` and hiding needs no case anywhere.
- **A pattern is a tree, and every variable in it binds.** The role sits on the leaf, `PVar.name` is `def(vals)`, and the scope layer lists the pattern field as evaluated inside. Python needs `astero.scopes.target_nodes` to know its own destructuring shapes; this needed no library change.
- **Four dispatches are gated by `astero.coverage`**, which reads their `match` arms back out of the source and compares them with the grammar: the printer, the interpreter, the checker and the compiler. Add a construct and forget one of them: that one fails by name.
- **`astero.python.emit`** renders the compiled Python, and **`astero.python.hygiene.all_names`** seeds the names a generated temporary must avoid.

| | PL/0 | caml-prépa |
| --- | --- | --- |
| namespaces | 2 | 5, one shared by two kinds of declaration |
| binding positions | one identifier field per construct | every variable of a pattern tree |
| conditional scopes | none | `Present("params")`, on `Binding` |
| nested scopes per construct | one | `Binding`, `LetIn`, `Fun` and `Case` nest |
| types | none | Hindley-Milner, which astero does not help with |
| the oracle | its own interpreter | `ocaml` and `ocamlc`, when installed |

**What astero does not derive: types.** `unify.py`, `prelude.py` and `infer.py` are the largest part of the compiler and nothing derives any of them. Unification, levels, the value restriction, abbreviations and the nominal tables are all written by hand. astero's plan names type inference as the one front-end job it does not do. This is what that costs.

### Two residuals

Both were found by running it. Both are limits of the declaration: the type checker and the back ends get these cases right; only the scope trees are approximate.

**`let` and `let rec` are the same to the scope model.** In OCaml a plain `let p = e in b` evaluates `e` in the scope *around* the `let`, so `let x = x + 1 in ...` reads the outer `x`. Saying that needs the binding's pattern routed inside the new scope and its value routed outside. Both sit in `LetIn.bindings`, and `Scope.inside` names a field of the construct that opens the scope, so it puts both in or both out. A condition does not reach it either: `Present("recursive")` chooses among `LetIn`'s fields, while the two that have to differ belong to a grandchild. The first draft of the specification proposed that condition; writing the resolver showed it changes only whether the names also leak outward. The candidate fixes:

1. Parallel fields on `LetIn` (`patterns`, `values`), expressible today, with a worse tree.
2. Dotted paths in `Scope.inside` (`"bindings.value"`), a small declaration change with a real cost in the resolver.
3. Desugaring `let p = e in b` to `(fun p -> b) e` in the parser, which makes scoping exact and loses the source shape the printer and the error messages want.

**A bare identifier on a construct that opens a scope binds outside it.** That is what Python needs for `def f`. OCaml's `for i = a to b do ... done` needs the opposite, so `For.var` holds a `PVar` node: a node can be routed into the scope, a string cannot. `TypeDef.params` has the same shape and is left as it is, since type variables are never renamed. The same field, `TVar.name`, also serves two positions: in a value annotation `'a` declares itself, and in a type declaration it must be a parameter. So the role is `defuse(tyvars)`: the resolver accepts every type variable, while the type checker rejects one that a declaration does not take.

### What writing it found

Each stage ended with a comparison against something independent. These defects came out of those comparisons. None of them crashed.

1. **`( :: )` named nothing.** `::` sat in the parser's operator table, so it parsed to a name no environment could supply. It is a constructor. Found by the test comparing the parser's table with the runtime's.
2. **`let f x : t = e` annotated the wrong thing.** OCaml reads the annotation as the type of `e`; this read it as the type of `f`. Found by `records.ml` refusing to type.
3. **A recursive binding's occurrence was linked to nothing.** The pattern was inferred twice, so `let rec f x = f` typed cleanly. Found by an occurs-check probe that did not fire.
4. **The shared runtime assumed how a function value was spelled.** `List.fold_left` called `f(a)(b)`, which the interpreter's closures accept and the compiler's `def`s do not. Found by the first corpus programme that folded a two-parameter function.
5. **A top-level `let` wrote into a scope a closure had already captured.** `let x = 1  let f = fun () -> x  let x = 2  let y = f ()` gave 2 where OCaml gives 1. Found by the compiled programme disagreeing with the interpreter.
6. **Signatures expanded type abbreviations.** `ocamlc -i` prints `solution` where this printed `float array`. Found when OCaml was installed, on two lines of `records.ml`, and fixed when the *Informatique MPI* programmes made it fourteen files out of nineteen.
