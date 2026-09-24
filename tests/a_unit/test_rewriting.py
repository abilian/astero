"""Tests for astero.python.rewriting."""

from __future__ import annotations

import ast
import re
import sys
from typing import cast

import pytest

from astero.python import rewriting


def _expr(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


def _assert_same(observed: ast.AST, expected: str) -> None:
    assert rewriting.key(observed) == rewriting.key(_expr(expected))


def test_metavariable_binds_expression() -> None:
    p = rewriting.Pass("t", rewriting.rules("_x + 0 => _x"))
    _assert_same(p(_expr("(a + 0) * (b + 0)")), "a * b")


def test_metavariable_is_nonlinear() -> None:
    p = rewriting.Pass("t", rewriting.rules("_x - _x => 0"))
    _assert_same(p(_expr("f(1) - f(1)")), "0")
    _assert_same(p(_expr("f(1) - f(2)")), "f(1) - f(2)")


def test_wildcard_matches_without_binding() -> None:
    p = rewriting.Pass("t", rewriting.rules("f(_, _) => 0"))
    _assert_same(p(_expr("f(1, 2)")), "0")
    _assert_same(p(_expr("f(1, 1)")), "0")
    _assert_same(p(_expr("f(1)")), "f(1)")


def test_starred_metavariable_binds_rest_of_list() -> None:
    binds = rewriting.match(_expr("f(1, *_xs)"), _expr("f(1, 2, 3)"))
    assert binds is not None
    assert [ast.unparse(x) for x in binds["_xs"]] == ["2", "3"]


def test_keyword_wildcard_leaves_keywords_unconstrained() -> None:
    loose = rewriting.Pass("t", rewriting.rules("f(_x, **_) => g(_x)"))
    _assert_same(loose(_expr("f(1)")), "g(1)")
    _assert_same(loose(_expr("f(1, key=2)")), "g(1)")

    strict = rewriting.Pass("t", rewriting.rules("f(_x) => g(_x)"))
    _assert_same(strict(_expr("f(1)")), "g(1)")
    _assert_same(strict(_expr("f(1, key=2)")), "f(1, key=2)")


def test_metavariable_in_identifier_field() -> None:
    p = rewriting.Pass(
        "t", rewriting.rules("math._f => _f"), rewriting.Strategy.OUTERMOST
    )
    _assert_same(p(_expr("math.sqrt(math.pi)")), "sqrt(pi)")


def test_abstract_term_constrains_only_named_fields() -> None:
    p = rewriting.Pass("t", rewriting.rules('ast.Call(ast.Name("f")) => g()'))
    _assert_same(p(_expr("f(1, 2, key=3)")), "g()")
    _assert_same(p(_expr("h(1)")), "h(1)")


def test_abstract_term_fields_are_positional_or_keyword() -> None:
    positional = rewriting.rule("ast.BinOp(_a, ast.Add(), _b) => _b")
    by_name = rewriting.rule("ast.BinOp(left=_a, op=ast.Add(), right=_b) => _b")
    for r in (positional, by_name):
        p = rewriting.Pass("t", (r,))
        _assert_same(p(_expr("1 + 2")), "2")
        _assert_same(p(_expr("1 - 2")), "1 - 2")


def test_abstract_term_rejects_too_many_positional_fields() -> None:
    with pytest.raises(ValueError, match=r"ast.Name has fields"):
        rewriting.rule("ast.Name(_a, _b, _c) => _a")


def test_abstract_term_rebuilds_a_node() -> None:
    p = rewriting.Pass(
        "t",
        rewriting.rules(
            "ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"
        ),
        eliminates=(ast.AugAssign,),
    )
    assert rewriting.key(p(ast.parse("x @= y"))) == rewriting.key(
        ast.parse("x = x @ y")
    )


def test_contexts_are_recomputed_not_written() -> None:
    p = rewriting.Pass(
        "t",
        rewriting.rules(
            "ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"
        ),
    )
    assign = p(ast.parse("x += y")).body[0]
    assert isinstance(assign.targets[0].ctx, ast.Store)
    assert isinstance(assign.value.left.ctx, ast.Load)


def test_rules_block_skips_blanks_and_comments() -> None:
    block = rewriting.rules("""
        # doubling
        f(_x) => g(_x)

        g(_x) => h(_x)
        """)
    assert [str(r) for r in block] == ["f(_x) => g(_x)", "g(_x) => h(_x)"]


def test_arrow_split_skips_arrows_inside_the_pattern() -> None:
    r = rewriting.rule("f('=>') => g()")
    assert (r.lhs_text, r.rhs_text) == ("f('=>')", "g()")


def test_delete_drops_a_list_element() -> None:
    p = rewriting.Pass("t", (rewriting.rule("pass", rewriting.DELETE),))
    out = p(ast.parse("def f():\n    pass\n    return 1"))
    assert len(out.body[0].body) == 1


def test_delete_outside_a_list_is_rejected() -> None:
    p = rewriting.Pass("t", (rewriting.rule("ast.Name()", rewriting.DELETE),))
    with pytest.raises(ValueError, match="cannot delete Name"):
        p(_expr("f.x"))  # Attribute.value holds one node, not a list


def test_strategies_differ() -> None:
    trim = rewriting.rules("a._f => _f")
    _assert_same(
        rewriting.Pass("t", trim, rewriting.Strategy.OUTERMOST)(_expr("a.b.c")), "b.c"
    )
    _assert_same(
        rewriting.Pass("t", trim, rewriting.Strategy.INNERMOST)(_expr("a.b.c")), "b.c"
    )

    # Only INNERMOST renormalizes a replacement until nothing fires.
    grow = rewriting.rules("""
        f(_x) => g(_x)
        g(_x) => h(_x)
        """)
    _assert_same(rewriting.Pass("t", grow)(_expr("f(1)")), "h(1)")
    _assert_same(
        rewriting.Pass("t", grow, rewriting.Strategy.OUTERMOST)(_expr("f(1)")), "g(1)"
    )


def test_environment_reaches_guards_and_replacements() -> None:
    def is_bound(m: rewriting.Match) -> bool:
        return bool(m.env) and m.binds["_v"] in m.env

    p = rewriting.Pass(
        "t",
        (
            rewriting.rule(
                "ast.Name(_v)", lambda m: m.env[m.binds["_v"]], when=is_bound
            ),
        ),
        rewriting.Strategy.OUTERMOST,
    )
    _assert_same(p(_expr("x + y"), {"x": _expr("2 * z")}), "2 * z + y")


def test_cyclic_rule_set_is_reported() -> None:
    p = rewriting.Pass(
        "t",
        rewriting.rules("""
            _x + 1 => 1 + _x
            1 + _x => _x + 1
            """),
    )
    with pytest.raises(RecursionError, match="cyclic"):
        p(_expr("a + 1"))


def test_postcondition_is_checked() -> None:
    p = rewriting.Pass("t", (), eliminates=(ast.AugAssign,))
    with pytest.raises(AssertionError, match="left 1 AugAssign"):
        p(ast.parse("x += 1"))


def test_rule_sides_must_agree_on_sort() -> None:
    with pytest.raises(ValueError, match="statement rule needs a statement"):
        rewriting.rule("x = 1 => x")
    with pytest.raises(ValueError, match="expression rule needs an expression"):
        rewriting.rule("x => y = 1")


def test_rule_needs_an_arrow() -> None:
    with pytest.raises(ValueError, match="needs a '=>' separator"):
        rewriting.rule("f(_x)")


def test_a_malformed_half_is_reported_as_a_syntax_error() -> None:
    with pytest.raises(ValueError, match=r"cannot parse 'i\(_x'"):
        rewriting.rule("h(_x) => i(_x")
    # The intended split is the one whose left side parses, not the first `=>`.
    with pytest.raises(ValueError, match=r"cannot parse 'g\('"):
        rewriting.rule("f('=>') => g(")


def test_pattern_must_be_a_single_expression() -> None:
    with pytest.raises(ValueError, match="single statement or expression"):
        rewriting.rule("x = 1\ny = 2", "x")


def test_two_splices_in_one_list_are_rejected() -> None:
    with pytest.raises(ValueError, match=r"at most one `\*` or `\*\*` pattern"):
        rewriting.rule("f(*_xs, *_ys) => g()")


def test_unknown_ast_class_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"unknown AST class: ast\.Nope"):
        rewriting.rule("ast.Nope() => x")


