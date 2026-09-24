"""Emitting Python source, one construct at a time.

`test_emit_roundtrip.py` runs the same oracle over the whole standard
library, which is the real evidence and takes minutes. It also reports
"some module did not round-trip" rather than which construct broke.

These are the same check on hand-picked constructs, in milliseconds: parse,
emit, reparse, and compare structurally with `rewriting.key`, which skips
the fields the parser derives. A failure here names the syntax.

`EXACT` is the second half. Round-tripping says the tree survived; it says
nothing about what the text looks like, so a handful of forms assert their
output character for character and a formatting change has to be
deliberate.
"""

from __future__ import annotations

import ast
import sys

import pytest

from astero.python.emit import emit, emit_module
from astero.python.rewriting import DERIVED, key

#: One entry per construct family. Parsed as a module, so statements are
#: allowed and an expression is written as an expression statement.
SOURCES: list[tuple[str, str]] = [
    ("constants", "x = (1, 1.5, 1j, 'a', b'b', True, None, ...)\n"),
    ("names and attributes", "a.b.c = d[0].e\n"),
    ("arithmetic", "x = 1 + 2 * 3 - 4 / 5 // 6 % 7 ** 8\n"),
    ("bitwise and shifts", "x = a | b ^ c & d << e >> f\n"),
    ("unary", "x = -a + ~b + (not c) + (+d)\n"),
    ("comparison chains", "x = a < b <= c == d != e >= f > g\n"),
    ("membership and identity", "x = a in b or a not in b or a is b or a is not b\n"),
    ("boolean operators", "x = a and b or c and d\n"),
    ("conditional expression", "x = a if b else c\n"),
    ("lambda", "f = lambda a, b=1, *c, d, **e: a\n"),
    ("call forms", "f(a, b=1, *c, **d)\n"),
    ("containers", "x = [1], (2,), {3}, {4: 5}, []\n"),
    ("comprehensions", "x = [i for i in r if i]\ny = {k: v for k, v in p}\n"),
    ("nested comprehension", "x = [a for b in c for a in b if a if b]\n"),
    ("generator and set comprehension", "x = sum(i for i in r)\ny = {i for i in r}\n"),
    ("slices", "x = a[1:2, ::3, ..., b:, :c]\n"),
    ("starred and double-starred", "x = [*a, *b]\ny = {**c, **d}\n"),
    ("f-string", 'x = f"a{b!r:>{w}}c"\n'),
    ("walrus", "if (n := f()) > 0:\n    pass\n"),
    ("await and async", "async def f():\n    await g()\n"),
    ("assignment forms", "a = b = 1\nc: int = 2\nd: int\ne += 3\n"),
    ("unpacking targets", "(a, (b, *c)), [d] = e\n"),
    ("if/elif/else", "if a:\n    pass\nelif b:\n    pass\nelse:\n    pass\n"),
    ("while/else", "while a:\n    break\nelse:\n    pass\n"),
    ("for/else", "for i in r:\n    continue\nelse:\n    pass\n"),
    ("with", "with a as b, c() as (d, e):\n    pass\n"),
    (
        "async for and with",
        "async def f():\n    async with a:\n        async for b in c:\n            pass\n",
    ),
    (
        "try/except/else/finally",
        "try:\n    pass\nexcept E as err:\n    pass\nexcept (F, G):\n    pass\nelse:\n    pass\nfinally:\n    pass\n",
    ),
    ("raise from", "raise E('x') from cause\n"),
    ("assert", "assert a, 'why'\n"),
    ("del, global, nonlocal", "def f():\n    global g\n    del a, b\n"),
    ("imports", "import a.b.c as d, e\nfrom . import f\nfrom ..g import h as i\n"),
    ("star import", "from a import *\n"),
    (
        "function with decorators",
        "@deco\n@mod.deco(1)\ndef f(a, /, b=1, *c, d=2, **e) -> int:\n    return a\n",
    ),
    ("class", "@deco\nclass C(Base, metaclass=M):\n    x = 1\n"),
    ("docstring and pass", "def f():\n    'doc'\n    pass\n"),
    ("yield forms", "def f():\n    yield\n    yield 1\n    x = yield from g()\n"),
    ("nested functions", "def f():\n    def g():\n        return 1\n    return g\n"),
]

SOURCES += [
    (
        "match",
        (
            "match p:\n"
            "    case [1, *rest] | (2, 3):\n        pass\n"
            "    case {'k': v, **extra}:\n        pass\n"
            "    case C(x=1) as whole if whole:\n        pass\n"
            "    case _:\n        pass\n"
        ),
    ),
    ("except*", "try:\n    pass\nexcept* E:\n    pass\n"),
]

if sys.version_info >= (3, 12):
    SOURCES += [
        ("type alias", "type A[T] = list[T]\n"),
        (
            "PEP 695 generics",
            "def f[T](x: T) -> T:\n    return x\nclass C[*Ts, **P]:\n    pass\n",
        ),
    ]

IDS = [name for name, _ in SOURCES]


@pytest.mark.parametrize(("_name", "source"), SOURCES, ids=IDS)
def test_a_module_round_trips(_name: str, source: str) -> None:
    """Emit it, parse the result, and compare the trees."""
    tree = ast.parse(source)
    emitted = emit_module(tree)
    assert key(ast.parse(emitted), DERIVED) == key(tree, DERIVED), emitted


@pytest.mark.parametrize(("_name", "source"), SOURCES, ids=IDS)
def test_emission_is_stable(_name: str, source: str) -> None:
    """Emitting what was emitted changes nothing. A pass that adds a bracket
    every time round would round-trip and still be wrong."""
    once = emit_module(ast.parse(source))
    assert emit_module(ast.parse(once)) == once


#: Text, not just structure. Bracketing is the reason: a correct tree can be
#: printed with brackets nobody needs, and only the text says so.
EXACT: list[tuple[str, str]] = [
    ("a + b * c", "a + b * c"),
    ("(a + b) * c", "(a + b) * c"),
    ("a - (b - c)", "a - (b - c)"),
    ("a - b - c", "a - b - c"),
    ("a ** b ** c", "a ** b ** c"),
    ("(a ** b) ** c", "(a ** b) ** c"),
    ("-(a ** b)", "-a ** b"),
    ("(-a) ** b", "(-a) ** b"),
    ("not (a and b)", "not (a and b)"),
    ("(a if b else c) + d", "(a if b else c) + d"),
    ("(lambda: 1)()", "(lambda: 1)()"),
    ("a[b][c]", "a[b][c]"),
    ("(a, b)[0]", "(a, b)[0]"),
]


@pytest.mark.parametrize(("source", "want"), EXACT, ids=[s for s, _ in EXACT])
def test_the_emitted_text_is_exactly_this(source: str, want: str) -> None:
    assert emit(ast.parse(source, mode="eval").body) == want


def test_emit_refuses_nothing_it_can_reach() -> None:
    """Every expression production the grammar declares reaches a rule.

    `emit` raises rather than emitting a placeholder, so this would fail
    loudly. It is here because the corpus cannot promise it saw every one.
    """
    from astero.python import PY

    missing = []
    for source in (s for _n, s in SOURCES):
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.expr):
                continue
            try:
                emit(node)
            except Exception as error:
                missing.append(f"{type(node).__name__}: {error}")
    assert not missing, missing
    assert len(PY.concrete("expr")) > 20
