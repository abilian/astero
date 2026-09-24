"""A Python expression emitter, with brackets derived rather than written.

The templates say what each production looks like. None of them says when a
subexpression needs brackets: `child` asks `needs_parens` with the declared
precedence, and that is the only place the question is answered.

The oracle is a round trip. Emit an expression, parse the result, and compare
the trees. `tests/b_integration/test_emit_roundtrip.py` runs it over every
expression in the standard library.
"""

from __future__ import annotations

import ast
import math

from astero.emit import (
    ATOM,
    Assoc,
    Doc,
    Level,
    concat,
    joined,
    joined_by,
    line,
    needs_parens,
    nest,
    render,
    text,
)
from astero.python.precedence import (
    abuts_badly,
    level_of,
    parser_flattens,
)

_BINOPS: dict[type, str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.MatMult: "@",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.BitOr: "|",
    ast.BitXor: "^",
    ast.BitAnd: "&",
}
_UNARYOPS: dict[type, str] = {
    ast.UAdd: "+",
    ast.USub: "-",
    ast.Invert: "~",
    ast.Not: "not ",
}
_CMPOPS: dict[type, str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}
_BOOLOPS: dict[type, str] = {ast.And: "and", ast.Or: "or"}


def _span(node: ast.AST) -> tuple[int, int] | None:
    lineno = getattr(node, "lineno", None)
    col = getattr(node, "col_offset", None)
    return None if lineno is None or col is None else (lineno, col)


def child(node: ast.expr, outer: Level, *, on_right: bool = False) -> Doc:
    """Emit `node` in a position of binding power `outer`, bracketing if needed.

    The one place brackets are decided. Every template calls this and none of
    them knows the rule.
    """
    doc = expr(node)
    if needs_parens(level_of(node), outer, on_right=on_right):
        return text("(") + doc + text(")")
    return doc


def _operator(node: ast.expr) -> Doc | None:
    """Templates for the productions precedence actually governs."""
    here = level_of(node)
    match node:
        case ast.BinOp(op=binop):
            return (
                child(node.left, here)
                + text(f" {_BINOPS[type(binop)]} ")
                + child(node.right, here, on_right=True)
            )
        case ast.UnaryOp(op=unop):
            return text(_UNARYOPS[type(unop)]) + child(
                node.operand, here, on_right=True
            )
        case ast.BoolOp(op=boolop, values=values):
            parts = [
                text("(") + expr(v) + text(")")
                if parser_flattens(node, v)
                else child(v, here, on_right=bool(i))
                for i, v in enumerate(values)
            ]
            return joined(f" {_BOOLOPS[type(boolop)]} ", parts)
        case ast.Compare(left=left, ops=ops, comparators=rest):
            doc = child(left, here)
            for cmpop, comparator in zip(ops, rest, strict=True):
                doc = (
                    doc
                    + text(f" {_CMPOPS[type(cmpop)]} ")
                    + child(comparator, here, on_right=True)
                )
            return doc
        case ast.IfExp(body=body, test=test, orelse=orelse):
            # `x if c else y` chains to the right only through `y`. An IfExp in
            # the body or the test needs brackets; one in the orelse does not.
            return (
                child(body, here)
                + text(" if ")
                + child(test, here)
                + text(" else ")
                + child(orelse, here, on_right=True)
            )
        case _:
            return None


def _container(node: ast.expr, span: tuple[int, int] | None) -> Doc | None:
    """Templates whose brackets are their own, not precedence's."""
    item = Level(3)
    match node:
        case ast.Attribute(value=value, attr=attr):
            receiver = (
                text("(") + expr(value) + text(")")
                if abuts_badly(value)
                else child(value, ATOM)
            )
            return receiver + text(f".{attr}", span)
        case ast.Subscript(value=value, slice=index):
            return child(value, ATOM) + text("[") + _slice(index) + text("]")
        case ast.Call(func=func, args=args, keywords=keywords):
            parts = [child(a, item) for a in args] + [_keyword(k) for k in keywords]
            return child(func, ATOM) + text("(") + joined(", ", parts) + text(")")
        case ast.Tuple(elts=elts):
            inner = joined(", ", [child(e, item) for e in elts])
            tail = text(",") if len(elts) == 1 else text("")
            return text("(") + inner + tail + text(")")
        case ast.List(elts=elts):
            return text("[") + joined(", ", [child(e, item) for e in elts]) + text("]")
        case ast.Set(elts=elts):
            return text("{") + joined(", ", [child(e, item) for e in elts]) + text("}")
        case ast.Dict(keys=keys, values=values):
            return text("{") + joined(", ", _pairs(keys, values)) + text("}")
        case ast.Starred(value=value):
            return text("*") + child(value, ATOM)
        case ast.Slice():
            return _slice(node)
        case _:
            return None


