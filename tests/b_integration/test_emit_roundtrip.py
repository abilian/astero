"""G1 to G3: emission, round-tripped against CPython's parser.

The oracle is the strongest one available for an emitter: emit an expression,
parse the result, and compare the trees. Formatting choices are invisible to
it, which is the point. What it does judge is whether the brackets are right,
and those are derived from a declared precedence table rather than written per
production.
"""

from __future__ import annotations

import ast
import sysconfig
from pathlib import Path

import pytest

from astero.emit import Assoc, Level, needs_parens
from astero.python.emit import emit, emit_module
from astero.python.rewriting import DERIVED, key

#: Only legal inside a parent, so a standalone round trip cannot judge them.
NOT_STANDALONE: tuple[type, ...] = (
    ast.Slice,
    ast.FormattedValue,
    ast.JoinedStr,
    ast.Starred,
)

# PEP 750 t-strings, from 3.14. An `Interpolation` is the t-string twin of
# `FormattedValue` and is legal only inside a `TemplateStr`: emitted alone,
# `{0}` reparses as a set display.
if hasattr(ast, "Interpolation"):
    NOT_STANDALONE += (ast.Interpolation,)


def _round_trips(node: ast.expr) -> bool:
    return key(ast.parse(emit(node), mode="eval").body, DERIVED) == key(node, DERIVED)


def _standalone(node: ast.AST) -> bool:
    if not isinstance(node, ast.expr) or isinstance(node, NOT_STANDALONE):
        return False
    # `x[1:2, 3:4]` is a Tuple of Slices, legal only inside a subscript.
    return not (
        isinstance(node, ast.Tuple) and any(isinstance(e, ast.Slice) for e in node.elts)
    )


PRECEDENCE_CASES = [
    "1 + 2 * 3",
    "(1 + 2) * 3",
    "2 ** 3 ** 4",
    "(2 ** 3) ** 4",
    "-x ** y",
    "(-x) ** y",
    "a < b < c",
    "not a or b",
    "not (a or b)",
    "a if b else c",
    "(a if b else c) if d else e",
    "a if (b if c else d) else e",
    "a if b else (c if d else e)",
    "a and b or c",
    "a and (b or c)",
    "-(a + b)",
    "~a & b",
    "a | b & c",
    "(a | b) & c",
    "x[1:2:3]",
    "(1,)",
    "[*a, b]",
    "{**a, 'k': v}",
    "a.b[c](d, e=1)",
    "(3531).to_bytes(2, 'little')",
    "1e309",
    "-1e309",
    "...",
]


@pytest.mark.parametrize("source", PRECEDENCE_CASES)
def test_g1_precedence_cases_round_trip(source: str) -> None:
    assert _round_trips(ast.parse(source, mode="eval").body), source


def test_g2_brackets_are_derived_not_written() -> None:
    """The rule lives in one function, and the table is what varies."""
    tight, loose = Level(13), Level(12)
    assert needs_parens(loose, tight, on_right=False)
    assert not needs_parens(tight, loose, on_right=True)
    # Left-associative: an equal child needs brackets only on the right.
    left = Level(12, Assoc.LEFT)
    assert needs_parens(left, left, on_right=True)
    assert not needs_parens(left, left, on_right=False)
    # Right-associative, such as `**`: the other way round.
    right = Level(17, Assoc.RIGHT)
    assert needs_parens(right, right, on_right=False)
    assert not needs_parens(right, right, on_right=True)
    # Non-associative, such as a comparison: always.
    none = Level(7, Assoc.NONE)
    assert needs_parens(none, none, on_right=True)
    assert needs_parens(none, none, on_right=False)


def test_g3_the_standard_library_round_trips() -> None:
    """Every standalone expression in the stdlib, emitted and reparsed."""
    total = failed = 0
    for path in sorted(Path(sysconfig.get_paths()["stdlib"]).rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, ValueError, UnicodeDecodeError, RecursionError):
            continue
        for node in ast.walk(tree):
            if not _standalone(node) or not isinstance(node, ast.expr):
                continue
            total += 1
            try:
                ok = _round_trips(node)
            except (SyntaxError, ValueError, RecursionError):
                ok = False
            failed += not ok
    assert total > 100_000, f"corpus too small: {total} expressions"
    assert failed == 0, f"{failed} of {total} expressions failed to round-trip"


def test_g4_the_standard_library_round_trips_as_whole_modules() -> None:
    """Statements and layout: parse, emit, reparse, compare.

    A stronger oracle than the expression one, because indentation is
    semantic in Python: a body emitted at the wrong depth reparses into a
    different tree rather than into ugly source.
    """
    total = failed = 0
    for path in sorted(Path(sysconfig.get_paths()["stdlib"]).rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, ValueError, UnicodeDecodeError, RecursionError):
            continue
        total += 1
        try:
            again = ast.parse(emit_module(tree))
            ok = key(again, DERIVED) == key(tree, DERIVED)
        except (SyntaxError, ValueError, RecursionError):
            ok = False
        failed += not ok
    assert total > 500, f"corpus too small: {total} modules"
    assert failed == 0, f"{failed} of {total} modules failed to round-trip"


LAYOUT_CASES = [
    "if a:\n    b\nelif c:\n    d\nelse:\n    e\n",
    "for i in r:\n    x += i\nelse:\n    pass\n",
    "try:\n    a\nexcept E as e:\n    b\nelse:\n    c\nfinally:\n    d\n",
    "with a as b, c as (d, e):\n    pass\n",
    "class C(B):\n    def m(self):\n        return 1\n",
    "while a:\n    if b:\n        continue\n    break\n",
    "(x): int = 1\n",
    "a and (b and c)\n",
]


@pytest.mark.parametrize("source", LAYOUT_CASES)
def test_g4_layout_cases(source: str) -> None:
    tree = ast.parse(source)
    assert key(ast.parse(emit_module(tree)), DERIVED) == key(tree, DERIVED), source