def test_rule_records_where_it_was_written() -> None:
    r = rewriting.rule("f(_x) => g(_x)")
    assert re.fullmatch(r"test_rewriting\.py:\d+", r.origin)


def test_compile_errors_name_the_call_site() -> None:
    with pytest.raises(ValueError, match=r"^test_rewriting\.py:\d+: unknown AST"):
        rewriting.rule("ast.Nope() => x")


def test_compile_errors_name_the_line_within_a_block() -> None:
    with pytest.raises(ValueError, match=r"block line 3: unknown AST class"):
        rewriting.rules("""
            f(_x) => g(_x)
            ast.Nope() => x
            """)


def test_block_rules_record_their_line() -> None:
    block = rewriting.rules("""
        f(_x) => g(_x)
        g(_x) => h(_x)
        """)
    assert [r.origin.split(" block ")[1] for r in block] == ["line 2", "line 3"]


def test_passes_print_their_rules() -> None:
    def is_zero(m: rewriting.Match) -> bool:
        return True

    p = rewriting.Pass(
        "demo",
        (
            *rewriting.rules("""
                hypot(_x, _y) => sqrt(_x ** 2 + _y ** 2)
                exp(_x)       => e ** _x
                """),
            rewriting.rule("ast.Expr(ast.Constant(_s))", rewriting.DELETE, is_zero),
        ),
        rewriting.Strategy.OUTERMOST,
        eliminates=(ast.AugAssign,),
    )
    assert str(p) == (
        "pass demo  [outermost, 3 rules]\n"
        "  eliminates AugAssign\n"
        "   1. hypot(_x, _y)              => sqrt(_x ** 2 + _y ** 2)\n"
        "   2. exp(_x)                    => e ** _x\n"
        "   3. ast.Expr(ast.Constant(_s)) => (delete)  if is_zero"
    )
    assert repr(p) == "<Pass demo: 3 rules, outermost>"
    assert str(p.rules[1]) == "exp(_x) => e ** _x"