def expr(node: ast.expr) -> Doc:
    """A document for `node`, by production."""
    span = _span(node)
    match node:
        case ast.Name():
            return text(node.id, span)
        case ast.Constant():
            # `kind` carries the `u` prefix of a u-string, which `repr` drops.
            return text((node.kind or "") + _constant(node.value), span)
    doc = _operator(node) or _container(node, span)
    if doc is not None:
        return doc
    # Productions with no template yet: CPython's own unparser, so the round
    # trip still exercises everything above.
    return text(ast.unparse(node), span)


_INFINITY = "1e309"


def _constant(value: object) -> str:
    """Source for a literal.

    `repr` is right except where it produces something that is not a literal.
    `Ellipsis`, `inf` and `nan` all reparse as names, so each is written as an
    expression that evaluates to itself, which is what CPython's own unparser
    does.
    """
    if value is Ellipsis:
        return "..."
    match value:
        case float() if not math.isfinite(value):
            if math.isnan(value):
                return f"({_INFINITY} - {_INFINITY})"
            return _INFINITY if value > 0 else f"-{_INFINITY}"
        case complex() if not (math.isfinite(value.real) and math.isfinite(value.imag)):
            return (
                repr(value)
                .replace("inf", _INFINITY)
                .replace("nan", f"({_INFINITY} - {_INFINITY})")
            )
    return repr(value)


def _pairs(keys: list[ast.expr | None], values: list[ast.expr]) -> list[Doc]:
    out = []
    for key, value in zip(keys, values, strict=True):
        if key is None:
            out.append(text("**") + child(value, ATOM))
        else:
            out.append(child(key, Level(3)) + text(": ") + child(value, Level(3)))
    return out


def _keyword(node: ast.keyword) -> Doc:
    if node.arg is None:
        return text("**") + child(node.value, ATOM)
    return text(f"{node.arg}=") + child(node.value, Level(3))


def _slice(node: ast.expr) -> Doc:
    # `x[1:2, 3:4]` is a Tuple of Slices, and a Slice is only legal directly
    # inside brackets, so this tuple is the one that must not be parenthesized.
    if isinstance(node, ast.Tuple) and any(isinstance(e, ast.Slice) for e in node.elts):
        return joined(", ", [_slice(e) for e in node.elts])
    if not isinstance(node, ast.Slice):
        return child(node, Level(3))
    parts = [
        text("") if node.lower is None else child(node.lower, Level(3)),
        text("") if node.upper is None else child(node.upper, Level(3)),
    ]
    doc = parts[0] + text(":") + parts[1]
    if node.step is not None:
        doc = doc + text(":") + child(node.step, Level(3))
    return doc


# ----------------------------------------------------------------- statements
#
# Indentation is what the document algebra is for: a body is a `Nest` of lines,
# and no template concatenates a newline or counts spaces.


def block(body: list[ast.stmt]) -> Doc:
    """An indented suite, one statement per line."""
    return nest(concat(*[line() + stmt(s) for s in body]))


def suite(header: Doc, body: list[ast.stmt]) -> Doc:
    return header + text(":") + block(body)


def _orelse(body: list[ast.stmt]) -> Doc:
    """An `else` clause, collapsing `else: if ...` into `elif`."""
    if not body:
        return text("")
    if len(body) == 1 and isinstance(body[0], ast.If):
        inner = body[0]
        return (
            line()
            + suite(text("elif ") + expr(inner.test), inner.body)
            + _orelse(inner.orelse)
        )
    return line() + suite(text("else"), body)


def stmt(node: ast.stmt) -> Doc:
    """A document for one statement."""
    doc = _simple(node) or _compound(node)
    if doc is not None:
        return doc
    # No template yet: CPython's unparser. Its own newlines are replaced by
    # `Line`, so the enclosing `Nest` supplies the block indent and the text
    # keeps only its relative indentation.
    return joined_by(line(), [text(t) for t in ast.unparse(node).splitlines()])


