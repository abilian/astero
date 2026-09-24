# caml-prépa — browser playground

The compiler of `examples/ocaml/` running in a browser, with six views of
the same programme: what it prints, the types it infers, the scopes astero
derives, the Python it compiles to, the source read back from the tree, and
the run one step at a time.

It runs the emitted Python as well as interpreting the tree, and the status
line says whether the two agreed. That is the differential test from
`tests/test_ocaml.py`, live.

## Running it

```sh
make -C examples web-serve      # builds the bundle, serves on :8000
```

Then open <http://localhost:8000/>. A plain HTTP server is enough; `file://`
will not do, because the page fetches its bundle.

`make -C examples web` builds `web/py/playground.zip` on its own, which is
what a static deploy needs. The whole site is the contents of `web/`, and
any host that serves a `.zip` and a `.wasm` will do.

## How it works

[Pyodide](https://pyodide.org) is CPython compiled to WebAssembly. Both
packages here are pure Python with no dependencies, so the entire toolchain
is one zip and one `unpackArchive` call:

- `build.py` zips `src/astero`, `examples/ocaml/src/ocaml`, `playground.py`
  and the corpus programmes, with the GPL text the `grimaud/` ones carry — built from the working tree,
  so what the page runs is what the tests run. Nothing is vendored.
- `ocaml.pipeline.analyse(source)` is the whole Python side: it runs every
  stage and returns what each produced. The page is a view over that dict,
  and `python -m ocaml` prints one of its keys.
- `app.js` boots Pyodide, unpacks the zip, fills the programme dropdown from
  the corpus it finds in the virtual filesystem, and renders.

## Files

- `index.html` — the playground
- `style.css` — palette on `:root`, redefined once for dark
- `app.js` — Pyodide boot, the six views, links (`#example=` for a worked
  example, `#z=` for deflated source)
- `build.py` — the bundler, and the reference-card generator
- `py/playground.zip` — the bundle (built; not in the repository)

## Serving it on its own

`make -C examples web-serve` serves this directory alone, which is the quick
path while working on the playground itself. The header links then go
nowhere: they are relative to the site, where this is mounted at `/play/`.
`make -C examples ocaml-docs-serve` runs `zensical serve` over one edition,
which rebuilds and reloads as you edit the documentation. It does not watch
this directory: change `app.js` or `style.css` and re-run it, because the
playground is copied in by the `web` target rather than served from here.

## Where the help pages went

The playground is one page of a site: `../docs/` holds the language tour,
the guide to these six views, and the reference card. `make -C .. ocaml-docs`
builds that site and copies this directory into it at `/play/`, which is why
the header links here are `../language/...`.

## The reference card is generated

Three of its tables are read off the compiler when the docs are built: the
operators with their precedence from `front/parser.py`'s `LEVELS`, the
keywords from `front/lexer.py`, and every standard-library name with its
type from `middle/prelude.py`. So a name added to the prelude appears in the
documentation, with its type, without anybody editing a page.

`build.py` fills `docs/src/language/reference.template.md`, which is in the
repository, and writes `reference.md`, which is not. A test asserts the
generated page holds all three tables in full.

## If it does not load

The status line says what failed. The usual two:

- **Pyodide will not load.** The version is one constant at the top of
  `app.js`; bump `PYODIDE_VERSION` when the CDN moves on.
- **`py/playground.zip` is missing.** Run `make -C examples web`.
