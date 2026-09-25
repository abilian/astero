# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-09-25

### Added

- `Scope.outside`: positions under `inside` that are evaluated in the enclosing scope, as dotted paths from the node (a field, `*` for every element of a list, or an index). Python's tables use it for a function's defaults and annotations and a comprehension's first iterable.
- `scopes.evaluated_outside(node, layer, scopes=None)`, the nodes at a layer's `outside` positions, less any that a scope opened along the path claims; and `scopes.layer_binds(node, grammar, ns, scopes)`, the names bound in each layer a node opens.

### Fixed

- A function's defaults and annotations, and a comprehension's first iterable, are evaluated in the scope around it. `scope_tree` puts a lambda in a default beside its function rather than inside it, a walrus in a default binds around the function, and `binds_in_scope`, `shadowed_at`, `substitute` and `free_names` follow.
- `hygiene.shadowed_at`, and with it `substitute` and `free_names` given `scopes=`, now follows `global`, `nonlocal` and class scope. A name declared `global` or `nonlocal` is no longer counted as bound where it is declared, so `substitute` no longer skips a use that reads the module's name, and refuses a target that assigns it. A class body's names no longer shadow inside the functions and generators nested in it.

## [0.2.1] - 2026-09-24

### Fixed

- `hygiene.substitute` with `scopes=` and `fresh=` repaired a capture by renaming the captured name throughout the tree, free uses included: `v + sum(v * z for v in xs)` with `z := v` came out as `_t1 + sum(_t1 * v for _t1 in xs)`. It now renames only where the capturing binding applies.
- `hygiene.shadowed_at` counted a name bound in a nested scope as bound by every scope around it, so `substitute` with `scopes=` left the lambda's own free `v` in `lambda: [v for v in xs] + [v]` unreplaced.
- `hygiene.substitute` with `scopes=` missed a capture when the incoming expression used a name beside its own binding of it: `t + sum(t for t in xs)` moved under a binder of `t` had its first `t` captured.

### Added

- `hygiene.free_names(..., scopes=)`: with a scope table, the exact free names, which is what `substitute` now checks for capture. Without one the tree still counts as one scope, which can miss a free name.

## [0.2.0] - 2026-09-01

### Added

- `astero.grammar`: the grammar core, its queries, and three ways to declare one. `astero.python` is the declared grammar that ships; `examples/postpile_ir/` mirrors postpile's SSA IR as a worked example of a non-tree one.
- `scopes`, `coverage`, `emit`, `emit_rules` and `tables` in the core, `rewriting`, `hygiene` and an emitter under `astero.python`, and `astero.testing`, each deriving what it needs from a grammar.
- A documentation site under `docs/`, including an API reference generated from the source's own docstrings.
- **PL/0**, a second worked compiler, in `examples/pl0/` with a tutorial. Wirth's teaching language: a tree of plain dataclasses where Python has `ast`, a grammar from `from_dataclasses`, two namespaces, and a language that declares a name before it assigns to one. It ships a parser, a P-machine and a tree-walking interpreter. The interpreter is the oracle the compiler is checked against.
- Apache-2.0 licence, and the metadata that names it.
- `emit_rules.Emitter.source_map(node)`: `(start, end, (line, column))` per emitted node, where the first pair indexes the emitted text and the second is where in the source it came from. `emit.spans` walked a document looking for positions and nothing built one carrying any, so the layer was unreachable; that is how it came to be measuring its parts at column zero. Rules do not change and templates gain no hole: the position attaches where the emitter already holds both the node and the document. The offsets stay correct through text the emitter invents, brackets included.
- `scopes.binds_in_scope(node, grammar, ns, scopes)`: every name a node introduces into the scope containing it. `names_bound_by` answers for one node and `scope_tree` for a whole module; this is the question a pass walking a tree asks, and the walk is the part that goes wrong. It reaches through the nodes that carry a binding (`withitem`, `alias`, `ExceptHandler`, a match pattern) and stops at a scope boundary, so a nested `def` contributes its own name and nothing else. `stop` bounds it to one statement for a flow analysis.
- `coverage.visitors(*classes)`: production names read off `visit_<Production>` method names, joining `handlers` and `match_arms` as the third way a consumer enumerates a language. It reads each class's own methods along the MRO. `dir()` would be shorter and wrong: `ast.NodeVisitor` defined `visit_Constant` through Python 3.13 and CPython dropped it in 3.14, so it reports a subclass as handling `Constant` on one interpreter and not the next.
- `Production[name]` and `name in production`, the twins of `Grammar[name]`. `Production.field(name)` still answers `Field | None`, for a caller asking whether a field exists; the subscript is for one that knows it does and was re-checking at every use.

### Changed (breaking)

The package is split by language. Everything under `astero` is now
language-agnostic; everything specific to Python is under `astero.python`.
There are no compatibility shims: 0.1.0 is days old and the import paths move.

**Upgrading from 0.1.0** touches two rows, because 0.1.0 shipped only the
rewrite engine. Everything else below was added *and* moved inside this
release, and is listed for anyone who tracked the branch.

| before | 0.2.0 | in 0.1.0? |
| --- | --- | --- |
| `astero.rewriting` | `astero.python.rewriting` | **yes** |
| `from astero import Pass, rewrite, rules, …` | `from astero.python import …` | **yes** |
| `astero.lang_py` | `astero.python` | no |
| `astero.emit_py` | `astero.python.emit` | no |
| `astero.hygiene` | `astero.python.hygiene` | no |
| `astero.generate` | `astero.testing` | no |
| `astero.lang_ssa`, `astero.lang_postpile_runtime` | `examples/postpile_ir/` | no |

