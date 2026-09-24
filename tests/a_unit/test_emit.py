"""The document layer: rendering, bracketing, and source spans.

`emit_rules` and `astero.python.emit` are tested through what they emit, which reaches
most of this module incidentally. `spans` is the exception: it is the piece
a source map would be built from, nothing in the library threads one, and
so nothing exercised it at all.
"""

from __future__ import annotations

from astero.emit import (
    ATOM,
    FREE,
    Assoc,
    Concat,
    Level,
    Line,
    Nest,
    Text,
    needs_parens,
    render,
    spans,
)


def test_spans_are_offsets_into_the_rendered_text() -> None:
    """Each (start, end) indexes `render(doc)`, and carries the source span."""
    doc = Concat(parts=(Text(text="ab", span=(0, 2)), Text(text="cde", span=(4, 7))))
    out = list(spans(doc))
    assert out == [(0, 2, (0, 2)), (2, 5, (4, 7))]
    text = render(doc)
    assert [text[start:end] for start, end, _ in out] == ["ab", "cde"]


def test_a_document_with_no_span_contributes_none() -> None:
    doc = Concat(parts=(Text(text="ab"), Text(text="cd", span=(9, 11))))
    assert list(spans(doc)) == [(2, 4, (9, 11))]


def test_a_span_on_a_composite_covers_everything_under_it() -> None:
    inner = Text(text="xy", span=(3, 5))
    doc = Concat(parts=(Text(text="a"), inner), span=(0, 5))
    assert list(spans(doc)) == [(0, 3, (0, 5)), (1, 3, (3, 5))]


def test_spans_reach_through_a_nest() -> None:
    """`Nest` indents its content, so the offsets are of the rendered form."""
    doc = Nest(indent=2, doc=Concat(parts=(Line(), Text(text="body", span=(7, 11)))))
    text = render(doc)
    out = list(spans(doc))
    assert out == [(3, 7, (7, 11))]
    assert text[3:7] == "body"


def test_an_offset_shifts_every_span() -> None:
    doc = Text(text="ab", span=(0, 2))
    assert list(spans(doc, 10)) == [(10, 12, (0, 2))]


# ------------------------------------------------------------- bracketing


def test_a_tighter_operand_needs_no_brackets() -> None:
    assert not needs_parens(Level(12), Level(11), on_right=False)
    assert needs_parens(Level(11), Level(12), on_right=False)


def test_associativity_decides_the_equal_case() -> None:
    """`a - (b - c)` brackets on the right of a left-associative operator."""
    left = Level(11, Assoc.LEFT)
    assert not needs_parens(left, left, on_right=False)
    assert needs_parens(left, left, on_right=True)

    right = Level(14, Assoc.RIGHT)
    assert needs_parens(right, right, on_right=False)
    assert not needs_parens(right, right, on_right=True)

    none = Level(9, Assoc.NONE)
    assert needs_parens(none, none, on_right=False)
    assert needs_parens(none, none, on_right=True)


def test_an_atom_is_never_bracketed_and_free_never_brackets() -> None:
    assert not needs_parens(ATOM, Level(99), on_right=False)
    assert not needs_parens(Level(1), FREE, on_right=False)
