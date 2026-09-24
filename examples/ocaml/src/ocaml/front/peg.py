"""The engine the grammar runs on.

A **parser** answers one question: given this list of tokens, what is the
structure? This file does not know any OCaml. It provides the small pieces
a grammar is built from, and `parser.py` puts them together.

The pieces are the ones any grammar needs. `seq(a, b)` matches `a` then
`b`. `alt(a, b)` tries `a`, and if that fails tries `b`. `many(a)` matches
as many `a` as it can. A parser is just a function from a position in the
token list to either a result and a new position, or `None` for "that did
not match".

This style is called **PEG**, for *parsing expression grammar*, and it has
one property that matters here: `alt` tries its alternatives **in order**
and takes the first that works, and `many` is **greedy**. OCaml is full of
forms that run as far to the right as they can — `let ... in`, `fun`, a
`match` arm, and the dangling `else` — and those two properties get all
four right without anyone writing a rule about it. A parser generator in
the older LR style needs a table of precedences to settle the same four.

"Packrat" means it remembers: `Rule` caches what it found at each position,
so a seventeen-level cascade of operators costs one pass rather than
seventeen.

Written here rather than taken off the shelf because the test suite runs on
Python 3.11 through 3.15 with pytest and nothing else installed, and both
astero and its two sibling examples have no dependencies at all. What that
costs is this file.

An alternative, would be to use the `lark` parser generator.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, fields
from typing import Any

from .lexer import Token, where

#: A parse that did not match. `None` rather than a sentinel, because a
#: successful parse is always a tuple.
Result = tuple[int, Any] | None
Parser = Callable[["State", int], Result]


class ParseError(SyntaxError):
    """The tokens are not a program."""


@dataclass
class State:
    """One parse. Carries the memo table and the furthest failure."""

    tokens: list[Token]
    furthest: int = 0
    expected: set[str] = field(default_factory=set)
    memo: dict[tuple[int, int], Result] = field(default_factory=dict)

    def fail(self, at: int, what: str) -> None:
        """Record a failure, keeping only the furthest position reached."""
        if at > self.furthest:
            self.furthest, self.expected = at, {what}
        elif at == self.furthest:
            self.expected.add(what)

    def span(self, at: int, to: int) -> tuple[int, int]:
        """Source offsets covering the tokens `[at, to)`.

        A token knows where it starts and carries the text it matched, so
        the end of the last one is the end of the span. An empty match is
        zero-width where it sits rather than a span over the token it did
        not consume.
        """
        start = self.tokens[at].at
        if to <= at:
            return (start, start)
        last = self.tokens[to - 1]
        return (start, last.at + len(last.text))


# --------------------------------------------------------------- terminals


def kind(name: str) -> Parser:
    """A token of this kind, yielding its value for a literal and its text
    otherwise."""

    def parse(state: State, at: int) -> Result:
        token = state.tokens[at]
        if token.kind != name:
            state.fail(at, name)
            return None
        return at + 1, token.value if token.value is not None else token.text

    return parse


def lit(text: str) -> Parser:
    """A keyword or symbol, yielding its own text."""

    def parse(state: State, at: int) -> Result:
        token = state.tokens[at]
        if token.text != text or token.kind not in {"kw", "sym"}:
            state.fail(at, repr(text))
            return None
        return at + 1, text

    return parse


def one_of(texts: Iterable[str]) -> Parser:
    """Any one of these keywords or symbols, yielding the one that matched."""
    wanted = frozenset(texts)

    def parse(state: State, at: int) -> Result:
        token = state.tokens[at]
        if token.text not in wanted or token.kind not in {"kw", "sym"}:
            state.fail(at, " or ".join(sorted(map(repr, wanted))))
            return None
        return at + 1, token.text

    return parse


# ------------------------------------------------------------- combinators


def seq(*parsers: Parser) -> Parser:
    """Each in turn, yielding the list of their values."""

    def parse(state: State, at: int) -> Result:
        out = []
        for parser in parsers:
            step = parser(state, at)
            if step is None:
                return None
            at, value = step
            out.append(value)
        return at, out

    return parse


def alt(*parsers: Parser) -> Parser:
    """The first that matches. Ordered, which is what PEG means."""

    def parse(state: State, at: int) -> Result:
        for parser in parsers:
            step = parser(state, at)
            if step is not None:
                return step
        return None

    return parse


def many(parser: Parser) -> Parser:
    """Zero or more, greedily. Never fails."""

    def parse(state: State, at: int) -> Result:
        out = []
        while (step := parser(state, at)) is not None:
            at, value = step
            out.append(value)
        return at, out

    return parse


def many1(parser: Parser) -> Parser:
    """One or more, greedily."""
    return act(seq(parser, many(parser)), lambda v: [v[0], *v[1]])


def opt(parser: Parser, default: Any = None) -> Parser:
    """The parser, or `default` without consuming anything."""

    def parse(state: State, at: int) -> Result:
        step = parser(state, at)
        return step if step is not None else (at, default)

    return parse


def sep1(parser: Parser, separator: str) -> Parser:
    """One or more, separated. The separators are dropped."""
    return act(
        seq(parser, many(seq(lit(separator), parser))),
        lambda v: [v[0], *(pair[1] for pair in v[1])],
    )


def not_(parser: Parser) -> Parser:
    """Succeeds, consuming nothing, when `parser` does not match.

    PEG's negative lookahead. A top-level `let x = 1` is a definition and
    `let x = 1 in e` is an expression, and this is what tells them apart
    without parsing the whole thing twice.
    """

    def parse(state: State, at: int) -> Result:
        return None if parser(state, at) is not None else (at, None)

    return parse


def guard(parser: Parser, build: Callable[[Any], Any]) -> Parser:
    """The parser, failing where `build` returns None.

    For a rule whose shape is only known once its parts are in hand: `<-`
    needs a record field or an array element on its left, and nothing
    earlier in the grammar says so. Failing rather than raising keeps the
    check inside the backtracking, which an exception would escape.
    """

    def parse(state: State, at: int) -> Result:
        step = parser(state, at)
        if step is None:
            return None
        value = build(step[1])
        return None if value is None else (step[0], value)

    return parse


def act(parser: Parser, build: Callable[[Any], Any]) -> Parser:
    """The parser, with `build` applied to whatever it yielded.

    Whatever it builds is also told where it came from, which is why the
    grammar above needs ninety `act` calls and no position bookkeeping. The
    engine stays ignorant of the language: anything with a `span` attribute
    still unset gets one, and everything else is left alone.

    Already set wins, so a rule that passes an inner node straight through
    keeps that node's narrower span. `(a + b)` points at `a + b`.
    """

    def parse(state: State, at: int) -> Result:
        step = parser(state, at)
        if step is None:
            return None
        built = build(step[1])
        _fill(built, state.span(at, step[0]), root=True)
        return (step[0], built)

    return parse


#: Distinguishes "has no span attribute" from "has one, still unset".
_UNSET = object()


def _fill(
    node: Any, fallback: tuple[int, int], root: bool = False
) -> tuple[int, int] | None:
    """Give every node an action just built a span, innermost first.

    One `act` often builds more than one node. The operator cascade folds a
    row of operands into nested `BinOp`s, and a postfix chain folds into
    nested `ArrayGet`s; only the outermost of those is what `build`
    returned. So this walks what came back and fills what is still unset,
    taking a node's span from the children it was built out of, which is
    exact, and from the text the action consumed when it has none, which is
    right for a node that stands for no text at all.

    The node the action returned is the exception: it spans everything the
    action consumed, keyword included, because that is what it was built
    from. Taking the union of its children instead would lose the `let` in
    front of a `LetItem`.

    A node that already has a span was built by an inner action and its
    subtree is filled, so the walk stops there and the whole pass stays
    linear in the tree.

    `dataclasses` rather than the grammar, so this engine still knows
    nothing about the language it is parsing.
    """
    if getattr(node, "span", _UNSET) is _UNSET:
        return None
    if node.span is not None:
        return node.span
    below = []
    for slot in fields(node):
        if slot.name == "span":
            continue
        held = getattr(node, slot.name)
        for item in held if isinstance(held, list) else [held]:
            found = _fill(item, fallback)
            if found is not None:
                below.append(found)
    if root or not below:
        node.span = fallback
    else:
        node.span = (min(s for s, _ in below), max(e for _, e in below))
    return node.span


@dataclass
class Rule:
    """A named parser, memoized, and settable after it is referred to.

    Both properties are needed: a grammar is mutually recursive, so a rule
    has to exist before its body does, and packrat is what keeps a
    seventeen-level expression cascade linear.
    """

    name: str
    body: Parser | None = None

    def define(self, body: Parser) -> Rule:
        self.body = body
        return self

    def __call__(self, state: State, at: int) -> Result:
        assert self.body is not None, f"rule {self.name} was never defined"
        key = (id(self), at)
        if key in state.memo:
            return state.memo[key]
        state.memo[key] = outcome = self.body(state, at)
        return outcome


def run(parser: Parser, tokens: list[Token], source: str) -> Any:
    """Parse the whole token list, or raise with the furthest failure."""
    state = State(tokens)
    step = parser(state, 0)
    if step is None or state.tokens[step[0]].kind != "eof":
        at = max(state.furthest, step[0] if step else 0)
        found = state.tokens[min(at, len(tokens) - 1)]
        wanted = " or ".join(sorted(state.expected)) or "end of input"
        seen = found.text or "end of input"
        place = where(source, found.at)
        raise ParseError(f"{place}: expected {wanted}, found {seen!r}")
    return step[1]
