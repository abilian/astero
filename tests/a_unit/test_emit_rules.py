"""Emission as a declaration: templates, guards, and derived brackets."""

from __future__ import annotations

import ast

import pytest

from astero.emit import Assoc, Level
from astero.emit_rules import (
    All,
    Both,
    Const,
    Either,
    EmitError,
    Emitter,
    Has,
    Is,
    Not,
    OpIs,
)
from astero.python import PY

LEVELS: dict[type[ast.AST], Level] = {
    ast.Or: Level(4),
    ast.And: Level(5),
    ast.Eq: Level(9, Assoc.NONE),
    ast.Lt: Level(10, Assoc.NONE),
    ast.Add: Level(12),
    ast.Sub: Level(12),
    ast.Mult: Level(13),
}
SYM: dict[type[ast.AST], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Lt: "<",
    ast.Eq: "===",
}


def _js(typer=None) -> Emitter:
    e = Emitter(PY, levels=LEVELS, typer=typer)
    e.projection("sym", lambda op: SYM[type(op)])
    e.projection("name", str)
    e.projection("lit", repr)
    e.rule("BinOp", "{left} {op:sym} {right}")
    e.rule("Compare", "{left} {ops:sym} {comparators}")
    e.rule("BoolOp", "{values: && }", OpIs((ast.And,)))
    e.rule("BoolOp", "{values: || }", OpIs((ast.Or,)))
    e.rule("Call", "{func}({args:, })")
    e.rule("Subscript", "{value}[{slice}]")
    e.rule("Name", "{id:name}")
    e.rule("Constant", "{value:lit}")
    return e


def _body(source: str) -> list[ast.stmt]:
    """The body of the one function in `source`.

    `ast.parse(...).body[0]` is a `stmt`, and a `stmt` has no `body`:
    only some of them do. Asserting which keeps that out of every test.
    """
    fn = ast.parse(source).body[0]
    assert isinstance(fn, ast.FunctionDef)
    return fn.body


def _out(source: str, emitter: Emitter | None = None) -> str:
    return (emitter or _js()).to_text(ast.parse(source, mode="eval").body)


# ------------------------------------------------------------- bracketing


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("a + b * c", "a + b * c"),
        ("(a + b) * c", "(a + b) * c"),
        ("a - b - c", "a - b - c"),
        ("a - (b - c)", "a - (b - c)"),
        ("a + b < c", "a + b < c"),
        ("a * (b + c)", "a * (b + c)"),
    ],
)
def test_brackets_come_from_the_precedence_table(source: str, expected: str) -> None:
    """No rule mentions a bracket. They are derived, as in `emit`."""
    assert _out(source) == expected


@pytest.mark.parametrize("source", ["f(a + b, c)", "x[a + b]"])
def test_a_hole_the_template_delimits_is_not_bracketed(source: str) -> None:
    """`f({args:, })` already separates them, so an argument binds freely."""
    assert _out(source) == source


def test_a_target_without_precedence_never_brackets() -> None:
    """WebAssembly text is self-bracketing, so the table is optional."""
    wat = Emitter(PY, levels=None)
    wat.projection("sym", lambda op: {ast.Add: "i32.add"}[type(op)])
    wat.projection("name", str)
    wat.rule("BinOp", "({op:sym} {left} {right})")
    wat.rule("Name", "(local.get ${id:name})")
    assert wat.to_text(ast.parse("a + b", mode="eval").body) == (
        "(i32.add (local.get $a) (local.get $b))"
    )


# ------------------------------------------------------------------ guards


def test_the_first_rule_whose_guard_holds_wins() -> None:
    assert _out("a and b") == "a && b"
    assert _out("a or b") == "a || b"


def test_a_rule_without_a_guard_is_the_fallback() -> None:
    e = _js()
    e.rule("UnaryOp", "!{operand}")
    assert _out("not a", e) == "!a"


def test_a_production_with_no_applicable_rule_is_an_error() -> None:
    with pytest.raises(EmitError, match="no rule for Lambda"):
        _out("lambda: 1")


