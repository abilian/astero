# The playground

The playground runs the whole compiler in a browser tab and shows six views of the same programme side by side.

```sh
make -C examples web-serve
```

Then <http://localhost:8000/>. The page uploads nothing, stores nothing, and needs no OCaml on the far end.

## What it shows

Five of them are the five the command line has, with the source pane beside them. The sixth is the one a command line cannot give you.

**Run** is what the programme prints. The status line reports whether *both back ends agree*, which is the differential test of [the back ends](back.md) running on whatever you typed: the programme is executed twice, once by walking the tree and once through the emitted Python.

**Types** is the signature inferred, as `ocamlc -i` would print it. A type variable written `'_weak1` has not been generalized, which is [the value restriction](middle.md).

**Names** is the scope tree, one per namespace. Reading it answers the questions people actually get stuck on: which `x` does this `x` refer to, does this recursive call resolve, does that parameter escape the function.

**Python** is what the second back end emits, and **Read back** is your source written back out of the tree, which is how you check the grouping is what you meant.

**Step** walks through the run. The programme is recorded once, evaluation by evaluation; you then move through the recording in either direction: backwards costs nothing because the run already happened, so going back reads a list. Each step marks the sub-expression in the source and lists the names in scope with what they hold. The mutable cells are listed apart from the names, so two names for one `ref` appear as one row. The step also names the block the **Names** view would draw, read from the same declaration.

`back/stepper.py` is the whole of it and holds no interpreter of its own. `interpret.eval_expr` calls a module-level `watching` when one is set, which is the only thing the back end knows about any of this; an ordinary run pays one comparison per node for it. Stepping into and out of a call counts calls, skipping sub-expressions: every operand of an expression is deeper than the expression, and none of them is a call.

The emitted Python is stepped too, by `sys.settrace` over the module the compiler produced. The two back ends do not take the same steps, so they are lined up on the one thing they share: how much each has printed. The alignment is exact where output happens and nearest-so-far between; the first character where they disagree marks a defect in one of them.

Two help pages sit beside it, linked from the header: one on using the playground, and a language reference.

## How it is built

[Pyodide](https://pyodide.org) is CPython compiled to WebAssembly. Both packages here are pure Python with no dependencies, so the toolchain is one zip and one call:

```js
await py.unpackArchive(await bundle.arrayBuffer(), "zip", { extractDir: HOME });
analyse = py.runPython("from ocaml.pipeline import analyse\nanalyse");
```

`web/build.py` builds one zip from `src/astero`, `src/ocaml` and the sixty corpus programmes, straight from the working tree. The bundle weighs 224 KB and vendors nothing, so what the page runs is what the tests run.

The whole Python side is one function. `ocaml.pipeline.analyse(source)` runs every stage and returns what each produced, so the page is a view over one dictionary and the JavaScript stays dumb. `python -m ocaml` prints one of its keys; the page renders all five. Neither repeats the sequence.

## The reference page is generated

`language.html` is a card covering the whole subset: definitions, types, expressions, patterns, operators, keywords, the standard library, and the known divergences from real OCaml.

Three of its tables are read off the compiler when the page is built:

| table | read from |
| --- | --- |
| operators, with precedence and associativity | `front/parser.py`'s `LEVELS` |
| keywords | `front/lexer.py`'s `KEYWORDS` |
| every standard-library name, with its type | `middle/prelude.py`'s `PRELUDE_TYPES` |

So adding a function to the prelude puts it in the documentation, with its type, without anybody editing the page. A test checks that the generated page contains all three tables in full, so the derivation cannot stop without a failure.

The prose lives in `language.template.html`, which is in the repository; `language.html` is a build product, like the bundle.

## Deploying it

The site is the contents of `web/` after `make -C examples web`. Any static host will serve it, since there is no server side. The only thing fetched from elsewhere is Pyodide itself, from a CDN, pinned to one version in a constant at the top of `app.js`.

If it does not load, the status line says why. The two usual causes are that the CDN has moved on, in which case bump `PYODIDE_VERSION`, and that the bundle has not been built, in which case run `make -C examples web`.