`astero/__init__.py` exports nothing now. Its entire previous surface came
from `rewriting` and `hygiene`, which is what settled that both are Python's:
`fix_contexts` computes an expression context no other language has, and
substitution is over `ast.Name`. `examples/pl0` imports neither.

Python's operator precedence moved out of `astero.emit` into
`astero.python.precedence`. `emit` holds the document algebra and the
bracketing rule, which know no operators; the table of what binds tighter than
what is a fact about one language. `astero.emit` no longer imports `ast`.

Two read-only mirrors of postpile's internals left the distribution. A generic
library has no business shipping one named consumer's instruction set in its
public namespace, and both were worked examples already by their own
docstrings.

### Changed

- `astero.python` no longer reports productions the parser cannot produce, so `PY.concrete()` returns 111 on Python 3.13 where it returned 117. `ast` still exposes `Num`, `Str`, `Bytes`, `NameConstant` and `Ellipsis` (folded into `Constant` in 3.8), and `Index`, `ExtSlice`, the `slice` sort, `AugLoad`, `AugStore`, `Param` and `Suite` (all gone in 3.9). Each is an `ast.AST` subclass that never comes out of `ast.parse`, Every consumer building a coverage obligation had to subtract them by hand. The set also differed between 3.11 and 3.12 for reasons unrelated to the language. The new `astero.python.DEPRECATED_ALIASES` names them, read off the interpreter and never listed. The real grammar is the C module `_ast`; the compatibility shims are defined in Python in `ast.py`.

### Fixed

- **`hygiene`'s name queries were Python-only, silently.** `taken_names`, `all_names` and `free_names` walked with `ast.walk`, which reads `node._fields`, so against a grammar declared off dataclasses they answered *emptily* rather than raising. A caller drawing fresh names from an empty `taken_names` would collide with every name in the program. `rename` was the loud half and raised. All of them go through the new `scopes.walk(node, grammar)`, and `examples/pl0` is the test. `substitute` stays Python's, and now says why: replacing a use with a subtree needs the language to spell uses as nodes in expression position, and PL/0's `Assign.name` is typed `Ident`.
- **`scopes` was Python-only, silently.** It read a node's fields with `ast.iter_fields` and tested nodes with `isinstance(node, ast.AST)`, so a tree of dataclasses produced a root block with no children and no bound names, and no error. It reads the fields from the grammar now, which is information the grammar already carried. The field order this produces matches `ast.iter_fields` for every node of the standard library, and the PL/0 example is the test that would have caught it.
- PEP 649 annotation blocks, from Python 3.14: `scope_tree` takes a `siblings` table and `astero.python.annotation_blocks(tree)` supplies it, returning nothing for a module carrying `from __future__ import annotations`, where PEP 563 makes annotations strings instead. This was the last gap between the derived scope tree and `symtable` on 3.14 and 3.15.
- Python 3.15 renamed the blocks CPython names itself, so `lambda` joins `genexpr` in being spelled version-dependently.
- A production the precedence table omits now imposes no bracketing on its children, so a statement rule no longer brackets its own operand.
- `scope_tree` accepts any node the declared grammar knows, which is what it already did. Its annotation said `ast.AST` and outlived the implementation.
- `Emitter.to_lines` walked a document with an `else` branch that read `doc.doc`. `Doc` is a base class, not a closed union, so that branch caught a bare `Doc` and any later subclass as well as the `Nest` it was written for. It dispatches explicitly now and raises on a document it does not know.
- `generate.missing_coverage` declared `Mapping[str, Scope]` for an argument every caller passes a layer table to. It reads only the keys, so it worked and the annotation was wrong.
- `Pass`'s `stop_at` documentation described behaviour the code has never had. The named node is skipped whole, neither entered nor offered to the rules, with the tree the pass is called on as the one exception.

### Internal

These change nothing a consumer can call, and are recorded because each was a check that looked like coverage and was not.

- **The version matrix ran 3.12 five times.** nox built the right virtualenv per session and `uv sync --active` rebuilt it, because `.python-version` pins 3.12 and uv honours it over the active interpreter. Support for 3.11 through 3.15 was therefore claimed on the strength of one interpreter. Passing the session's Python to uv fixes it, and needs a `test` dependency group: `dev` carries `pre-commit`, whose `pyyaml` cannot build on 3.15.
- `make lint` runs six checkers and had never passed. The nox `check` session ran three of them, scoped to `src`, so nothing reported the other 49 diagnostics. It calls `make lint` now, and `ruff`, `ty`, `pyrefly`, `zuban` and `mypy` are all clean across `src`, `tests` and `examples`.
- The SSA oracles skipped every run, because postpile's own dependency was not installed. `postyp` is a dev dependency now. postpile itself is still not one: those tests locate a checkout and skip when there is none.
- Two tests put every assertion inside a loop over a computed collection, so an empty collection meant they checked nothing. Both have a floor now. An audit over the suite found seven more, all of which loop over a literal.

## [0.1.0] - 2026-08-10

### Added

- `astero.rewriting`: a rewrite-rule engine over Python ASTs. Rules are single strings with `=>` between pattern and replacement, in concrete Python syntax or in abstract `ast.Cls(...)` terms. Metavariables, wildcards, list and keyword splices, three traversal strategies, per-pass postconditions, and rules that print themselves.
- Ported from the prototype validated against latexify_py, whose six `ast.NodeTransformer` passes it reimplements. Differential testing over 68 inputs found 121 divergences, all of them bugs in the hand-written originals.

### Documentation

- `notes/common/`: the prior-art survey, the area survey beyond desugaring, the design of the grammar core, and the plan.