def test_guards_read_the_declared_type() -> None:
    types: dict[str | None, type] = {"s": str, "n": int}
    e = _js(typer=lambda node: types.get(getattr(node, "id", None)))
    e.rules.insert(0, e.rules[0])  # keep list identity simple
    e.rules.clear()
    e.rule(
        "BinOp", "{left}.repeat({right})", All((OpIs((ast.Mult,)), Is("left", (str,))))
    )
    e.rule("BinOp", "{left} {op:sym} {right}")
    e.rule("Name", "{id:name}")
    assert _out("s * n", e) == "s.repeat(n)"
    assert _out("n * n", e) == "n * n"


def test_both_either_all_and_not_compose() -> None:
    types: dict[str | None, type] = {"a": int, "b": str}
    e = Emitter(PY, levels=LEVELS, typer=lambda n: types.get(getattr(n, "id", None)))
    e.projection("name", str)
    e.rule("BinOp", "SAME({left}, {right})", Both((int,)))
    e.rule(
        "BinOp",
        "EITHER({left}, {right})",
        Either((Is("left", (str,)), Is("right", (str,)))),
    )
    e.rule("BinOp", "NEITHER({left}, {right})", Not(Both((int,))))
    e.rule("Name", "{id:name}")
    assert _out("a + a", e) == "SAME(a, a)"
    assert _out("a + b", e) == "EITHER(a, b)"


def test_const_recognises_a_literal() -> None:
    e = _js()
    e.rules.clear()
    e.rule(
        "BinOp", "FMT({left}, {right})", All((OpIs((ast.Mod,)), Const("left", of=str)))
    )
    e.rule("BinOp", "MOD({left}, {right})")
    e.rule("Name", "{id:name}")
    e.rule("Constant", "{value:lit}")
    assert _out("'x%d' % n", e).startswith("FMT(")
    assert _out("a % n", e).startswith("MOD(")


# ---------------------------------------------------------------- templates


def test_a_template_naming_an_absent_field_is_rejected_at_declaration() -> None:
    e = Emitter(PY, levels=LEVELS)
    with pytest.raises(EmitError, match="BinOp has no field 'nope'"):
        e.rule("BinOp", "{nope}")


def test_a_rule_for_an_unknown_production_is_rejected() -> None:
    e = Emitter(PY, levels=LEVELS)
    with pytest.raises(EmitError, match="no production 'Nope'"):
        e.rule("Nope", "x")


def test_an_optional_hole_disappears_when_absent() -> None:
    e = Emitter(PY, levels=LEVELS)
    e.projection("name", str)
    e.rule("Return", "return {value?};")
    e.rule("Name", "{id:name}")
    assert e.to_text(_body("def f():\n    return a")[0]) == "return a;"
    assert e.to_text(_body("def f():\n    return")[0]) == "return ;"


def test_a_projection_over_a_sequence_maps() -> None:
    """`{ops:sym}` spells each operator, not the list."""
    assert _out("a < b") == "a < b"


def test_covered_reports_the_productions_with_rules() -> None:
    assert {"BinOp", "Compare", "Call"} <= _js().covered()


def test_has_asks_what_present_asks_in_the_grammar() -> None:
    """`yield x` and `yield` are two spellings, not one with an empty hole."""
    e = Emitter(PY, levels=LEVELS)
    e.projection("name", str)
    e.rule("Yield", "yield {value}", Has("value"))
    e.rule("Yield", "yield")
    e.rule("Name", "{id:name}")
    body = _body("def f():\n    yield a\n    yield")
    assert all(isinstance(stmt, ast.Expr) for stmt in body)
    yields = [stmt.value for stmt in body if isinstance(stmt, ast.Expr)]
    assert e.to_text(yields[0]) == "yield a"
    assert e.to_text(yields[1]) == "yield"


def test_a_literal_brace_is_written_doubled() -> None:
    """A target with object literals needs an escape, as `str.format` has."""
    e = Emitter(PY, levels=None)
    e.projection("lit", repr)
    e.rule("List", "Object.assign([{elts:, }], {{_is_list: true}})")
    e.rule("Constant", "{value:lit}")
    assert e.to_text(ast.parse("[1, 2]", mode="eval").body) == (
        "Object.assign([1, 2], {_is_list: true})"
    )


