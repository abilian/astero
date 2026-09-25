"""What a single node binds, without fetching its `Field` first.

`bound_names` answers for one field, so a caller had to find the production,
fetch the `Field` and pass its sort. Every consumer wrote that dance, and
writing the tutorial made it obvious enough to fix: `names_bound_by` is the
identifier twin of `Grammar.binds`, which answers for slot contents.
"""

from __future__ import annotations

import ast
import dataclasses

import pytest

from astero.python import BINDING_SCOPES, PY, VARS
from astero.scopes import binds_in_scope, names_bound_by


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x = 1", {"x"}),
        ("a, b = 1, 2", {"a", "b"}),
        ("[a, *rest] = xs", {"a", "rest"}),
        ("for k, v in d: pass", {"k", "v"}),
        ("def g(a): pass", {"g"}),
        ("class C: pass", {"C"}),
        # A subscript target binds nothing, and `del` is not a binding.
        ("b[0] = 1", set()),
        ("del x", set()),
    ],
)
def test_names_bound_by_a_node(source: str, expected: set[str]) -> None:
    assert names_bound_by(ast.parse(source).body[0], PY, VARS) == expected


@pytest.mark.parametrize(
    ("source", "path", "expected"),
    [
        ("with open(f) as fh: pass", lambda n: n.items[0], {"fh"}),
        ("import a.b as c", lambda n: n.names[0], {"c"}),
        ("try:\n  pass\nexcept E as err:\n  pass", lambda n: n.handlers[0], {"err"}),
    ],
)
def test_the_binding_may_live_on_a_child(source, path, expected) -> None:
    """The node only, like `Grammar.binds`. A pass walks and asks each node."""
    node = ast.parse(source).body[0]
    assert names_bound_by(node, PY, VARS) == set()
    assert names_bound_by(path(node), PY, VARS) == expected


# ---------------------------------------------------------------------------
# binds_in_scope
#
# `names_bound_by` answers for one node and `scope_tree` for a whole module.
# A pass walking a tree itself wants the middle question, and writing that
# walk by hand is where it goes wrong: it has to reach through a `withitem`
# and stop at a `def`. Porting postpile's definite-assignment analysis is
# what showed the walk was missing.
# ---------------------------------------------------------------------------

STMTS = PY.concrete("stmt")


def _binds(source: str, **kwargs) -> set[str]:
    return binds_in_scope(ast.parse(source).body[0], PY, VARS, BINDING_SCOPES, **kwargs)


def test_a_definition_binds_only_its_own_name_here() -> None:
    """Parameters and body belong to the function, so they are not this
    scope's business. Getting that wrong is what the layer table prevents."""
    assert _binds("def f(a, b=1, *c, d, **e):\n    x = 1\n") == {"f"}
    assert _binds("async def g(a):\n    y = 1\n") == {"g"}
    assert _binds("class C(Base):\n    z = 1\n") == {"C"}
    assert _binds("h = lambda a: (z := a)") == {"h"}


def test_it_reaches_through_the_nodes_that_carry_the_binding() -> None:
    """None of `withitem`, `alias`, `ExceptHandler` or a match pattern is
    named here; the walk finds them because the grammar declares them."""
    assert _binds("with open(p) as fh, q() as (a, b):\n    pass\n") == {"fh", "a", "b"}
    assert _binds("import a.b as c, d") == {"c", "d"}
    assert _binds("from m import x as y, z") == {"y", "z"}
    assert _binds("try:\n    pass\nexcept E as err:\n    pass\n", stop=STMTS) == {"err"}
    assert _binds(
        "match p:\n    case {'k': v, **rest}:\n        pass\n", stop=STMTS
    ) == {"v", "rest"}


def test_a_comprehension_target_does_not_leak() -> None:
    """True on every supported version. PEP 709 stopped a comprehension
    opening a `symtable` block in 3.12 and left its target local, which is
    why this takes `BINDING_SCOPES` and not `SCOPES`."""
    assert _binds("v = [x for x in xs]") == {"v"}
    assert _binds("v = {k: w for k, w in pairs}") == {"v"}
    assert _binds("v = sum(g for g in xs)") == {"v"}


def test_stop_bounds_the_walk_to_one_statement() -> None:
    """What a flow analysis wants: the `for` reports its target and the
    walrus its iterable evaluates, and says nothing about the body."""
    source = "for i in (n := r):\n    y = 1\n"
    assert _binds(source, stop=STMTS) == {"i", "n"}
    assert _binds(source) == {"i", "n", "y"}


def test_the_node_asked_about_is_always_entered() -> None:
    """`stop` names what the walk will not descend into. The root is the
    question, so it is entered whatever `stop` says."""
    assert _binds("x = 1", stop=STMTS) == {"x"}
    assert _binds("x: int = 1", stop=STMTS) == {"x"}


def test_it_works_over_a_grammar_that_is_not_pythons() -> None:
    """The walk reads fields from the grammar, so a tree of dataclasses
    resolves. `scopes` being Python-only was a real defect once."""
    from astero.grammar import defines, from_dataclasses

    @dataclasses.dataclass
    class Var:
        name: str

    @dataclasses.dataclass
    class Block:
        decls: list

    grammar = from_dataclasses(
        "toy",
        [Var, Block],
        roles={"Var": {"name": defines("v")}},
        namespaces=("v",),
        ident_sorts=("str",),
    )
    tree = Block(decls=[Var(name="a"), Var(name="b")])
    assert binds_in_scope(tree, grammar, "v", {}) == {"a", "b"}


#: One of every construct an `outside` path can name.
_EVERY_POSITION = (
    "def f(a: A = 1, /, b: B = 2, *c: C, d: D = 3, **e: E): pass\n"
    "async def g(a: A = 1, /, b: B = 2, *c: C, d: D = 3, **e: E): pass\n"
    "h = lambda a=1, *, b=2: a\n"
    "w = (i for i in xs)\n"
    "x = [i for i in xs]\n"
    "y = {i for i in xs}\n"
    "z = {i: i for i in xs}\n"
)


def test_every_outside_path_names_a_real_position() -> None:
    """`outside` is authored, so it is held against the parser: each path
    must start in a field the layer holds inside, and reach a node in a tree
    that has every construct. A misspelt field reaches nothing."""
    from astero.python import SCOPES
    from astero.scopes import evaluated_outside

    tree = ast.parse(_EVERY_POSITION)
    checked = 0
    for table in (SCOPES, BINDING_SCOPES):
        for production, layers in table.items():
            nodes = [n for n in ast.walk(tree) if type(n).__name__ == production]
            for layer in layers:
                for path in layer.outside:
                    assert path.split(".")[0] in layer.inside, f"{production}: {path}"
                    one = dataclasses.replace(layer, outside=(path,))
                    assert any(evaluated_outside(n, one) for n in nodes), (
                        f"{production}: {path} reaches nothing"
                    )
                    checked += 1
    assert checked >= 20


def test_what_a_function_evaluates_outside_binds_outside() -> None:
    """A walrus in a default binds around the function, as CPython has it."""
    tree = ast.parse("def f(k=(y := 1)):\n    return y\n")
    assert binds_in_scope(tree.body[0], PY, VARS, BINDING_SCOPES) == {"f", "y"}
