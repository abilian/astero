"""B4 and the table language's own behaviour."""

from __future__ import annotations

import pytest

from astero.tables import Family, TableError

DEMO = Family.parse(
    "demo",
    normalize={"Bool": "Int64"},
    matrix="""
                  Int64     Float64   Str
    get           GET_I64   GET_F64   GET_STR
    get_fast      GET_I64_U GET_F64_U .
    """,
)


def test_lookup_and_holes() -> None:
    assert DEMO.lookup("get", "Str") == "GET_STR"
    assert DEMO.lookup("get_fast", "Str") is None
    assert DEMO.holes() == (("get_fast", "Str"),)


def test_normalization_applies_to_every_row() -> None:
    assert "Bool" not in DEMO.index
    assert DEMO.resolve("Bool") == "Int64"
    for op in DEMO:
        assert DEMO.lookup(op, "Bool") == DEMO.lookup(op, "Int64")


def test_as_dict_is_the_hand_written_shape() -> None:
    """A dictionary cannot express a hole, so the hole is simply absent."""
    assert DEMO.as_dict("get") == {
        "Int64": "GET_I64",
        "Float64": "GET_F64",
        "Str": "GET_STR",
        "Bool": "GET_I64",
    }
    assert DEMO.as_dict("get_fast", include_aliases=False) == {
        "Int64": "GET_I64_U",
        "Float64": "GET_F64_U",
    }


def test_b4_a_missing_cell_is_an_error() -> None:
    """B4: a row that does not cover the index is rejected at declaration."""
    with pytest.raises(TableError, match="2 cells for 3 keys"):
        Family.parse(
            "bad",
            matrix="""
                      a       b       c
            row       A       B
            """,
        )


def test_an_alias_must_land_in_the_index() -> None:
    with pytest.raises(TableError, match="normalizes to 'Nope'"):
        Family.parse("bad", matrix="\n a\n row A\n", normalize={"Bool": "Nope"})


def test_an_alias_cannot_also_be_a_column() -> None:
    with pytest.raises(TableError, match="both an index key and an alias"):
        Family.parse(
            "bad", matrix="\n Int64 Bool\n row A B\n", normalize={"Bool": "Int64"}
        )


def test_a_duplicate_column_is_rejected() -> None:
    with pytest.raises(TableError, match="duplicate key"):
        Family.parse("bad", matrix="\n a a\n row A B\n")


def test_unknown_operations_and_keys_say_so() -> None:
    with pytest.raises(KeyError, match="no operation 'nope'"):
        DEMO.lookup("nope", "Int64")
    with pytest.raises(KeyError, match="not defined at 'Bytes'"):
        DEMO.lookup("get", "Bytes")


def test_comments_and_blank_lines_are_skipped() -> None:
    family = Family.parse(
        "demo",
        matrix="""
        # the index
              a     b
        row   A     B    # trailing
        """,
    )
    assert family.index == ("a", "b")
    assert family.lookup("row", "b") == "B"


def test_a_family_renders_back_as_a_matrix() -> None:
    assert DEMO.as_matrix().splitlines() == [
        "          Int64      Float64    Str",
        "get       GET_I64    GET_F64    GET_STR",
        "get_fast  GET_I64_U  GET_F64_U  .",
    ]
