"""Programs that exercise every declared role.

The grammar says which positions bind, which declare, and which open a scope.
That list is also a coverage obligation: each one is a case the derivations
have to get right, and the standard library is not guaranteed to contain a
good example of each.

So the generator is driven by the declaration rather than by a hand-written
list of interesting programs. Ask the grammar for its binding positions, emit a
program per position, and a role added to the declaration is fuzzed from the
moment it is declared. `missing_coverage` is what turns that from a claim into
a check.

Each snippet is ordinary Python source, so the oracles are CPython's own:
`ast.parse` for contexts, `symtable` for scopes.
"""

from __future__ import annotations

import ast
import random
import sys
from collections.abc import Iterator, Mapping

from astero.grammar import Grammar, Kind
from astero.scopes import Scope

#: One snippet per production that binds, declares, or opens a scope. Keyed by
#: the production it exists to exercise, so coverage is checkable.
SNIPPETS: dict[str, str] = {
    "Assign": "a = 1\nb = c = 2\n(d, e), [f] = (1, 2), [3]\n*g, h = [1, 2, 3]\n",
    "AnnAssign": "i: int = 1\nj: str\n",
    "AugAssign": "k = 0\nk += 1\n",
    "For": "for m in range(3):\n    pass\nfor n, o in [(1, 2)]:\n    pass\n",
    "AsyncFor": "async def f0():\n    async for p in q:\n        pass\n",
    "FunctionDef": (
        "def deco(fn):\n    return fn\n"
        "def f1(a1, /, b1=1, *c1, d1=2, **e1) -> int:\n    return a1\n"
        "@deco\ndef f2():\n    pass\n"
    ),
    "AsyncFunctionDef": "async def f3(a2):\n    return a2\n",
    "ClassDef": (
        "class Base:\n    pass\n"
        "class M(type):\n    pass\n"
        "class C1(Base, metaclass=M):\n"
        "    x1 = 1\n"
        "    def m1(self):\n        return self\n"
    ),
    "arg": "def f4(a3, *b3, c3, **d3):\n    return a3\nlambda e3, *f3, **g3: e3\n",
    "Lambda": "h3 = lambda i3: i3 + 1\n",
    "comprehension": "j3 = [k3 for k3 in range(3)]\n",
    # Before PEP 709 each of these opened a scope, so each is its own
    # obligation on 3.11.
    "ListComp": "j5 = [k5 for k5 in range(3)]\n",
    "SetComp": "l5 = {m5 for m5 in []}\n",
    "DictComp": "n5 = {o5: p5 for o5, p5 in []}\n",
    "GeneratorExp": "q3 = (r3 for r3 in range(3))\n",
    "NamedExpr": "if (s3 := 1):\n    pass\n",
    "withitem": "with open('x') as t3, open('y') as (u3, v3):\n    pass\n",
    "ExceptHandler": "try:\n    pass\nexcept ValueError as w3:\n    pass\n",
    "alias": (
        "import os\nimport os.path\nimport json as x3\n"
        "from re import sub\nfrom re import sub as y3\n"
    ),
    "Global": "z3 = 0\ndef f5():\n    global z3\n    z3 = 1\n",
    "Nonlocal": (
        "def f6():\n    a4 = 0\n"
        "    def g6():\n        nonlocal a4\n        a4 = 1\n"
        "    return g6\n"
    ),
    "MatchAs": (
        "v1 = [1, 2]\n"
        "match v1:\n    case [1, b4]:\n        pass\n"
        "match 3:\n    case c4:\n        pass\n"
    ),
    "MatchStar": "v2 = [1, 2, 3]\nmatch v2:\n    case [1, *d4]:\n        pass\n",
    "MatchMapping": (
        "v3 = {'k': 1, 'z': 2}\nmatch v3:\n    case {'k': e4, **f4}:\n        pass\n"
    ),
    "Delete": "g4 = 1\ndel g4\n",
    # Private mangling, the case a renaming pass gets wrong.
    "mangling": (
        "class C2:\n    __h4 = 1\n"
        "    def m2(self):\n        __i4 = 2\n        return __i4\n"
    ),
    # A class body is invisible to the functions nested in it.
    "class_scope": ("class C3:\n    j4 = 1\n    def m3(self):\n        return j4\n"),
}

if sys.version_info >= (3, 12):
    SNIPPETS |= {
        "TypeAlias": "type T1 = int\n",
        "TypeVar": "def f7[T2](x: T2) -> T2:\n    return x\n",
        "TypeVarTuple": "def f8[*T3](x):\n    return x\n",
        "ParamSpec": "def f9[**T4](x):\n    return x\n",
    }


def snippets() -> Mapping[str, str]:
    """Every snippet, keyed by the production it exercises."""
    return dict(SNIPPETS)


def missing_coverage(
    grammar: Grammar, scopes: Mapping[str, tuple[Scope, ...]], ns: str
) -> set[str]:
    """Declared positions with no snippet exercising them.

    The point of the whole module: a role added to the declaration and not to
    the corpus shows up here rather than going untested.

    `scopes` is a layer table, `astero.python.SCOPES` or one like it. Only its keys
    are read; the annotation said `Mapping[str, Scope]`, which no caller has
    ever passed.
    """
    obliged = (
        set(grammar.positions((Kind.DEF, Kind.DEFUSE), ns))
        | set(grammar.positions(Kind.DECLARE, ns))
        | set(scopes)
    )
    return obliged - set(SNIPPETS)


def _indent(body: str, levels: int) -> str:
    pad = "    " * levels
    return "\n".join(pad + line for line in body.splitlines())


#: How a snippet gets nested. Each returns the wrapped source.
WRAPPERS = (
    lambda name, body: f"def {name}():\n{_indent(body, 1)}\n",
    lambda name, body: f"class {name}:\n{_indent(body, 1)}\n",
    lambda name, body: f"async def {name}():\n{_indent(body, 1)}\n",
    lambda name, body: (
        f"def {name}():\n    def inner():\n{_indent(body, 2)}\n    return inner\n"
    ),
)


def combinations(count: int, seed: int = 0) -> Iterator[str]:
    """Snippets nested inside one another, to reach the interactions.

    A binding position inside a comprehension inside a class body is where the
    hand-written binders in the corpus go wrong, and no single snippet gets
    there. The generator is seeded, so a failure is reproducible.
    """
    rng = random.Random(seed)
    bodies = [text for text in SNIPPETS.values() if "\n" in text]
    for index in range(count):
        source = rng.choice(WRAPPERS)(f"v{index}", rng.choice(bodies))
        try:
            ast.parse(source)
        except SyntaxError:
            continue
        yield source
