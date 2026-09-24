"""Turning a pattern into a test and a list of places to look.

`match l with h :: t -> ...` has to become, in Python, roughly: *is this a
cons cell? if so, `h` is its first argument and `t` is its second.* This
file produces those two things. `tests` gives the conditions that must
hold, and `bindings` gives, for each name the pattern binds, the expression
that reaches its value.

Both are simple because `expand` has already run. An or-pattern like
`Add (a, b) | Mul (a, b)` is turned into two separate patterns first, so
nothing below has to deal with alternatives, and every test is a path into
the value.

ponytail: that expansion is a cross-product, so a pattern with many nested
`|` grows. A decision tree is the upgrade, and it needs the exhaustiveness
algorithm `specification.md`, *Typing*, defers.
"""

from __future__ import annotations

import ast
from typing import Any

from ocaml import syntax as s

from .pyast import Literal, attribute, call, const, field_of, item, name


def expand(pattern: Any) -> list[Any]:
    """A pattern as a list of or-free patterns.

    `Some (A | B)` becomes `Some A` and `Some B`, so the tests below are
    paths into the subject and never a disjunction. The cross-product is the
    ponytail note at the top of this file.
    """
    match pattern:
        case s.POr(alternatives=alternatives):
            return [made for alt in alternatives for made in expand(alt)]
        case s.PTuple(items=items):
            return [s.PTuple(list(row)) for row in _rows(items)]
        case s.PList(items=items):
            return [s.PList(list(row)) for row in _rows(items)]
        case s.PArray(items=items):
            return [s.PArray(list(row)) for row in _rows(items)]
        case s.PConstruct(name=label, args=args):
            return [s.PConstruct(label, list(row)) for row in _rows(args)]
        case s.PRecord(fields=fields):
            rows = _rows([f.pattern for f in fields])
            return [
                s.PRecord([
                    s.PField(f.label, p) for f, p in zip(fields, row, strict=True)
                ])
                for row in rows
            ]
        case s.PAlias(pattern=inner, name=label):
            return [s.PAlias(made, label) for made in expand(inner)]
        case s.PConstraint(pattern=inner):
            return expand(inner)
    return [pattern]


def _rows(patterns: list[Any]) -> list[tuple[Any, ...]]:
    """Every combination of the expansions of each position."""
    rows: list[tuple[Any, ...]] = [()]
    for pattern in patterns:
        rows = [(*row, made) for row in rows for made in expand(pattern)]
    return rows


def tests(pattern: Any, path: ast.expr) -> list[ast.expr]:
    """What must hold for `path` to match. Ordered, because `and` is."""
    match pattern:
        case s.PWild() | s.PVar():
            return []
        case s.PLit(value=value):
            return [_equals(path, value)]
        case s.PTuple(items=items):
            return [t for i, p in enumerate(items) for t in tests(p, item(path, i))]
        case s.PList(items=items):
            return _list_tests(items, path)
        case s.PArray(items=items):
            found: list[ast.expr] = [
                ast.Compare(
                    left=call(name("len"), path),
                    ops=[ast.Eq()],
                    comparators=[const(len(items))],
                )
            ]
            for index, entry in enumerate(items):
                found += tests(entry, item(path, index))
            return found
        case s.PConstruct(name=label, args=args):
            found = [_tag_is(path, label)]
            for index, entry in enumerate(args):
                found += tests(entry, item(attribute(path, "args"), index))
            return found
        case s.PRecord(fields=fields):
            return [
                check
                for f in fields
                for check in tests(f.pattern, field_of(path, f.label))
            ]
        case s.PAlias(pattern=inner):
            return tests(inner, path)
    raise TypeError(f"no rule for {type(pattern).__name__}")


def _tag_is(path: ast.expr, label: str) -> ast.expr:
    return ast.Compare(
        left=attribute(path, "tag"), ops=[ast.Eq()], comparators=[const(label)]
    )


def _equals(path: ast.expr, literal: Any) -> ast.expr:
    return ast.Compare(
        left=path, ops=[ast.Eq()], comparators=[const(_literal_value(literal))]
    )


def _literal_value(literal: Any) -> Literal:
    return None if isinstance(literal, s.Unit) else literal.value


def _list_tests(items: list[Any], path: ast.expr) -> list[ast.expr]:
    """`[a; b]` is two cons cells and a nil, so it is three tag tests."""
    found: list[ast.expr] = []
    walk = path
    for entry in items:
        found.append(_tag_is(walk, "::"))
        found += tests(entry, item(attribute(walk, "args"), 0))
        walk = item(attribute(walk, "args"), 1)
    found.append(_tag_is(walk, "[]"))
    return found


def bindings(pattern: Any, path: ast.expr) -> list[tuple[str, ast.expr]]:
    """The names a pattern binds, each with the path that reaches it."""
    match pattern:
        case s.PWild() | s.PLit():
            return []
        case s.PVar(name=label):
            return [(label, path)]
        case s.PTuple(items=items):
            return [b for i, p in enumerate(items) for b in bindings(p, item(path, i))]
        case s.PArray(items=items):
            return [b for i, p in enumerate(items) for b in bindings(p, item(path, i))]
        case s.PList(items=items):
            return _list_bindings(items, path)
        case s.PConstruct(args=args):
            return [
                b
                for index, entry in enumerate(args)
                for b in bindings(entry, item(attribute(path, "args"), index))
            ]
        case s.PRecord(fields=fields):
            return [
                b for f in fields for b in bindings(f.pattern, field_of(path, f.label))
            ]
        case s.PAlias(pattern=inner, name=label):
            return [(label, path), *bindings(inner, path)]
    raise TypeError(f"no rule for {type(pattern).__name__}")


def _list_bindings(items: list[Any], path: ast.expr) -> list[tuple[str, ast.expr]]:
    found: list[tuple[str, ast.expr]] = []
    walk = path
    for entry in items:
        found += bindings(entry, item(attribute(walk, "args"), 0))
        walk = item(attribute(walk, "args"), 1)
    return found