def _simple(node: ast.stmt) -> Doc | None:
    item = Level(3)
    match node:
        case ast.Expr(value=value):
            return expr(value)
        case ast.Assign(targets=targets, value=value):
            lhs = joined(" = ", [child(t, item) for t in targets])
            return lhs + text(" = ") + child(value, item)
        case ast.AugAssign(target=target, op=op, value=value):
            return (
                child(target, ATOM)
                + text(f" {_BINOPS[type(op)]}= ")
                + child(value, item)
            )
        case ast.AnnAssign(target=target, annotation=annotation, value=value):
            # `simple` is 0 when the target is parenthesised, and that changes
            # the meaning: `(x): int` records no module annotation.
            lhs = child(target, ATOM)
            if not node.simple and isinstance(target, ast.Name):
                lhs = text("(") + lhs + text(")")
            doc = lhs + text(": ") + child(annotation, item)
            return doc if value is None else doc + text(" = ") + child(value, item)
        case _:
            return _keyword_stmt(node)


def _keyword_stmt(node: ast.stmt) -> Doc | None:
    """Statements that are a keyword and at most a short tail."""
    match node:
        case ast.Return(value=value):
            return text("return") if value is None else text("return ") + expr(value)
        case ast.Pass():
            return text("pass")
        case ast.Break():
            return text("break")
        case ast.Continue():
            return text("continue")
        case ast.Delete(targets=targets):
            return text("del ") + joined(", ", [child(t, ATOM) for t in targets])
        case ast.Global(names=names):
            return text("global " + ", ".join(names))
        case ast.Nonlocal(names=names):
            return text("nonlocal " + ", ".join(names))
        case _:
            return None


def _compound(node: ast.stmt) -> Doc | None:
    match node:
        case ast.If(test=test, body=body, orelse=orelse):
            return suite(text("if ") + expr(test), body) + _orelse(orelse)
        case ast.While(test=test, body=body, orelse=orelse):
            return suite(text("while ") + expr(test), body) + _else(orelse)
        case ast.For(target=target, iter=iterable, body=body, orelse=orelse):
            header = text("for ") + child(target, ATOM) + text(" in ") + expr(iterable)
            return suite(header, body) + _else(orelse)
        case ast.AsyncFor(target=target, iter=iterable, body=body, orelse=orelse):
            header = (
                text("async for ") + child(target, ATOM) + text(" in ") + expr(iterable)
            )
            return suite(header, body) + _else(orelse)
        case ast.FunctionDef() | ast.AsyncFunctionDef():
            return _function(node)
        case ast.ClassDef(body=body):
            # Bases, keywords and type parameters keep the unparser for now.
            head = ast.unparse(node).splitlines()[len(node.decorator_list)]
            return _decorators(node) + text(head.rstrip()) + block(body)
        case ast.With(items=items, body=body) | ast.AsyncWith(items=items, body=body):
            kw = "async with " if isinstance(node, ast.AsyncWith) else "with "
            return suite(text(kw) + joined(", ", [_item(i) for i in items]), body)
        case ast.Try():
            return _try(node)
        case _:
            return None


def _decorators(node: ast.stmt) -> Doc:
    decorators: list[ast.expr] = getattr(node, "decorator_list", [])
    if not decorators:
        return text("")
    return concat(*[text("@") + expr(d) + line() for d in decorators])


def _item(item: ast.withitem) -> Doc:
    doc = expr(item.context_expr)
    if item.optional_vars is None:
        return doc
    return doc + text(" as ") + child(item.optional_vars, ATOM)


def _function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Doc:
    """A def, with the signature line taken from the unparser.

    Arguments have their own grammar (defaults, kinds, annotations) and no
    template yet, so the header is borrowed and the body is not.
    """
    lines = ast.unparse(node).splitlines()
    header = lines[len(node.decorator_list)].rstrip()
    return _decorators(node) + text(header) + block(node.body)


def _try(node: ast.Try) -> Doc:
    doc = suite(text("try"), node.body)
    for handler in node.handlers:
        head = text("except")
        if handler.type is not None:
            head += text(" ") + expr(handler.type)
        if handler.name:
            head += text(f" as {handler.name}")
        doc = doc + line() + suite(head, handler.body)
    if node.orelse:
        doc = doc + line() + suite(text("else"), node.orelse)
    if node.finalbody:
        doc = doc + line() + suite(text("finally"), node.finalbody)
    return doc


def _else(body: list[ast.stmt]) -> Doc:
    return text("") if not body else line() + suite(text("else"), body)


def module(node: ast.Module) -> Doc:
    return joined_by(line(), [stmt(s) for s in node.body])


def emit(node: ast.expr) -> str:
    """Source text for an expression."""
    return render(expr(node))


def emit_module(node: ast.Module) -> str:
    """Source text for a module."""
    return render(module(node)) + "\n"


#: Nothing here reads this; it exists so a reader can see that the associativity
#: of the table is what makes the brackets come out.
ASSOCIATIVITY_MATTERS = (Assoc.LEFT, Assoc.RIGHT, Assoc.NONE)
