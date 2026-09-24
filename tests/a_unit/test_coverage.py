"""Measuring a dispatch table against a grammar."""

from __future__ import annotations

import ast
from functools import singledispatch

import pytest

from astero.coverage import Coverage, dispatch, handlers, visitors
from astero.python import PY


def _registry(*classes: type):
    @singledispatch
    def gen(node): ...

    for cls in classes:
        gen.register(cls, lambda _node: None)
    return gen.registry


def test_handlers_ignores_the_object_fallback() -> None:
    assert handlers([_registry(ast.Assign, ast.Expr)]) == {"Assign", "Expr"}


def test_missing_is_what_can_appear_and_has_no_handler() -> None:
    cover = dispatch(PY, [_registry(ast.Assign)], bases=("stmt",))
    assert "Assign" not in cover.missing
    assert "Return" in cover.missing
    assert "BinOp" not in cover.missing, "an expression is not a statement's job"


def test_an_abstract_production_is_never_owed() -> None:
    cover = dispatch(PY, [_registry(ast.Assign)], bases=("stmt",))
    assert "stmt" not in cover.expected


def test_a_reason_excuses_a_production() -> None:
    cover = dispatch(
        PY,
        [_registry(ast.Assign)],
        bases=("stmt",),
        accounted={"desugared": {"AugAssign"}},
    )
    assert "AugAssign" not in cover.missing


def test_an_excuse_for_something_that_does_not_exist_is_reported() -> None:
    cover = dispatch(PY, [_registry()], bases=("stmt",), accounted={"why": {"Nope"}})
    assert cover.absent == {"Nope"}


def test_an_excuse_for_something_handled_is_reported() -> None:
    cover = dispatch(
        PY,
        [_registry(ast.Assign)],
        bases=("stmt",),
        accounted={"todo": {"Assign"}},
    )
    assert cover.redundant == {"Assign"}


def test_no_bases_means_the_whole_grammar() -> None:
    cover = dispatch(PY, [_registry(ast.Assign)])
    assert "Assign" in cover.expected
    assert "BinOp" in cover.expected
    assert "Load" in cover.expected


def test_explain_names_what_is_wrong() -> None:
    cover = dispatch(
        PY,
        [_registry(ast.Assign)],
        bases=("stmt",),
        accounted={"todo": {"Nope", "Assign"}},
    )
    text = cover.explain()
    assert "no handler and no reason" in text
    assert "not a production here" in text
    assert "handled anyway" in text


def test_a_complete_dispatcher_reports_nothing_missing() -> None:
    classes = [PY[name].cls for name in PY.concrete("stmt")]
    assert all(cls is not None for cls in classes)
    complete = _registry(*(cls for cls in classes if cls is not None))
    cover = dispatch(PY, [complete], bases=("stmt",))
    assert not cover.missing
    assert not cover.absent
    assert cover.explain().startswith(f"{len(cover.expected)} of {len(cover.expected)}")


def test_coverage_can_be_built_directly() -> None:
    cover = Coverage(handled=frozenset({"a"}), expected=frozenset({"a", "b"}))
    assert cover.missing == {"b"}
    assert cover.excused == frozenset()


@pytest.mark.parametrize("base", ["stmt", "expr"])
def test_bases_partition_what_is_owed(base: str) -> None:
    cover = dispatch(PY, [_registry()], bases=(base,))
    assert cover.expected == PY.concrete(base)


# ---------------------------------------------------------------------------
# `match` over node types, the enumeration `handlers` cannot read
# ---------------------------------------------------------------------------


def _emit_one(node):
    match node:
        case ast.Assign():
            return "assign"
        case ast.Return() | ast.Delete():
            return "return-or-delete"
        case ast.Constant(value=float()):
            return "float const"
        case ast.Pass() as stmt:
            return f"pass {stmt}"
        case _:
            return None


def _emit_more(node):
    match node:
        case Expr():
            return "expr"


class Expr:
    pass


