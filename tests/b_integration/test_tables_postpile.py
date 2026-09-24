"""B1 to B4: declared families against postpile's hand-written tables.

postpile is read, never imported. Point `POSTPILE_SRC` at a checkout, or leave
one beside astero.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from postpile_ir.runtime import CHAN, LIST, OBJ

_CANDIDATES = [
    Path(os.environ["POSTPILE_SRC"]) if os.environ.get("POSTPILE_SRC") else None,
    # The sandbox copy comes first. There is often a second checkout beside
    # astero, and reading that one while editing this one validates a tree
    # nobody is changing.
    Path(__file__).resolve().parents[2] / "sandbox" / "postpile",
    Path(__file__).resolve().parents[3] / "postpile",
    Path.home() / "projects" / "compilers" / "postpile",
]

_COMMON = "src/postpile/compiler/frontend/common.py"


def _tables() -> dict[str, dict[str, str]]:
    """Every `dict[type[DType], str]` table in postpile's frontend, by name."""
    for root in _CANDIDATES:
        if root and (root / _COMMON).exists():
            tree = ast.parse((root / _COMMON).read_text(encoding="utf-8"))
            break
    else:
        pytest.skip("no postpile checkout found; set POSTPILE_SRC")
    return {
        node.target.id: {
            ast.unparse(k): ast.unparse(v)
            # A `None` key is `{**other}`, which these tables do not use.
            for k, v in zip(node.value.keys, node.value.values, strict=True)
            if k is not None
        }
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Dict)
    }


# One family row per hand-written table.
LIST_ROWS = {
    "_LIST_APPEND": (LIST, "append"),
    "_LIST_GET": (LIST, "get"),
    "_LIST_SET": (LIST, "set"),
    "_LIST_HAS": (LIST, "has"),
    "_LIST_GET_U": (LIST, "get_unchecked"),
    "_LIST_SET_U": (LIST, "set_unchecked"),
}
CHAN_ROWS = {
    "_CHAN_SEND": (CHAN, "send"),
    "_CHAN_RECV": (CHAN, "recv"),
    "_SELECT_SEND": (CHAN, "select_send"),
    "_SELECT_READ": (CHAN, "select_read"),
}
OBJ_ROWS = {
    "_OBJ_GET": (OBJ, "get"),
    "_OBJ_SET": (OBJ, "set"),
}


def _assert_rows_reproduce(rows, tables) -> None:
    for name, (family, op) in rows.items():
        assert name in tables, f"{name} is gone from postpile's source"
        derived = family.as_dict(op)
        assert derived == tables[name], (
            f"{family.name}.{op} does not reproduce {name}:\n"
            f"  declared: {derived}\n"
            f"  postpile: {tables[name]}"
        )


def test_b1_one_family_reproduces_the_six_list_tables() -> None:
    """B1: six hand-written dictionaries, one declaration, cell for cell."""
    _assert_rows_reproduce(LIST_ROWS, _tables())


def test_b2_one_family_reproduces_the_channel_and_select_tables() -> None:
    """B2: four tables with two different key sets, one declaration.

    `_CHAN_SEND` carries a Bool key and `_SELECT_SEND` does not, because
    postpile normalizes before the second and not before the first. One
    normalization makes them the same shape.
    """
    tables = _tables()
    for name, (family, op) in CHAN_ROWS.items():
        assert name in tables
        aliases = name in {"_CHAN_SEND", "_CHAN_RECV"}
        derived = family.as_dict(op, include_aliases=aliases)
        assert derived == tables[name], (
            f"{family.name}.{op} does not reproduce {name}:\n"
            f"  declared: {derived}\n"
            f"  postpile: {tables[name]}"
        )


def test_b2_object_field_tables() -> None:
    tables = _tables()
    for name, (family, op) in OBJ_ROWS.items():
        assert family.as_dict(op, include_aliases=False) == tables[name], name


def test_b3_the_wire_rule_is_stated_once() -> None:
    """B3: Bool resolves to Int64 for every row of every family, from one place."""
    for family in (LIST, CHAN, OBJ):
        assert "Bool" not in family.index, "Bool is an alias, never a column"
        for op in family:
            assert family.lookup(op, "Bool") == family.lookup(op, "Int64"), (
                f"{family.name}.{op}"
            )


def test_the_declared_holes_are_the_ones_postpile_leaves_out() -> None:
    """postpile expresses a hole as an absent key. The family says it out loud."""
    tables = _tables()
    assert LIST.holes() == (("get_unchecked", "Str"), ("set_unchecked", "Str"))
    assert "Str" not in tables["_LIST_GET_U"]
    assert "Str" not in tables["_LIST_SET_U"]


def test_the_wire_rule_still_matches_postpiles_own() -> None:
    tables = _tables()
    wire = tables["_CHAN_WIRE"]
    # `_tables()` parses postpile's source, so an empty table means the parse
    # stopped matching rather than that the wire rule agrees.
    assert len(wire) > 1, f"_CHAN_WIRE parsed to {len(wire)} rows"
    for key, target in wire.items():
        assert CHAN.resolve(key) == target, f"_CHAN_WIRE says {key} -> {target}"
