"""A grammar read off annotated dataclasses, the third front door.

`astero.python.build` reads a module of `ast` classes and `lang_ssa` is written out
by hand. A compiler whose IR is already dataclasses should declare it in
place, with only the roles authored.
"""

from __future__ import annotations

import dataclasses

import pytest

from astero.grammar import (
    ATTR,
    CHILD,
    Absent,
    Present,
    Shape,
    defines,
    from_dataclasses,
    sort_of,
    uses,
)

VALS = "vals"


@dataclasses.dataclass
class Value:
    name: str


@dataclasses.dataclass
class BinOpInstr:
    result: Value
    op: str
    left: Value
    right: Value


@dataclasses.dataclass
class Call:
    result: Value | None
    func: str
    args: list[Value]


@dataclasses.dataclass
class AssignValue:
    target: Value
    value: Value
    declare: bool


ROLES = {
    "BinOpInstr": {"result": defines(VALS), "left": uses(VALS), "right": uses(VALS)},
    "Call": {"result": defines(VALS), "args": uses(VALS)},
    # One slot, two roles, told apart by a sibling.
    "AssignValue": {
        "value": uses(VALS),
        "target": (
            (defines(VALS), Present("declare")),
            (uses(VALS), Absent("declare")),
        ),
    },
}


def _grammar():
    return from_dataclasses(
        "demo", [BinOpInstr, Call, AssignValue], roles=ROLES, namespaces={VALS}
    )


def test_names_sorts_and_shapes_come_from_the_annotations() -> None:
    g = _grammar()
    assert g["Call"]["result"].shape is Shape.OPT
    assert g["Call"]["args"].shape is Shape.SEQ
    assert g["BinOpInstr"]["left"].shape is Shape.ONE
    assert g["Call"]["args"].sort == "Value"


def test_only_the_roles_are_authored() -> None:
    """A field with no role is an attr when it holds plain data."""
    g = _grammar()
    assert g["BinOpInstr"]["op"].role == ATTR
    assert g["Call"]["func"].role == ATTR
    assert g["AssignValue"]["declare"].role == ATTR


def test_a_field_with_an_unknown_sort_stays_a_child() -> None:
    """The answer that keeps traversal complete."""

    @dataclasses.dataclass
    class Odd:
        thing: Value

    g = from_dataclasses("odd", [Odd], namespaces={VALS})
    assert g["Odd"]["thing"].role == CHILD


def test_the_queries_answer_over_the_derived_grammar() -> None:
    g = _grammar()
    assert g.operands(VALS)["BinOpInstr"] == ("left", "right")
    assert g.definitions(VALS)["Call"] == ("result",)


def test_one_slot_can_carry_two_conditional_roles() -> None:
    """postpile's `AssignValue.target`: defined when declaring, read otherwise."""
    g = _grammar()
    assert g.check() == []
    target, value = Value("t"), Value("v")

    declaring = AssignValue(target, value, True)
    assert g.binds(declaring, VALS) == (target,)
    assert g.reads(declaring, VALS) == (value,)

    reassign = AssignValue(target, value, False)
    assert g.binds(reassign, VALS) == ()
    assert g.reads(reassign, VALS) == (target, value)


def test_reads_flattens_a_sequence_and_skips_an_empty_option() -> None:
    """`Call.args` is a list and `Call.result` may be absent."""
    g = _grammar()
    a, b = Value("a"), Value("b")
    assert g.reads(Call(None, "f", [a, b]), VALS) == (a, b)
    assert g.binds(Call(None, "f", []), VALS) == ()
    assert g.binds(Call(a, "f", []), VALS) == (a,)


def test_an_undeclared_production_is_an_error_not_an_empty_answer() -> None:
    """The failure postpile's verifier values: an IR node nobody declared is
    invisible to every invariant at once, so it has to be loud."""

    @dataclasses.dataclass
    class Undeclared:
        result: Value

    with pytest.raises(KeyError, match="Undeclared"):
        _grammar().reads(Undeclared(Value("x")), VALS)


def test_a_conditional_field_is_reported_once_by_positions() -> None:
    assert _grammar().operands(VALS)["AssignValue"].count("target") == 1


def test_an_unconditional_duplicate_is_still_an_error() -> None:
    from astero.grammar import Field, Grammar, Production

    prod = Production(
        "Dup",
        (Field("x", uses(VALS), sort="Value"), Field("x", defines(VALS), sort="Value")),
    )
    problems = Grammar("g", {"Dup": prod}, namespaces=frozenset({VALS})).check()
    assert any("duplicate field" in p for p in problems)


def test_a_class_that_is_not_a_dataclass_is_rejected() -> None:
    class Plain:
        pass

    with pytest.raises(TypeError, match="Plain is not a dataclass"):
        from_dataclasses("bad", [Plain])


def test_the_grammar_carries_the_classes_so_rewrites_can_build() -> None:
    g = _grammar()
    assert g.constructor("BinOpInstr") is BinOpInstr


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        ("Value", "Value"),
        ("list[Value]", "Value"),
        ("Value | None", "Value"),
        ("list[Value] | None", "Value"),
        ("int", "int"),
    ],
)
def test_sort_of_strips_container_and_optionality(
    annotation: str, expected: str
) -> None:
    assert sort_of(annotation) == expected