def test_a_template_operator_brackets_its_own_holes() -> None:
    """`Math.floor({left}/{right})` has a `/` the declaration must level.

    The result is an atom, the holes sit either side of a division, and those
    are three different levels. Conflating them emitted `Math.floor(a - b/2)`.
    """
    levels = dict(LEVELS)
    levels[ast.FloorDiv] = Level(13)
    e = Emitter(PY, levels=levels)
    e.projection("name", str)
    e.projection("lit", repr)
    e.rule("BinOp", "Math.floor({left}/{right})", OpIs((ast.FloorDiv,)))
    e.rule("BinOp", "{left} {op:sym} {right}")
    e.projection("sym", lambda op: SYM[type(op)])
    e.rule("Name", "{id:name}")
    e.rule("Constant", "{value:lit}")
    assert _out("(a - b) // 2", e) == "Math.floor((a - b)/2)"
    # And the call is an atom, so a parent does not bracket it.
    assert _out("(a - b) // 2 - c", e) == "Math.floor((a - b)/2) - c"


def test_a_separator_delimits_but_an_operator_does_not() -> None:
    e = Emitter(PY, levels=LEVELS)
    e.projection("name", str)
    e.projection("lit", repr)
    e.rule("Call", "f({args:, })")
    e.rule("BinOp", "{left} {op:sym} {right}")
    e.projection("sym", lambda op: SYM[type(op)])
    e.rule("Name", "{id:name}")
    e.rule("Constant", "{value:lit}")
    assert _out("f(a + b, c)", e) == "f(a + b, c)"


# ------------------------------------------------------- a second target


def test_folded_s_expressions_need_no_precedence_table() -> None:
    """WebAssembly text, in its folded form. Every construct self-brackets."""
    wat = Emitter(PY, levels=None)
    wat.projection("name", lambda v: f"$var_{v}")
    wat.projection("lit", lambda v: f"(ref.i31 (i32.const {v}))")
    wat.projection("fn", lambda op: {ast.Add: "add", ast.Mult: "mul"}[type(op)])
    wat.rule("BinOp", "(call ${op:fn} {left} {right})")
    wat.rule("Name", "(local.get {id:name})")
    wat.rule("Constant", "{value:lit}")
    assert wat.to_text(ast.parse("a + b * 2", mode="eval").body) == (
        "(call $add (local.get $var_a) "
        "(call $mul (local.get $var_b) (ref.i31 (i32.const 2))))"
    )


def test_a_flat_stack_sequence_is_reachable_after_all() -> None:
    """What p2w emits: post-order instructions, not nested text.

    A template composes a child's text into the parent's, which looked like it
    meant nesting. It does not. Put the operator after both holes and the
    composition *is* post-order, which is exactly what a stack machine wants:

        local.get $a
        local.get $b
        i32.const 2
        i32.mul
        i32.add

    The generated module validates with `wasm-tools` and returns what Python
    returns, checked by hand at the time this was written.
    """
    wat = Emitter(PY, levels=None)
    wat.projection("name", lambda v: "$" + str(v))
    wat.projection("lit", lambda v: "i32.const " + str(v))
    wat.projection("op", lambda o: {ast.Add: "add", ast.Mult: "mul"}[type(o)])
    wat.rule("BinOp", "{left}\n{right}\ni32.{op:op}")
    wat.rule("Name", "local.get {id:name}")
    wat.rule("Constant", "{value:lit}")

    out = wat.to_text(ast.parse("a + b * 2", mode="eval").body)
    assert out.splitlines() == [
        "local.get $a",
        "local.get $b",
        "i32.const 2",
        "i32.mul",
        "i32.add",
    ]

    # Nested on both sides, where post-order matters most: each `mul` follows
    # its own operands rather than both trailing at the end.
    deep = wat.to_text(ast.parse("(a * 2) + (b * 2)", mode="eval").body)
    assert deep.splitlines() == [
        "local.get $a",
        "i32.const 2",
        "i32.mul",
        "local.get $b",
        "i32.const 2",
        "i32.mul",
        "i32.add",
    ]


# ---------------------------------------------------------------------------
# Two type systems, one guard vocabulary
# ---------------------------------------------------------------------------


class _InstanceType:
    """A type system whose `type_of` returns instances, as p2w's does."""

    def __eq__(self, other):
        return type(self) is type(other)

    def __hash__(self):
        return hash(type(self))


class FloatT(_InstanceType):
    pass


class IntT(_InstanceType):
    pass


class StrT(_InstanceType):
    pass


