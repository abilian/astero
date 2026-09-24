"""The runtime operation families, checked against themselves.

`test_tables_postpile.py` checks these against the sixteen tables in
postpile's own source, which is the real oracle and needs a checkout.
Without one nothing looked at this module: a typo in a matrix, a row that
lost a column, a hole in the wrong cell would all have gone unnoticed until
someone had postpile beside them.

Nothing here reads postpile. The question is whether the declaration says
what it was written to say.
"""

from __future__ import annotations

import pytest
from postpile_ir.runtime import CHAN, FAMILIES, LIST, OBJ, WIRE

from astero.tables import HOLE, Family, TableError

ALL = [LIST, CHAN, OBJ]
IDS = [family.name for family in ALL]


@pytest.mark.parametrize("family", ALL, ids=IDS)
def test_every_family_is_keyed_by_the_three_element_types(family: Family) -> None:
    assert family.index == ("Int64", "Float64", "Str")


def test_the_operations_each_family_declares() -> None:
    assert set(LIST) == {
        "append",
        "get",
        "set",
        "has",
        "get_unchecked",
        "set_unchecked",
    }
    assert set(CHAN) == {"send", "recv", "select_send", "select_read"}
    assert set(OBJ) == {"get", "set"}


@pytest.mark.parametrize("family", ALL, ids=IDS)
def test_a_bool_crosses_the_wire_as_an_int64(family: Family) -> None:
    """The rule this module exists to state once.

    postpile spelled it three ways across sixteen tables: inlined as a key,
    keyed on another table's output, and pushed onto callers through a
    parameter named `wire`. Here it is `normalize=WIRE`, applied to every
    row of every family.
    """
    assert WIRE == {"Bool": "Int64"}
    assert "Bool" not in family.index, "Bool is an alias, never a column"
    for op in family:
        assert family.lookup(op, "Bool") == family.lookup(op, "Int64"), op


def test_the_unchecked_list_helpers_have_no_string_form() -> None:
    """A hole, not a missing key: a Str element stays on the borrow-classified
    helpers, which is a decision rather than an omission."""
    assert LIST.holes() == (("get_unchecked", "Str"), ("set_unchecked", "Str"))
    assert LIST.lookup("get_unchecked", "Str") is HOLE
    assert LIST.lookup("get_unchecked", "Int64") == "LIST_GET_I64_U"


@pytest.mark.parametrize("family", ALL, ids=IDS)
def test_only_the_list_family_has_holes(family: Family) -> None:
    assert family.holes() == () or family is LIST


def test_as_dict_drops_the_holes_and_can_add_the_aliases() -> None:
    plain = LIST.as_dict("get_unchecked", include_aliases=False)
    assert plain == {"Int64": "LIST_GET_I64_U", "Float64": "LIST_GET_F64_U"}
    assert "Str" not in plain, "a hole is absent, not None"
    assert LIST.as_dict("get", include_aliases=True)["Bool"] == "LIST_GET_I64"


def test_the_families_are_registered_by_name() -> None:
    assert FAMILIES == {"list": LIST, "chan": CHAN, "obj": OBJ}


def test_a_ragged_matrix_is_refused() -> None:
    """`Family.parse` describes a rectangle, and says so when it is handed
    something else. Nothing in this module is ragged; this is the guard that
    makes the tables above meaningful."""
    with pytest.raises(TableError):
        Family.parse(
            "ragged",
            matrix="""
                     Int64      Float64
            get      G_I64
            """,
        )
