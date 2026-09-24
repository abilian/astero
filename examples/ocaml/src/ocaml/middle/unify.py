"""Type inference, part one: what a type is, and making two of them equal.

The compiler is never told that `fact` takes an `int`. It works that out,
and the way it works it out is **unification**: start with an unknown, and
every time the programme uses a value, insist that its type matches how it
was used. `n <= 1` says `n` is comparable to an `int`, so the unknown
standing for `n` becomes `int`. Do that everywhere and the types fall out.

A type here is one of two things. A `Var` is an unknown, which may later
turn out to be something (it holds a link to whatever it turned out to be).
A `Con` is a type constructor applied to arguments: `int` is `Con("int")`,
`int list` is `Con("list", (int,))`, and a function `a -> b` is
`Con("->", (a, b))`. Tuples are `Con("*", ...)`. One shape for everything.

`unify(a, b)` makes two types equal or raises. It refuses a cycle, which is
the **occurs check**: `let rec f x = f` would need a type containing itself,
and the check is what turns that into an error instead of a hang.

**Levels** decide what may be generalized. A variable made inside a `let`'s
right-hand side carries a deeper level than the `let` itself, and
generalizing quantifies exactly the variables deeper than the level asked
about. Scanning the whole environment for free variables gives the same
answer and costs a walk of it per binding.

`infer.py` is part two: one rule per kind of node. This file knows nothing
about the language's syntax and imports nothing from it.

It is not called `types.py`, because a module with that name on `sys.path`
shadows the standard one, which `dataclasses` imports. That is not a
hypothetical; it happened here.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

# ------------------------------------------------------------------- types


@dataclass(eq=False)
class Var:
    """A unification variable: unbound, or linked to what it turned out to be."""

    id: int
    level: int
    link: Type | None = None


@dataclass(frozen=True)
class Con:
    """A type constructor applied to arguments. `int`, `'a list`, `a -> b`.

    A type abbreviation, `type word = symbol list`, is a `Con` too, and
    carries what it stands for in `expansion`. OCaml prints the name a
    programme wrote, so `word` stays `word` until unification meets a type
    with another name and has to look inside.
    """

    name: str
    args: tuple[Type, ...] = ()
    expansion: Type | None = field(default=None, compare=False)

    def rebuilt(self, each: Callable[[Type], Type]) -> Con:
        """The same constructor, with `each` applied to every part."""
        inside = None if self.expansion is None else each(self.expansion)
        return Con(self.name, tuple(each(a) for a in self.args), inside)


Type = Var | Con


@dataclass(frozen=True)
class Scheme:
    """A type with some of its variables quantified."""

    quantified: tuple[int, ...]
    body: Type


ARROW = "->"
TUPLE = "*"

INT = Con("int")
FLOAT = Con("float")
CHAR = Con("char")
STRING = Con("string")
BOOL = Con("bool")
UNIT = Con("unit")
EXN = Con("exn")


class TypingError(Exception):
    """The programme does not type."""


def arrow(*parts: Type) -> Type:
    """`a -> b -> c`, right-associated."""
    result = parts[-1]
    for part in reversed(parts[:-1]):
        result = Con(ARROW, (part, result))
    return result


# ------------------------------------------------------------- unification


def expand(node: Type) -> Type:
    """What an abbreviation stands for, all the way down to a real head."""
    node = prune(node)
    while isinstance(node, Con) and node.expansion is not None:
        node = prune(node.expansion)
    return node


def prune(node: Type) -> Type:
    """Follow the links, shortening them on the way."""
    while isinstance(node, Var) and node.link is not None:
        node.link = prune(node.link)
        node = node.link
    return node


def occurs(var: Var, node: Type) -> None:
    """Refuse a cycle, and lower the levels of what `var` is about to hold.

    The level part is not an optimisation: a variable reachable from `var`
    must not outlive it, or generalization would quantify something the
    outer scope still refers to.
    """
    node = prune(node)
    if isinstance(node, Var):
        if node is var:
            raise TypingError("this would give a cyclic type")
        node.level = min(node.level, var.level)
        return
    for argument in node.args:
        occurs(var, argument)


def unify(left: Type, right: Type) -> None:
    given = left, right
    left, right = prune(left), prune(right)
    if isinstance(left, Var):
        if left is right:
            return
        occurs(left, right)
        left.link = right
        return
    if isinstance(right, Var):
        unify(right, left)
        return
    if left.name == right.name and len(left.args) == len(right.args):
        # Two uses of one abbreviation agree where their expansions do, which
        # is weaker than agreeing argument by argument when a parameter goes
        # unused, and is what OCaml checks.
        if left.expansion is not None and right.expansion is not None:
            unify(left.expansion, right.expansion)
            return
        for a, b in zip(left.args, right.args, strict=True):
            unify(a, b)
        return
    # One side is an abbreviation and the other is not. They agree if its
    # expansion does, and a variable that held the plain side is relinked to
    # the abbreviation, as OCaml relinks it: a parameter first seen as
    # `symbol list` and then passed where `word` is wanted prints as `word`.
    if left.expansion is not None:
        unify(left.expansion, right)
        _relink(given[1], left)
        return
    if right.expansion is not None:
        unify(left, right.expansion)
        _relink(given[0], right)
        return
    raise TypingError(f"this has type {show(right)} but {show(left)} was expected")


def _relink(given: Type, abbreviation: Con) -> None:
    if isinstance(given, Var) and given.link is not None:
        given.link = abbreviation


# --------------------------------------------------------------- schemes


@dataclass
class Fresh:
    """A supply of unification variables, and the level they are made at."""

    counter: itertools.count[int] = field(default_factory=lambda: itertools.count(1))

    def __call__(self, level: int) -> Var:
        return Var(next(self.counter), level)


def generalize(node: Type, level: int) -> Scheme:
    """Quantify every variable made deeper than `level`."""
    found: list[int] = []

    def walk(current: Type) -> None:
        current = prune(current)
        if isinstance(current, Var):
            if current.level > level and current.id not in found:
                found.append(current.id)
            return
        for argument in current.args:
            walk(argument)

    walk(node)
    return Scheme(tuple(found), resolved(node))


def resolved(node: Type) -> Type:
    """`node` with every link followed, so nothing can relink it later.

    A generalized binding's type is settled. `_relink` rewrites the variable
    a type is reached through, and without this `let eps = char_of_int 255`
    printed as `symbol` once `eps` was compared with one.
    """
    node = prune(node)
    return node if isinstance(node, Var) else node.rebuilt(resolved)


def instantiate(scheme: Scheme, level: int, fresh: Fresh) -> Type:
    if not scheme.quantified:
        # The same type, not a copy: a parameter's variable stays the one
        # its uses share, which is what `_relink` needs to reach.
        return scheme.body
    made = {name: fresh(level) for name in scheme.quantified}

    def copy(current: Type) -> Type:
        current = prune(current)
        if isinstance(current, Var):
            return made.get(current.id, current)
        return current.rebuilt(copy)

    return copy(scheme.body)


# --------------------------------------------------------------- printing


#: How tightly a position binds, for `_show`. A tuple binds tighter than an
#: arrow, so `int * bool -> int` needs no brackets and `(int -> int) list`
#: does. Three levels is the whole rule.
ARROW_PLACE = 0
TUPLE_PLACE = 1
ATOM_PLACE = 2


def show(node: Type, names: dict[int, str] | None = None) -> str:
    """A type as OCaml writes it. Quantified variables get `'a` in order."""
    names = {} if names is None else names
    return _show(node, names, ARROW_PLACE)


def _name_for(var: Var, names: dict[int, str]) -> str:
    if var.id not in names:
        names[var.id] = f"'{chr(ord('a') + len(names) % 26)}"
    return names[var.id]


def _show(node: Type, names: dict[int, str], place: int) -> str:
    node = prune(node)
    if isinstance(node, Var):
        return _name_for(node, names)
    if node.name == ARROW:
        left = _show(node.args[0], names, TUPLE_PLACE)
        right = _show(node.args[1], names, ARROW_PLACE)
        body = f"{left} -> {right}"
        return body if place == ARROW_PLACE else f"({body})"
    if node.name == TUPLE:
        body = " * ".join(_show(a, names, ATOM_PLACE) for a in node.args)
        return body if place <= TUPLE_PLACE else f"({body})"
    if not node.args:
        return node.name
    if len(node.args) == 1:
        return f"{_show(node.args[0], names, ATOM_PLACE)} {node.name}"
    inner = ", ".join(_show(a, names, ARROW_PLACE) for a in node.args)
    return f"({inner}) {node.name}"


def show_scheme(scheme: Scheme) -> str:
    """The scheme, with quantified variables first so they read `'a` onwards."""
    names: dict[int, str] = {}
    for index, quantified in enumerate(scheme.quantified):
        names[quantified] = f"'{chr(ord('a') + index % 26)}"
    weak = itertools.count(1)

    def walk(current: Type) -> None:
        current = prune(current)
        if isinstance(current, Var):
            if current.id not in names:
                names[current.id] = f"'_weak{next(weak)}"
            return
        for argument in current.args:
            walk(argument)

    walk(scheme.body)
    return show(scheme.body, names)
