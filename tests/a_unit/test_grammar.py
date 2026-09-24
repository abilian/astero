"""Declaring a sublanguage as a subset of a declared one.

A compiler for a Python subset names the productions it admits, and everything
else — roles, sorts, shapes, conditions — comes from the grammar it is a subset
of. Writing the tutorial found this missing: filtering `PY.productions` by hand
failed with `KeyError: 'Store'`, because the context productions are machinery
its author never names.
"""

from __future__ import annotations

import ast

import pytest


def test_a_subset_keeps_the_named_productions() -> None:
    from astero.python import PY

    named = {"Module", "Assign", "Name", "Constant", "BinOp", "Add"}
    tiny = PY.subset(named)
    assert named <= set(tiny.productions)
    assert tiny.check() == []

    # The abstract bases come too. They are sorts, not productions a
    # sublanguage admits or refuses, and without them `concrete(sort)` stops
    # answering on the result.
    assert tiny.concrete("expr") == {"Name", "Constant", "BinOp"}
    assert tiny.concrete("stmt") == {"Assign"}
    assert "Add" not in tiny.concrete("expr"), "an operator is not an expression"
    # Roles, sorts and shapes come from the grammar it is a subset of.
    assert tiny["Assign"]["targets"].role == PY["Assign"]["targets"].role


def test_a_subset_of_something_absent_is_an_error() -> None:
    from astero.python import PY

    with pytest.raises(KeyError, match="Nonexistent"):
        PY.subset({"Module", "Nonexistent"})


def test_a_pass_over_a_subset_still_derives_contexts() -> None:
    """The first thing a new consumer hit: contexts are machinery, and a
    sublanguage's author never names `Store`, `Load` or `Del`."""
    from astero.python import PY, Pass, rules

    tiny = PY.subset({
        "Module",
        "Assign",
        "AugAssign",
        "Name",
        "Constant",
        "BinOp",
        "Subscript",
        "Add",
    })
    desugar = Pass(
        "desugar",
        rules("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"),
        eliminates=(ast.AugAssign,),
        grammar=tiny,
    )
    out = desugar(ast.parse("b[1] += 5"))
    assert ast.unparse(out) == "b[1] = b[1] + 5"
    assert isinstance(out.body[0].targets[0].ctx, ast.Store)
    assert isinstance(out.body[0].value.left.ctx, ast.Load)