def test_a_guard_accepts_a_typer_that_returns_instances() -> None:
    """`Is`/`Both` compared with `in`, which is False for every instance.

    prescrypt-ng's `get_type` returns the class, so `Int in (Int, Float)` is
    the test and it worked. p2w's returns `FloatType()`, and nothing matched.
    """
    from astero.emit_rules import Both, Is

    node = ast.parse("a + b", mode="eval").body
    by_instance = Emitter(PY, typer=lambda _n: FloatT())
    assert Is("left", (FloatT, IntT)).holds(node, by_instance)
    assert Both((FloatT, IntT)).holds(node, by_instance)
    assert not Is("left", (StrT,)).holds(node, by_instance)


def test_a_typer_that_returns_classes_still_works() -> None:
    from astero.emit_rules import Both, Is

    node = ast.parse("a + b", mode="eval").body
    by_class = Emitter(PY, typer=lambda _n: FloatT)
    assert Is("left", (FloatT, IntT)).holds(node, by_class)
    assert Both((FloatT, IntT)).holds(node, by_class)
    assert not Both((StrT,)).holds(node, by_class)


# ---------------------------------------------------------------------------
# Labels, which are what a flat target was missing
# ---------------------------------------------------------------------------


def _stack_machine() -> Emitter:
    vm = Emitter(PY, levels=None)
    vm.projection("lit", str)
    vm.projection("name", str)
    vm.rule("Constant", "CONST {value:lit}")
    vm.rule("Name", "PUSH {id:name}")
    vm.rule("Assign", "{value}\nSTORE x")
    vm.rule("While", "{&top}:\n{test}\nJZ {&done}\n{body:\n}\nJMP {&top}\n{&done}:")
    return vm


def test_the_same_label_twice_in_one_template_is_one_label() -> None:
    out = (
        _stack_machine()
        .to_text(ast.parse("while x:\n    y = 1\n").body[0])
        .splitlines()
    )
    top = out[0].rstrip(":")
    assert out[-2] == f"JMP {top}"


def test_a_second_node_gets_a_different_label() -> None:
    vm = _stack_machine()
    first = vm.to_text(ast.parse("while a:\n    b = 1\n").body[0]).splitlines()[0]
    second = vm.to_text(ast.parse("while c:\n    d = 1\n").body[0]).splitlines()[0]
    assert first != second


def test_a_statement_list_renders_with_a_separator() -> None:
    """Statement *structure* needed nothing new; only labels did."""
    out = _stack_machine().to_text(
        ast.parse("while x:\n    y = 1\n    z = 2\n").body[0]
    )
    assert "CONST 1\nSTORE x\nCONST 2\nSTORE x" in out


def test_a_label_hole_is_not_checked_against_the_fields() -> None:
    """`{&done}` names a label, and `While` has no field called `done`."""
    Emitter(PY, levels=None).rule("While", "{&done}: {test}")


def test_to_lines_splits_where_the_template_said_to() -> None:
    """`to_text().splitlines()` is the obvious thing and it is unsound.

    A newline written in a template separates two emitted lines. A newline
    that arrives inside a value — a string literal — does not, and splitting
    the rendered text cannot tell them apart.
    """
    vm = Emitter(PY, levels=None)
    vm.projection("lit", lambda v: f'"{v}"')
    vm.rule("Constant", "CONST {value:lit}")
    vm.rule("Assign", "{value}\nSTORE x")

    node = ast.parse('s = "a\\nb"').body[0]
    assert vm.to_lines(node) == ['CONST "a\nb"', "STORE x"]
    assert vm.to_text(node).splitlines() == ['CONST "a', 'b"', "STORE x"]


def test_to_lines_and_to_text_agree_when_no_value_breaks() -> None:
    vm = _stack_machine()
    node = ast.parse("while x:\n    y = 1\n    z = 2\n").body[0]
    assert vm.to_lines(node) == vm.to_text(node).splitlines()


# ------------------------------------------ a production with no binding power


