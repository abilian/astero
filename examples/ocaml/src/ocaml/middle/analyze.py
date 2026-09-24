"""Which definition does each name refer to?

Given `let x = 1 in let x = 2 in x`, which `x` does the last one mean? Given
`let rec f n = f (n - 1)`, does the `f` inside refer to the one being
defined? Those are scope questions, and this answers them.

What is worth noticing is how little is here: about fifty lines, and none of
them mentions `PVar`, `Variant` or `FieldDef`, or lists which fields hold a
binding. All of that comes from `grammar.py` by asking astero:
`OCAML.definitions(ns)` says which fields declare a name,
`OCAML.reads(node, ns)` says which read one, and `binds_in_scope` says what
a subtree contributes to the scope around it. A compiler that wrote those
lists out by hand would have four of them to keep in step; this has none.

The routing is the part to read. A scope layer lists the fields that are
evaluated *inside* the scope its production opens, so `_resolve` walks with
two environments and picks per field. That one rule is what puts a `match`
arm's pattern inside the arm, a `for` loop's index inside the loop, and a
function's parameters inside the function while its name stays outside.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator
from typing import Any

from astero.scopes import Block, binds_in_scope, scope_tree
from ocaml import syntax

from .grammar import CONS, FIELDS, NAMESPACES, OCAML, SCOPES, TYPES, TYVARS, VALS
from .prelude import CONSTRUCTORS, FIELD_NAMES, PRELUDE_TYPES, TYPE_NAMES

#: The initial environment, one entry per namespace the grammar declares.
#: `prelude.py` is the source, and it is a middle-end module on purpose:
#: which names are in scope is decided before anything runs. `back/runtime.py`
#: supplies a value for each of them, and a test holds the two in step.
PRELUDE: dict[str, frozenset[str]] = {
    VALS: frozenset(PRELUDE_TYPES),
    CONS: frozenset(CONSTRUCTORS),
    FIELDS: frozenset(FIELD_NAMES),
    TYPES: frozenset(TYPE_NAMES),
    TYVARS: frozenset(),
}


def is_node(value: Any) -> bool:
    """Whether the grammar declares this value as a production."""
    return type(value).__name__ in OCAML.productions


def opened_fields(node: Any) -> frozenset[str]:
    """Fields of `node` evaluated inside a scope it opens, conditions applied.

    `Present("params")` is why `let f x = e` answers with two fields and
    `let x = e` with none, without either form being named below.
    """
    return frozenset(
        name
        for layer in SCOPES.get(type(node).__name__, ())
        if layer.applies(node)
        for name in layer.inside
    )


def fields_of(node: Any) -> Iterator[tuple[str, Any]]:
    """(field name, child) for every child a traversal enters."""
    for slot in OCAML.children(type(node).__name__):
        value = getattr(node, slot.name, None)
        for child in value if isinstance(value, list) else [value]:
            if is_node(child):
                yield slot.name, child


def scope_names(node: Any, inside: Collection[str], ns: str) -> set[str]:
    """Every name in `ns` that the fields `inside` contribute to one scope.

    `binds_in_scope` stops at a scope boundary, so a `fun` nested in the body
    contributes its own name and not its parameters.
    """
    out: set[str] = set()
    for name, child in fields_of(node):
        if name in inside:
            out |= binds_in_scope(child, OCAML, ns, SCOPES)
    return out


def blocks(structure: syntax.Structure, ns: str) -> Block:
    """The scope tree of a structure, in one namespace. For reading."""
    return scope_tree(structure, OCAML, SCOPES, ns, root_kind="module", root_name="top")


def check(structure: syntax.Structure, ns: str) -> list[str]:
    """Uses of a name in `ns` that nothing in scope declares."""
    problems: list[str] = []
    root = scope_names(structure, ("items",), ns) | PRELUDE[ns]
    _resolve(structure, [root], ns, problems)
    return problems


def unbound(structure: syntax.Structure) -> list[str]:
    """The same, across every namespace the grammar declares."""
    return [problem for ns in NAMESPACES for problem in check(structure, ns)]


def _resolve(node: Any, visible: list[set[str]], ns: str, problems: list[str]) -> None:
    for name in OCAML.reads(node, ns):
        if not any(name in level for level in visible):
            problems.append(f"{type(node).__name__}: {name!r} is not declared in {ns}")
    inside = opened_fields(node)
    inner = [*visible, scope_names(node, inside, ns)] if inside else visible
    for name, child in fields_of(node):
        _resolve(child, inner if name in inside else visible, ns, problems)