def test_ctx_nodes_matches_the_grammar() -> None:
    """`CTX_NODES` is authored so type checkers can narrow. This is its gate."""
    derived = {
        c
        for c in vars(ast).values()
        if isinstance(c, type) and issubclass(c, ast.AST) and "ctx" in c._fields
    }
    assert set(rewriting.CTX_NODES) == derived


def test_ast_classes_covers_the_grammar() -> None:
    derived = {
        name
        for name, c in vars(ast).items()
        if isinstance(c, type) and issubclass(c, ast.AST)
    }
    assert set(rewriting.AST_CLASSES) == derived


def test_target_positions_come_from_the_grammar() -> None:
    """The engine and the declared grammar cannot disagree about targets.

    This was a hand-written table, and it fell behind Python 3.12: `TypeAlias`
    was missing, so `type X = int` came out with a Load context. Deriving it
    means a production the grammar knows about cannot be missed here.
    """
    from astero.grammar import Kind
    from astero.python import PY, VARS

    derived = rewriting.target_fields(PY)
    declared = PY.positions((Kind.DEF, Kind.DEFUSE), VARS) | PY.positions(
        Kind.DEL, VARS
    )
    assert set(derived) == set(declared)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="needs Python 3.12+")
def test_a_type_alias_binds_its_name() -> None:
    # The `if` repeats the `skipif` above: a decorator does not narrow
    # `ast.TypeAlias`, which does not exist before 3.12.
    if sys.version_info >= (3, 12):
        tree = ast.parse("type X = int")
        rewriting.fix_contexts(tree)
        alias = tree.body[0]
        assert isinstance(alias, ast.TypeAlias)
        assert isinstance(alias.name.ctx, ast.Store)


def test_rewrite_declares_a_rule_on_the_function_that_performs_it() -> None:
    """The pattern belongs next to the code, not in a list pointing at a name."""

    @rewriting.rewrite("ast.BoolOp(_o, _v)")
    def nest(m: rewriting.Match) -> ast.AST | None:
        node = cast("ast.BoolOp", m.node)
        values = list(node.values)
        if len(values) <= 2:
            # Without this the rule rewrites its own result forever, which is
            # what the fixpoint strategy is entitled to assume it will not do.
            return None
        right = values.pop()
        while len(values) > 1:
            right = ast.BoolOp(op=node.op, values=[values.pop(), right])
        return ast.BoolOp(op=node.op, values=[values[0], right])

    assert isinstance(nest, rewriting.Rule)
    assert str(nest) == "ast.BoolOp(_o, _v) => nest"
    p = rewriting.Pass("t", (nest,))
    assert ast.unparse(p(ast.parse("a and b and c"))) == "a and (b and c)"


def test_a_callable_replacement_declines_by_returning_none() -> None:
    """Declining falls through to the next rule, as a False guard does."""

    @rewriting.rewrite("f(_x)")
    def only_zero(m: rewriting.Match) -> ast.AST | None:
        arg = m.binds["_x"]
        if not (isinstance(arg, ast.Constant) and arg.value == 0):
            return None
        return ast.Name(id="zero", ctx=ast.Load())

    p = rewriting.Pass("t", rewriting.rules("f(_y) => g(_y)", only_zero))
    # The block rule is tried first and matches everything, so put the
    # declining rule first to see the fall-through.
    q = rewriting.Pass("t", (only_zero, *rewriting.rules("f(_y) => g(_y)")))
    assert ast.unparse(p(ast.parse("f(0)"))) == "g(0)"
    assert ast.unparse(q(ast.parse("f(0)"))) == "zero"
    assert ast.unparse(q(ast.parse("f(1)"))) == "g(1)"


