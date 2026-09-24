"""What a consumer's dispatch table covers of a grammar, and what it does not.

A `singledispatch` registry, a `match` over node types, a dictionary of
handlers: each is an enumeration of the language sitting next to another
enumeration of the language. They have to agree, and when they drift the
symptom is a `NotImplementedError` in someone's program rather than a failure
in a test.

Comparing the two is four lines, which is why the first two consumers each
wrote their own copy and the copies had already diverged. That is the shape
this project exists to remove, so it lives here now.

    cover = dispatch(PY, (compile_expr.registry, compile_stmt.registry),
                     bases=("stmt", "expr"),
                     accounted={"inline": INLINE, "unimplemented": TODO})
    assert not cover.missing, cover.explain()

What `accounted` is for: a production may legitimately have no handler of its
own. It may be eliminated by an earlier pass, emitted by whatever contains it,
or simply not implemented yet. Each of those is a decision, so each is named,
and `absent` catches an entry that no longer corresponds to anything.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from astero.grammar import Grammar


def handlers(registries: Iterable[Mapping[type, Any]]) -> frozenset[str]:
    """Production names a set of `singledispatch` registries handles.

    `object` is the fallback every registry carries and never a production.
    """
    return frozenset(
        cls.__name__ for registry in registries for cls in registry if cls is not object
    )


#: Classes that supply `visit_` methods of their own without those being a
#: consumer's decision. `ast.NodeVisitor` defined `visit_Constant` through
#: 3.13, the shim routing the constant nodes 3.8 folded together, and CPython
#: dropped it in 3.14. Every subclass appeared to handle `Constant` on one
#: interpreter and not the next, which is version sensitivity a coverage
#: obligation should never inherit.
#:
#: One entry, because it is the only class in the MRO that has any: neither
#: `ast.NodeTransformer` nor `object` defines a `visit_` method of its own,
#: and `test_coverage.py` gates that against `ast` rather than trusting it.
_FRAMEWORK_BASES = (ast.NodeVisitor,)


def visitors(*classes: type, prefix: str = "visit_") -> frozenset[str]:
    """Production names the `visit_<Production>` methods of `classes` handle.

    The third way a consumer enumerates a language, after a `singledispatch`
    registry and a `match`. `ast.NodeVisitor` dispatches on
    `visit_` + `type(node).__name__`, so the method names are the table.

    Read from each class's own `__dict__` along the MRO, framework bases
    excluded. `dir` would be shorter and wrong: `ast.NodeVisitor` defines
    `visit_Constant`, so every subclass would report handling `Constant`,
    and a gate built on that certifies a production nobody wrote. A class
    that defines `visit_Constant` itself still counts, because the lookup
    is by where the method is defined.

    `generic_visit` is the fallback rather than a production, and it does
    not carry the prefix.

    Pass several classes when a consumer splits its dispatch, the way an
    expression visitor and a statement visitor divide the grammar::

        cover = Coverage(
            handled=visitors(ExpressionCodegen, FunctionCodegen),
            expected=PY.concrete("expr") | PY.concrete("stmt"),
        )
    """
    found: set[str] = set()
    for cls in classes:
        for klass in cls.__mro__:
            if klass in _FRAMEWORK_BASES:
                continue
            found |= {
                name.removeprefix(prefix)
                for name in vars(klass)
                if name.startswith(prefix) and name != prefix
            }
    return frozenset(found)


def match_arms(*functions: Any) -> frozenset[str]:
    """Production names the `match` statements in `functions` have a case for.

    A `match` over node types is the second way a consumer enumerates a
    language, and the one `handlers` cannot read: there is no registry to
    inspect, only `case Cls(...)` patterns in the source. This reads them back
    from it.

    Top-level patterns only, and both sides of an alternative:
    `case ArrayDim() | ArrayStride()` handles two. A nested pattern is part of
    the arm's condition rather than the thing it dispatches on, so
    `case Const(value=float())` handles `Const` and not `float`. A `case _`
    handles nothing by name, which is the point: a fallback is not coverage.

    Raises `OSError` if a function's source is unavailable, which is the
    honest answer for something defined in a REPL or a C extension.
    """
    found: set[str] = set()
    for function in functions:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Match):
                continue
            for case in node.cases:
                found |= _pattern_names(case.pattern)
    return frozenset(found)


def _pattern_names(pattern: ast.pattern) -> set[str]:
    """The class a top-level pattern dispatches on, or both sides of an `|`."""
    match pattern:
        case ast.MatchOr():
            return {n for alt in pattern.patterns for n in _pattern_names(alt)}
        case ast.MatchClass():
            return {_dotted_tail(pattern.cls)}
        # `case Cls() as x` still dispatches on `Cls`.
        case ast.MatchAs() if pattern.pattern is not None:
            return _pattern_names(pattern.pattern)
    return set()


def _dotted_tail(node: ast.expr) -> str:
    """`ast.Assign` and `Assign` name the same production."""
    return node.attr if isinstance(node, ast.Attribute) else ast.unparse(node)


@dataclass(frozen=True)
class Coverage:
    """A dispatch table measured against a grammar."""

    #: Production names the consumer handles.
    handled: frozenset[str]
    #: Production names it is obliged to handle, before `accounted` is applied.
    expected: frozenset[str]
    #: Names deliberately not handled, grouped by the reason they are not.
    accounted: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @property
    def excused(self) -> frozenset[str]:
        if not self.accounted:
            return frozenset()
        return frozenset().union(*self.accounted.values())

    @property
    def missing(self) -> frozenset[str]:
        """Productions that can appear, are not handled, and have no reason."""
        return self.expected - self.handled - self.excused

    @property
    def absent(self) -> frozenset[str]:
        """Excused names this grammar has no production for.

        Usually a stale entry. Sometimes a production the running interpreter
        does not have, since a grammar read off `ast` moves with the version,
        so a consumer subtracts the ones it knows are version-dependent.
        """
        return self.excused - self.expected

    @property
    def redundant(self) -> frozenset[str]:
        """Excused names that are handled after all, so the excuse is stale."""
        return self.excused & self.handled

    def explain(self) -> str:
        covered = len(self.handled & self.expected)
        lines = [f"{covered} of {len(self.expected)} productions handled"]
        if self.missing:
            lines.append(
                f"  no handler and no reason: {sorted(self.missing)}\n"
                "  add one, or name it in `accounted` with the reason"
            )
        if self.absent:
            lines.append(f"  excused but not a production here: {sorted(self.absent)}")
        if self.redundant:
            lines.append(f"  excused but handled anyway: {sorted(self.redundant)}")
        return "\n".join(lines)


def dispatch(
    grammar: Grammar,
    registries: Iterable[Mapping[type, Any]],
    *,
    bases: Collection[str] = (),
    accounted: Mapping[str, Iterable[str]] | None = None,
) -> Coverage:
    """Measure `registries` against the productions of `grammar`.

    `bases` narrows the obligation to what can appear under those productions,
    which is how a statement dispatcher is not asked about expressions. With no
    bases the whole grammar is the obligation.
    """
    expected = (
        frozenset().union(*(grammar.concrete(b) for b in bases))
        if bases
        else grammar.concrete()
    )
    return Coverage(
        handled=handlers(registries),
        expected=expected,
        accounted={k: frozenset(v) for k, v in (accounted or {}).items()},
    )
