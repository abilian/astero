"""Nox configuration."""

from __future__ import annotations

from pathlib import Path

import nox

# The floor is 3.11 (pyproject), and the grammar work targets 3.15 too.
PYTHONS = ["3.11", "3.12", "3.13", "3.14", "3.15"]


#: The worked examples, which are workspace members with suites of their
#: own. They run in the matrix too: `examples/ocaml` sets a field on
#: `ast.FunctionDef` that 3.12 added, and nothing else would catch it.
EXAMPLES = ["pl0", "tinypy", "ocaml"]


@nox.session(python=PYTHONS)
def tests(session: nox.Session):
    """Run the test suite, astero's and each example's."""
    # Not `make test`: that runs the project venv's interpreter, and the
    # point of this session is the one nox built for this version.
    uv_sync(session)
    session.run("pytest")
    root = Path.cwd()
    for example in EXAMPLES:
        session.chdir(root / "examples" / example)
        session.run("pytest", "-q")
    session.chdir(root)


@nox.session
def check(session: nox.Session):
    """Run every check `make lint` runs.

    Delegated rather than restated. This session used to list `ruff check`,
    `ruff format --check` and `ty check src`, which was a subset of the
    Makefile's six and scoped to `src`, so CI passed while `make lint`
    reported 49 diagnostics across the tests and the examples. One
    definition cannot disagree with itself.
    """
    uv_sync(session)
    session.run("make", "lint", external=True)


#
# Utils
#
def uv_sync(session: nox.Session):
    """Install the project into the venv nox built for this session.

    `--python` is not optional. Without it `uv sync` reads `.python-version`,
    which pins 3.12, and *rebuilds* the session's virtualenv with that
    interpreter — so every version in the matrix ran 3.12 and `-p 3.15`
    tested nothing 3.12 did not. nox reported the right interpreter while
    creating the venv, which is what made it hard to see.
    """
    python = session.python if isinstance(session.python, str) else None
    args = ["uv", "sync", "-q", "--active"]
    if python:
        # A version session installs the `test` group only. `dev` carries
        # `pre-commit`, whose `pyyaml` does not build on 3.15, and none of
        # the checkers are needed to run the suite.
        args += ["--python", python, "--no-dev", "--group", "test"]
    session.run(*args, external=True)
    # session.run(
    #     "uv", "sync", "-q", "--all-groups", "--all-extras", "--active",
    #     external=True,
    # )
