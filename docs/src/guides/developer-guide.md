# Developer guide

This guide is for working on astero itself.

## Commands

```bash
make test       # astero's suite, then each example's
make lint       # ruff, ruff format --check, ty, pyrefly, zuban, mypy
make docs       # build this site with --strict
```

`nox -s check` runs `make lint`, so the two cannot disagree about what a check is.

## Run the suite on more than one interpreter

Much of the code is version-sensitive. A green run on one Python tells you little about the others:

```bash
nox -s tests                    # 3.11 through 3.15
nox -s tests -p 3.15            # one of them
```

The session passes its Python to `uv sync`. Without that, `uv` reads `.python-version`, rebuilds the virtualenv nox just made, and every entry in the matrix runs 3.12 while reporting the version you asked for. A green matrix then means one interpreter passed five times.

These are the version differences that bite:

| what changes | from |
| --- | --- |
| `ast._field_types` exists, so shapes are known (previously `UNKNOWN`) | 3.13 |
| comprehensions stop opening a `symtable` block (PEP 709) | 3.12 |
| PEP 695 blocks spelled `type parameters`, not `type parameter` | 3.13 |
| PEP 649 adds `annotation` blocks | 3.14 |
| `symtable.get_type()` returns an enum (previously a string) | 3.13 |

CPython also injects synthetic names (`.0`, `.defaults`, `.generic_base`, `.type_params`, `__type_params__`, `.format`), which any oracle comparison must filter out.

## The design rule

**Nothing derived is ever authored.** Before adding a table to the codebase, check whether a declaration already determines it. It applies to astero's own source as much as to a consumer's.

## Every derivation needs an oracle

Every derivation is compared against an independent source of truth. Without one, a passing test only shows that the code agrees with itself. The corpus is the Python standard library, and the oracles already exist there:

| derivation | oracle |
| --- | --- |
| `ctx` values | CPython's parser |
| scopes and bound names | the `symtable` module |
| emitted source | emit it, then reparse it |
| a consumer's IR grammar | that consumer's own hand-written pass, frozen |

Thresholds in the integration tests hold the figure that was measured, so a regression fails the suite and an improvement does not have to be chased.

**A switch-over destroys its own oracle.** Once a consumer replaces its hand-written pass with a derivation, both sides of the comparison are the same code and the test checks nothing. When adopting a derivation somewhere, copy the replaced pass into the test as a frozen reference, hold the derivation to that, and add a test checking that the original really is gone.

## Two failure modes to test for

**Drift:** two enumerations of one thing, one stale. Loud; the design prevents it.

**Answering the wrong question:** quiet, because nothing disagrees with anything. `SCOPES` versus `BINDING_SCOPES`, and `ident_slots()` versus `ident_slots(ns)`, were both correct derivations of the wrong thing. Neither was found by reading the code; both were found by a consumer test that stated what the consumer actually meant.

## Measure before building

Four planned features were cancelled by measuring first: a bracketing rewrite, an attribution layer, a document-algebra port, and adopting `tables` in the compiler it was written for. In each case the argument for building was unchecked arithmetic, and checking took minutes.

The test to apply is to **check that the duplication has drifted** before replacing it. That your derivation is correct is a different claim from that the hand-written copies disagree, and only the second is a reason to change anything. `tables` reproduced twelve hand-written dictionaries cell for cell and was still not adopted, because the rule it would have stated once was written six times and all six agreed.

Build what a consumer cannot express without you. Features built because a shape *looked* convertible went unused; features built because a real consumer was stuck landed in an afternoon and were used immediately. Every defect and interface constraint the library has turned up came from adopting it somewhere new. Reading it has turned up none.

## The condition language stays two words

`Present(field)` and `Absent(field)`, and nothing else. It is not a callable.

Admitting an arbitrary predicate would put host code back inside the declaration, which the design exists to remove. The limit has already cost something. PEP 649 annotation scopes depend on a block's *contents*, which `Present` and `Absent` cannot say, so they are handled by a separate `siblings` table instead. The condition language did not widen to absorb them.

The same line applies to `emit_rules` guards, for the same reason.

## Authored data must be gated

Where hand-written data is unavoidable (a table a type checker needs in order to narrow, a frozen oracle, a code snippet in these docs), write a test checking that it still equals what it mirrors.

`CTX_NODES` and `AST_CLASSES` in `rewriting.py` are written out longhand so type checkers can narrow. Each has a test comparing it against what `ast` reports. The tutorials are checked against `examples/` the same way, snippet by snippet and figure by figure, from the example's own suite: each is a project with its own `pyproject.toml`, `ruff.toml` and `tests/`, and a member of the workspace.

The same rule covers what the tools cannot see. `case X()` where `X` is a tuple compiles, satisfies ruff and all four type checkers, and raises only when the arm runs; `test_match_patterns.py` checks every class pattern in the library names a class.

## No inline suppressions

No `# noqa`, no `# type: ignore`, no `# ruff: ignore`. Either fix the cause, or record the exception in `ruff.toml` with a comment saying why.

The pre-commit hook runs a newer ruff than the project pins, so it catches things `make lint` does not.