def _c() -> Emitter:
    """A structured target: statements, and a precedence table for expressions."""
    c = Emitter(PY, levels=LEVELS)
    c.projection("sym", lambda op: SYM[type(op)])
    c.projection("name", str)
    c.projection("lit", str)
    c.projection("target", lambda t: t.id)
    c.rule("BinOp", "{left} {op:sym} {right}")
    c.rule("Compare", "{left} {ops:sym} {comparators}")
    c.rule("Name", "{id:name}")
    c.rule("Constant", "{value:lit}")
    c.rule("Assign", "{targets:target} = {value};")
    c.rule("Return", "return {value};")
    c.rule("While", "while ({test}) {{ {body: } }}")
    return c


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("t = 0", "t = 0;"),
        ("t = a + b", "t = a + b;"),
        ("return n * 2", "return n * 2;"),
        ("while a < b: t = 1", "while (a < b) { t = 1; }"),
    ],
)
def test_a_statement_imposes_no_binding_power(source: str, expected: str) -> None:
    """A production the precedence table omits declares that it imposes none.

    `Assign` and `Return` are in no table, and the missing entry used to read
    as `ATOM` — the *tightest* context there is — so every statement bracketed
    its own operand: `t = (0);`, `return (n * 2);`. Undeclared is not a level.
    """
    assert _c().to_text(ast.parse(source).body[0]) == expected


def test_an_omitted_production_is_still_an_atom_as_a_child() -> None:
    """The other half of the same question, and it answers the other way.

    `level_of` and `inner_level` read the same missing entry: as a *child* a
    production the table omits is a primary, so `f(a) * b` brackets nothing.
    """
    assert _out("f(a) * b") == "f(a) * b"
    assert _out("x[i] - 1") == "x[i] - 1"


# ---------------------------------------------------------------------------
# Source maps
#
# `emit.spans` walked a document and nothing built one with spans in it, so
# the layer existed and was unreachable. Every rule's output now carries the
# position of the node it emitted, which needs no cooperation from the rules
# and no extra hole in the template.
# ---------------------------------------------------------------------------


def _mapped(source: str, emitter: Emitter) -> list[tuple[str, str]]:
    """(emitted fragment, the source text at the position it maps to)."""
    tree = ast.parse(source, mode="eval").body
    out = emitter.to_text(tree)
    lines = source.split("\n")
    pairs = []
    for start, end, (line, col) in emitter.source_map(tree):
        fragment = out[start:end]
        pairs.append((fragment, lines[line - 1][col : col + len(fragment)]))
    return pairs


def test_every_fragment_maps_to_where_it_came_from() -> None:
    """The property a source map has to have: follow the position and find
    the text that produced the fragment."""
    e = _js()
    e.rule("BinOp", "{left} {op:sym} {right}")
    e.rule("Name", "{id:name}")
    e.rule("Constant", "{value:name}")
    for fragment, origin in _mapped("alpha + beta * 3", e):
        assert fragment == origin, (fragment, origin)


def test_it_holds_when_the_emitter_adds_its_own_brackets() -> None:
    """Brackets come from the precedence table, not from the tree, so the
    offsets after one have shifted relative to any naive count."""
    e = _js()
    e.rule("BinOp", "{left} {op:sym} {right}")
    e.rule("Name", "{id:name}")
    for fragment, origin in _mapped("(a + b) * c", e):
        assert fragment == origin, (fragment, origin)


def test_a_node_the_host_built_carries_no_position() -> None:
    """A synthesized node has no `lineno`, and is left without a span rather
    than given a position it does not have."""
    e = _js()
    e.rule("Name", "{id:name}")
    e.rule("BinOp", "{left} {op:sym} {right}")
    built = ast.BinOp(
        left=ast.Name(id="a", ctx=ast.Load()),
        op=ast.Add(),
        right=ast.Name(id="b", ctx=ast.Load()),
    )
    assert e.to_text(built) == "a + b"
    assert e.source_map(built) == []


def test_the_map_reaches_every_node_that_has_a_position() -> None:
    e = _js()
    e.rule("BinOp", "{left} {op:sym} {right}")
    e.rule("Name", "{id:name}")
    tree = ast.parse("a + b", mode="eval").body
    positions = {span for _s, _e, span in e.source_map(tree)}
    assert positions == {(1, 0), (1, 4)}, positions


def test_a_fallback_carries_a_position_too() -> None:
    """`fallback=` is how a consumer adopts one production at a time, so it
    must not be a hole in the map."""
    e = Emitter(PY, levels=LEVELS, fallback=lambda node: f"<{type(node).__name__}>")
    e.projection("name", str)
    e.rule("Name", "{id:name}")
    tree = ast.parse("a + b", mode="eval").body
    assert e.to_text(tree) == "<BinOp>"
    assert e.source_map(tree) == [(0, 7, (1, 0))]