def test_match_arms_reads_the_patterns_back() -> None:
    from astero.coverage import match_arms

    assert match_arms(_emit_one) == frozenset({
        "Assign",
        "Return",
        "Delete",
        "Constant",
        "Pass",
    })


def test_a_nested_pattern_is_a_condition_not_a_dispatch() -> None:
    """`case Constant(value=float())` handles `Constant`, not `float`."""
    from astero.coverage import match_arms

    assert "float" not in match_arms(_emit_one)


def test_a_wildcard_arm_handles_nothing_by_name() -> None:
    """A fallback is not coverage, which is the whole point of asking."""
    from astero.coverage import match_arms

    assert "_" not in match_arms(_emit_one)


def test_a_dotted_name_and_a_bare_one_are_the_same_production() -> None:
    from astero.coverage import match_arms

    assert match_arms(_emit_more) == frozenset({"Expr"})


def test_several_functions_are_one_table() -> None:
    from astero.coverage import match_arms

    assert match_arms(_emit_one, _emit_more) == match_arms(_emit_one) | match_arms(
        _emit_more
    )


# ---------------------------------------------------------------------------
# visitors
#
# The third way a consumer enumerates a language. `handlers` reads a
# `singledispatch` registry and `match_arms` reads `case` patterns; a
# `NodeVisitor`'s method names are a table neither can see, and all four
# consumers dispatch that way.
# ---------------------------------------------------------------------------


class _Expressions(ast.NodeVisitor):
    def visit_Name(self, node): ...
    def visit_BinOp(self, node): ...
    def generic_visit(self, node): ...


class _Statements(ast.NodeVisitor):
    def visit_Assign(self, node): ...


class _More(_Expressions):
    def visit_Call(self, node): ...


def test_it_reads_the_method_names_as_a_table() -> None:
    assert visitors(_Expressions) == frozenset({"Name", "BinOp"})


def test_generic_visit_is_a_fallback_and_not_a_production() -> None:
    assert "generic_visit" not in visitors(_Expressions)
    assert "" not in visitors(_Expressions)


def test_several_classes_that_divide_the_grammar() -> None:
    assert visitors(_Expressions, _Statements) == frozenset({"Name", "BinOp", "Assign"})


def test_a_consumers_own_base_class_still_counts() -> None:
    assert visitors(_More) == frozenset({"Name", "BinOp", "Call"})


def test_the_framework_shim_is_not_counted() -> None:
    """A class that does not handle `Constant` never reports handling it.

    `ast.NodeVisitor` defined `visit_Constant` through 3.13, the shim that
    routed the constant nodes 3.8 folded together, and CPython dropped it in
    3.14. So `dir()` answers this differently depending on the interpreter,
    and a gate built on it would certify a production nobody wrote on one
    version and stop on the next. Reading the MRO answers the same
    everywhere, which is what this pins.
    """
    assert "Constant" not in visitors(_Expressions)
    assert "Constant" not in visitors(_Statements, _More)


def test_only_node_visitor_supplies_a_visit_method() -> None:
    """The fact `_FRAMEWORK_BASES` encodes, gated against `ast`.

    The exclusion tuple names one class, not three: `ast.NodeTransformer`
    and `object` are in every consumer's MRO and neither defines a `visit_`
    method of its own, so listing them said nothing. That is a claim about
    CPython, so it is checked against CPython — a version that gives either
    of them one fails here, pointing at the tuple, rather than letting a
    consumer inherit a production it never wrote.
    """
    assert not [n for n in vars(ast.NodeTransformer) if n.startswith("visit_")]
    assert not [n for n in vars(object) if n.startswith("visit_")]


def test_a_class_that_defines_visit_constant_itself_does_count() -> None:
    class Owns(ast.NodeVisitor):
        def visit_Constant(self, node): ...

    assert visitors(Owns) == frozenset({"Constant"})


def test_it_measures_against_a_grammar_like_the_other_two_readers() -> None:
    cover = Coverage(
        handled=visitors(_Expressions, _Statements),
        expected=frozenset({"Name", "BinOp", "Assign", "Call"}),
    )
    assert cover.missing == frozenset({"Call"})
