"""Python's operator precedence, and the three questions that read it.

`astero.emit` holds the document algebra and the bracketing *rule*:
`Level`, `Assoc` and `needs_parens` work on any language. What binds tighter
than what is a fact about Python, so it lives here rather than there.

Split out when the package grew an `astero.python` — the tables had been
sitting in the generic module since the emitter was written, which is the
same misplacement this library exists to complain about.
"""

from __future__ import annotations

import ast

from astero.emit import ATOM, Assoc, Level

#: Python's expression grammar, lowest binding power first. Declared once;
#: `needs_parens` is the only code that reads it.
PRECEDENCE: dict[type, Level] = {
    ast.Lambda: Level(1, Assoc.NONE),
    ast.IfExp: Level(2, Assoc.RIGHT),
    ast.NamedExpr: Level(3, Assoc.NONE),
    ast.BoolOp: Level(4),  # refined per operator below
    ast.Compare: Level(7, Assoc.NONE),
    ast.BinOp: Level(10),  # refined per operator below
    ast.UnaryOp: Level(16, Assoc.RIGHT),
    ast.Await: Level(18, Assoc.RIGHT),
    ast.Starred: Level(3, Assoc.NONE),
    ast.Yield: Level(1, Assoc.NONE),
    ast.YieldFrom: Level(1, Assoc.NONE),
}


BINOP_LEVELS: dict[type, Level] = {
    ast.BitOr: Level(8),
    ast.BitXor: Level(9),
    ast.BitAnd: Level(10),
    ast.LShift: Level(11),
    ast.RShift: Level(11),
    ast.Add: Level(12),
    ast.Sub: Level(12),
    ast.Mult: Level(13),
    ast.MatMult: Level(13),
    ast.Div: Level(13),
    ast.FloorDiv: Level(13),
    ast.Mod: Level(13),
    ast.Pow: Level(17, Assoc.RIGHT),
}


BOOLOP_LEVELS: dict[type, Level] = {ast.Or: Level(5), ast.And: Level(6)}


#: `not x` binds looser than a comparison, unlike the other unary operators.
UNARY_LEVELS: dict[type, Level] = {ast.Not: Level(6)}


def abuts_badly(receiver: ast.expr) -> bool:
    """Whether a `.` directly after `receiver` would lex as part of it.

    Precedence decides grouping. It does not decide token separation, and
    `3531.to_bytes(...)` is a syntax error because `3531.` lexes as a float.
    A second, much smaller declaration covers that: the two questions are
    independent and an emitter needs both.
    """
    return (
        isinstance(receiver, ast.Constant)
        and isinstance(receiver.value, int)
        and not isinstance(receiver.value, bool)
    )


def parser_flattens(parent: ast.expr, child: ast.expr) -> bool:
    """Whether reparsing would merge `child` into `parent`.

    `a and (b and c)` parses as one three-value `BoolOp`, so emitting it
    without brackets loses the tree even though it keeps the meaning. Like
    `abuts_badly`, this is a fact about the parser that no precedence table
    states, and it is the second entry in that small second declaration.
    """
    return (
        isinstance(parent, ast.BoolOp)
        and isinstance(child, ast.BoolOp)
        and type(parent.op) is type(child.op)
    )


def level_of(node: ast.expr) -> Level:
    """The binding power of an expression, from the declared table."""
    match node:
        case ast.BinOp():
            return BINOP_LEVELS.get(type(node.op), Level(10))
        case ast.BoolOp():
            return BOOLOP_LEVELS.get(type(node.op), Level(4))
        case ast.UnaryOp():
            return UNARY_LEVELS.get(type(node.op), PRECEDENCE[ast.UnaryOp])
    return PRECEDENCE.get(type(node), ATOM)
