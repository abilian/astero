"""A2: Python's declared grammar. A1 lives in tests/b_integration.

These are the gates the design note asks for. The role table is authored, which
is the one thing the design condemns, so it earns its place by being checkable
against the parser that produced the trees.
"""

from __future__ import annotations

import ast

import pytest

from astero import grammar
from astero.python import PY


def test_a2_ident_slots_reach_what_hand_written_tables_missed() -> None:
    """A2: the derived slots include the four positions the audit found missing."""
    slots = PY.ident_slots()
    assert "arg" in slots["arg"], "parameters, including vararg/kwarg/lambda"
    assert "name" in slots["AsyncFunctionDef"], "async def was skipped by hand"
    assert "name" in slots["FunctionDef"]
    assert "id" in slots["Name"]


def test_a2_every_identifier_field_is_declared() -> None:
    """Any `str`-sorted field the grammar reports must be classified.

    Needs `_field_types`, so it only runs where the interpreter supplies sorts.
    """
    if PY["Name"]["id"].shape is grammar.Shape.UNKNOWN:
        pytest.skip("interpreter does not expose ast._field_types")
    undeclared = []
    for prod in PY:
        cls = getattr(ast, prod.name, None)
        types: dict[str, object] = getattr(cls, "_field_types", None) or {}
        for fname, ann in types.items():
            if "identifier" not in str(ann) and str(ann) != "<class 'str'>":
                continue
            fld = prod.field(fname)
            if (
                fld is not None
                and fld.sort not in PY.ident_sorts
                and fld.role.kind is not grammar.Kind.ATTR
            ):
                undeclared.append(f"{prod.name}.{fname}")
    assert not undeclared, (
        f"identifier-typed fields with no declared role: {undeclared}"
    )


def test_annotations_are_not_a_casualty_of_renaming() -> None:
    """The slot table renames in place, so sibling fields cannot be dropped.

    The hand-written pass rebuilt each parameter as `ast.arg(arg=...)` and lost
    its annotation. A slot is a field, so nothing else is touched.
    """
    tree = ast.parse("def f(x: int, *args: str, **kw: bytes) -> float: return x")
    slots = PY.ident_slots()
    renamed = 0
    for node in ast.walk(tree):
        for fname in slots.get(type(node).__name__, ()):
            value = getattr(node, fname, None)
            if isinstance(value, str):
                setattr(node, fname, value + "_z")
                renamed += 1
    assert renamed >= 5, "def name plus three parameters at least"
    out = ast.unparse(tree)
    # Every annotation survives, and the names inside them are renamed too,
    # which is what a global rename should do. The hand-written pass dropped
    # them entirely.
    assert out == (
        "def f_z(x_z: int_z, *args_z: str_z, **kw_z: bytes_z) -> float_z:"
        "\n    return x_z"
    )


def test_grammar_is_well_formed() -> None:
    assert PY.check() == []
