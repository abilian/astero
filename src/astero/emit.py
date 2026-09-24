"""Emission: documents, and parenthesization derived from declared precedence.

Every compiler in the corpus builds target text by concatenating strings, and
every one of them hand-rolls the question of when a subexpression needs
brackets. That question has a known answer given a precedence table, so the
table is declared and the brackets are derived.

Two pieces.

A **document** is a tree, not a string: text, concatenation, nesting, and a
line break that a group may or may not take. Layout becomes the renderer's
job, and a span rides on a document, so a source map is a projection of the
emitted document rather than a structure threaded alongside the emitter.

A **precedence table** gives each production a binding power and an
associativity. A child is bracketed when its power is lower than the position
it sits in, which is the whole rule. Nothing is written per production.
"""

from __future__ import annotations

import enum
from collections.abc import Iterator
from dataclasses import dataclass, field

# ------------------------------------------------------------------ documents


@dataclass(frozen=True)
class Doc:
    """A layout-independent rendering, with an optional source span."""

    span: tuple[int, int] | None = None

    def __add__(self, other: Doc) -> Doc:
        # Keyword rather than positional: `span` is the inherited first field,
        # so a positional argument here becomes the span and the parts are
        # lost. The emitter rendered empty strings until this was found.
        return Concat(parts=(self, other))


@dataclass(frozen=True)
class Text(Doc):
    text: str = ""


@dataclass(frozen=True)
class Concat(Doc):
    parts: tuple[Doc, ...] = ()


@dataclass(frozen=True)
class Nest(Doc):
    """Indent everything inside by `indent` columns after a line break."""

    indent: int = 4
    doc: Doc = field(default_factory=lambda: Text(text=""))


@dataclass(frozen=True)
class Line(Doc):
    """A hard break, followed by the indentation in force where it appears.

    In Python indentation is semantic, so a break in a statement body is a
    correctness question rather than a cosmetic one. A soft break that a group
    may flatten to fit a width is a separate concept and is not needed yet.
    """


def text(value: str, span: tuple[int, int] | None = None) -> Doc:
    return Text(text=value, span=span)


def concat(*parts: Doc) -> Doc:
    return Concat(parts=parts)


def joined(sep: str, parts: list[Doc]) -> Doc:
    out: list[Doc] = []
    for i, part in enumerate(parts):
        if i:
            out.append(Text(text=sep))
        out.append(part)
    return Concat(parts=tuple(out))


def render(doc: Doc, indent: int = 0) -> str:
    """Text for a document. A `Line` breaks and re-indents to its `Nest` depth."""
    return "".join(_render(doc, indent))


def _render(doc: Doc, indent: int) -> Iterator[str]:
    match doc:
        case Text():
            yield doc.text
        case Concat():
            for part in doc.parts:
                yield from _render(part, indent)
        case Nest():
            yield from _render(doc.doc, indent + doc.indent)
        case Line():
            yield "\n" + " " * indent


def line() -> Doc:
    return Line()


def nest(doc: Doc, indent: int = 4) -> Doc:
    return Nest(indent=indent, doc=doc)


def spans(
    doc: Doc, offset: int = 0, indent: int = 0
) -> Iterator[tuple[int, int, tuple[int, int]]]:
    """(start, end, span) for every document carrying one.

    A source map is this list, and `start` and `end` index `render(doc)`.

    `indent` is not decoration. A `Line` renders as a break plus the
    indentation in force, so everything after one inside a `Nest` is wider
    than the same document rendered at column zero. Measuring the parts at
    zero put every offset after the first break too far left, which a
    caller would have seen as a source map that drifts down the file. The
    emitter threads no source map, so nothing here noticed.
    """
    length = len(render(doc, indent))
    if doc.span is not None:
        yield (offset, offset + length, doc.span)
    match doc:
        case Concat():
            for part in doc.parts:
                yield from spans(part, offset, indent)
                offset += len(render(part, indent))
        case Nest():
            yield from spans(doc.doc, offset, indent + doc.indent)


def joined_by(sep: Doc, parts: list[Doc]) -> Doc:
    """Like `joined`, with a document separator rather than a string."""
    out: list[Doc] = []
    for i, part in enumerate(parts):
        if i:
            out.append(sep)
        out.append(part)
    return Concat(parts=tuple(out))


# ----------------------------------------------------------------- precedence


class Assoc(enum.Enum):
    LEFT = "left"
    RIGHT = "right"
    NONE = "none"


@dataclass(frozen=True)
class Level:
    """A binding power and how it associates."""

    power: int
    assoc: Assoc = Assoc.LEFT


def needs_parens(inner: Level, outer: Level, *, on_right: bool) -> bool:
    """Whether a subexpression at `inner` needs brackets inside `outer`.

    The whole parenthesization rule, in three lines, given a table. A child
    binding less tightly always needs them; a child binding equally tightly
    needs them on the side the operator does not associate towards.
    """
    if inner.power < outer.power:
        return True
    if inner.power > outer.power:
        return False
    if outer.assoc is Assoc.LEFT:
        return on_right
    if outer.assoc is Assoc.RIGHT:
        return not on_right
    return True


#: A primary: the tightest thing there is, and never bracketed.
ATOM = Level(100)

#: What a production that declares *no* binding power imposes on its children.
#: A statement is not an operator, so nothing about `t = 0` says that `0` is
#: bracketed, and a table that omits a production says exactly that. Every
#: declared level is above this one.
FREE = Level(0)