def test_rules_takes_compiled_rules_after_its_block() -> None:
    @rewriting.rewrite("h(_x)")
    def to_k(m: rewriting.Match) -> ast.AST:
        return ast.Name(id="k", ctx=ast.Load())

    got = rewriting.rules(
        """
        f(_x) => g(_x)
        p(_x) => q(_x)
        """,
        to_k,
    )
    assert [r.lhs_text for r in got] == ["f(_x)", "p(_x)", "h(_x)"]
    assert got[-1] is to_k


def test_a_declining_rule_leaves_the_node_alone_when_nothing_else_matches() -> None:
    @rewriting.rewrite("f(_x)")
    def never(m: rewriting.Match) -> ast.AST | None:
        return None

    p = rewriting.Pass("t", (never,))
    assert ast.unparse(p(ast.parse("f(1)"))) == "f(1)"


# ---------------------------------------------------------------------------
# A rule that answers with several statements, and one that stops at a scope
# ---------------------------------------------------------------------------
#
# Both came from p2w's `transform_yield_from`, which is a rewrite the engine
# could not express: `val = yield from it` is a loop *and* an assignment, and
# a `yield from` inside a nested function belongs to that generator.


def _two_statements(m):
    """Answer one `Expr(Constant('split'))` with two statements."""
    return [ast.parse("a = 1").body[0], ast.parse("b = 2").body[0]]


def _split_pass():
    from astero.python import PY

    rule = rewriting.rewrite("ast.Expr(ast.Constant('split'))")(_two_statements)
    return rewriting.Pass("split", (rule,), grammar=PY)


def test_a_rule_may_answer_with_several_statements() -> None:
    out = _split_pass()(ast.parse("x = 0\n'split'\ny = 3\n"))
    assert ast.unparse(out).splitlines() == ["x = 0", "a = 1", "b = 2", "y = 3"]


def test_several_statements_in_a_single_slot_is_an_error() -> None:
    """A list can only be spliced into a field that holds a list.

    An `if` body is a list and its `test` is not, so a rule answering an
    expression with two nodes has nowhere to put them.
    """
    from astero.python import PY

    rule = rewriting.rewrite("ast.Name('q')")(
        lambda _m: [ast.Name(id="a"), ast.Name(id="b")]
    )
    bad = rewriting.Pass("bad", (rule,), grammar=PY)
    with pytest.raises(TypeError, match="holds one"):
        bad(ast.parse("y = q\n"))


def test_a_pass_can_decline_to_enter_a_scope() -> None:
    from astero.python import PY

    renamer = rewriting.Pass(
        "rename",
        rewriting.rules("ast.Name('q') => ast.Name('z')"),
        grammar=PY,
        stop_at=(ast.FunctionDef, ast.Lambda),
    )
    out = renamer(ast.parse("q\ndef f():\n    return q\nlambda: q\n"))
    text = ast.unparse(out)
    assert text.splitlines()[0] == "z", text
    assert "return q" in text, "the rewrite entered the function"
    assert "lambda: q" in text, "the rewrite entered the lambda"


def test_stop_at_skips_the_boundary_node() -> None:
    """`stop_at` skips a production whole, rather than entering it.

    The docstring said the boundary node was "still offered to the rules",
    and it is not: `_rewrite_slots` skips it before `run` sees it. Both
    halves are pinned here so the two cannot drift apart again.
    """
    from astero.python import PY, Pass, rules

    swap = rules("ast.FunctionDef(_n, _a, _b, _d) => ast.Pass()")
    guarded = Pass("guarded", swap, grammar=PY, stop_at=(ast.FunctionDef,))

    # Reached through a parent: skipped, so the rule never fires.
    tree = ast.parse("def f():\n    pass\n")
    assert "def f" in ast.unparse(guarded(tree))

    # Called on the boundary node itself: offered, because the traversal has
    # not started descending yet.
    assert ast.unparse(guarded(ast.parse("def f():\n    pass\n").body[0])) == "pass"

    # Without stop_at the same rule does fire through the parent.
    plain = Pass("plain", swap, grammar=PY)
    assert "def f" not in ast.unparse(plain(ast.parse("def f():\n    pass\n")))
