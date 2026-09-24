"""The PL/0 example: a compiler for a language that is not Python.

TinyPy checks astero against a Python subset, which leaves one question
open: how much of the library assumed a Python AST? PL/0 answers it. Its
tree is plain dataclasses, its grammar comes from `from_dataclasses`, and
its scope rules are one `Scope` entry written here rather than the ones
`astero.python` ships.

Writing it found that `astero.scopes` iterated fields with
`ast.iter_fields`, so a non-Python tree resolved to an empty scope tree
instead of failing. `test_scopes_over_a_non_python_grammar` is the check
that would have caught it.

The oracle is `interpret.py`, a direct tree-walker sharing only the parser
with the compiler. Weaker than CPython, and stated as such on the tutorial
page.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from astero.python.hygiene import all_names, free_names, rename, taken_names
from astero.scopes import walk

EXAMPLE = Path(__file__).resolve().parents[1]
SOURCE = EXAMPLE / "src/pl0"
ROOT = EXAMPLE.parents[1]

#: What the `pl0` fixture hands a test. `Any` because `parse` is a
#: function and the other six entries are modules.
Modules = dict[str, Any]


@pytest.fixture(scope="module")
def pl0() -> Modules:
    """The example's modules.

    A plain import: the sources are a package under `src/`, which
    `pythonpath` puts in reach, so nothing here touches `sys.path`.

    `dict[str, Any]`, not `dict[str, ModuleType]`: `parse` is a function, so
    a checker that can resolve these modules infers `ModuleType` from the
    other six and refuses to call it.
    """
    from pl0 import analyze, codegen, grammar, interpret, machine, parser, syntax

    return {
        "analyze": analyze,
        "codegen": codegen,
        "grammar": grammar,
        "interpret": interpret,
        "machine": machine,
        "parse": parser.parse,
        "syntax": syntax,
    }


PROGRAMS = {
    "squares": (
        "const m = 10;\nvar x, s;\nprocedure sq; begin s := x * x end;\n"
        "begin x := 1; while x <= m do begin call sq; ! s; x := x + 1 end end."
    ),
    "nested": (
        "var n, r;\nprocedure o;\n  var k;\n  procedure i; begin r := r + n + k end;\n"
        "  begin k := 100; call i; call i end;\n"
        "begin n := 5; r := 0; call o; ! r end."
    ),
    "recursion": (
        "var n, f;\nprocedure fa;\n"
        "  begin if n > 1 then begin f := f * n; n := n - 1; call fa end end;\n"
        "begin n := 6; f := 1; call fa; ! f end."
    ),
    "odd": "var i;\nbegin i := 0; while i < 8 do begin if odd i then ! i; i := i + 1 end end.",
    "gcd": (
        "var a, b;\nbegin a := 48; b := 18;\n"
        "  while a # b do begin if a > b then a := a - b; if b > a then b := b - a end;\n"
        "  ! a end."
    ),
    "signs": "var x;\nbegin x := -3 * 4; ! x; x := (0 - 7) / 2; ! x; x := 7 / (0 - 2); ! x end.",
    "shadowing": (
        "var x;\nprocedure p; var x; begin x := 99; ! x end;\n"
        "begin x := 1; call p; ! x end."
    ),
}


def test_no_module_shadows_a_standard_library_one() -> None:
    """This example is put on `sys.path`, so a module named after a standard
    one shadows it for everything imported afterwards."""

    found = {path.stem for path in SOURCE.glob("*.py")}
    assert found & sys.stdlib_module_names == set()


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_the_compiler_agrees_with_the_interpreter(pl0: Modules, name: str) -> None:
    """The differential claim: two implementations, one answer."""
    tree = pl0["parse"](PROGRAMS[name])
    compiled = pl0["machine"].run(pl0["codegen"].compile_program(tree))
    assert compiled == pl0["interpret"].run(tree)


def test_the_grammar_is_well_formed(pl0: Modules) -> None:
    assert pl0["grammar"].PL0.check() == []


def test_the_roles_answer_for_a_language_that_binds_differently(pl0: Modules) -> None:
    """PL/0 declares before it assigns, and the queries say so.

    In Python `x = 1` introduces `x`; here `var x` does and `x := 1` writes
    to it. Same queries, different answers, because the declarations differ.
    """
    g, vars_, procs = pl0["grammar"].PL0, pl0["grammar"].VARS, pl0["grammar"].PROCS
    assert g.definitions(vars_) == {"Const": ("name",), "Var": ("name",)}
    assert g.operands(vars_) == {"Name": ("name",), "Assign": ("name",)}
    assert g.definitions(procs) == {"Procedure": ("name",)}
    # A namespace keeps the two apart: nothing about procedures shows up
    # when asking about variables.
    assert "Procedure" not in g.definitions(vars_)
    assert "Call" not in g.operands(vars_)


def test_scopes_over_a_non_python_grammar(pl0: Modules) -> None:
    """`scope_tree` works on a tree that is not Python's.

    It did not: it used `ast.iter_fields` and `isinstance(x, ast.AST)`, so
    a dataclass tree produced a root block with no children and no names,
    quietly. The fix reads the fields from the grammar instead.
    """
    from astero.scopes import scope_tree

    g = pl0["grammar"]
    tree = pl0["parse"](PROGRAMS["nested"])
    block = scope_tree(tree, g.PL0, g.SCOPES, g.VARS, root_kind="program")

    assert block.bound == {"n", "r"}
    assert [c.name for c in block.children] == ["o"]
    assert block.children[0].bound == {"k"}
    assert [c.name for c in block.children[0].children] == ["i"]


def test_the_checker_reports_undeclared_names_in_both_namespaces(pl0: Modules) -> None:
    problems = pl0["analyze"].check(pl0["parse"]("var x; begin y := 1; call nope end."))
    assert any("'y'" in p for p in problems)
    assert any("'nope'" in p for p in problems)


def test_a_name_declared_in_an_inner_block_is_not_visible_outside(pl0: Modules) -> None:
    source = "procedure p; var k; begin k := 1 end;\nbegin k := 2 end."
    assert any("'k'" in p for p in pl0["analyze"].check(pl0["parse"](source)))


def test_every_production_has_an_emission_rule(pl0: Modules) -> None:
    """The gate, from the class hierarchy rather than from a list."""
    cover = pl0["codegen"].coverage()
    assert not cover.missing, cover.explain()


# ---------------------------------------------------------------------------
# The tutorial page, gated against the example
# ---------------------------------------------------------------------------

TUTORIAL = ROOT / "docs/src/tutorial-pl0.md"

#: Blocks that are output, or a fragment shown without its context.
ILLUSTRATIVE = ("Ident = str",)


def _python_blocks(text: str) -> list[str]:
    import re

    return re.findall(r"```python\n(.*?)```", text, re.DOTALL)


def test_every_snippet_appears_in_the_example() -> None:
    """A tutorial whose code has drifted from the code it describes lies."""
    flat = " ".join(
        " ".join(f.read_text(encoding="utf-8").split())
        for f in sorted(SOURCE.glob("*.py"))
    )
    missing = []
    for block in _python_blocks(TUTORIAL.read_text(encoding="utf-8")):
        if any(mark in block for mark in ILLUSTRATIVE):
            continue
        if " ".join(block.split()) not in flat:
            missing.append(block.strip().splitlines()[0])
    assert not missing, f"snippets not found in examples/pl0: {missing}"


def test_the_tutorials_claimed_outputs(pl0: Modules) -> None:
    """The figures the page prints, asserted rather than remembered."""
    expected = {
        "squares": [1, 4, 9, 16, 25, 36, 49, 64, 81, 100],
        "nested": [210],
        "recursion": [720],
        "gcd": [6],
        "shadowing": [99, 1],
    }
    for name, want in expected.items():
        tree = pl0["parse"](PROGRAMS[name])
        assert pl0["machine"].run(pl0["codegen"].compile_program(tree)) == want


def test_the_tutorials_scope_tree(pl0: Modules) -> None:
    """The tree the page prints, character for character.

    It sat in a plain fence, so `test_every_snippet_appears_in_the_example`
    skipped it and nothing checked it. The columns had been tidied by hand
    and were not what `Block.__str__` produces.
    """
    from astero.scopes import scope_tree

    g = pl0["grammar"]
    tree = pl0["parse"](PROGRAMS["nested"])
    block = scope_tree(
        tree, g.PL0, g.SCOPES, g.VARS, root_kind="program", root_name="main"
    )
    printed = str(block)

    page = TUTORIAL.read_text(encoding="utf-8")
    assert printed in page, f"the page does not show this tree:\n{printed}"


# ------------------------------------------------- hygiene over a non-Python tree


def test_the_name_queries_answer_for_a_grammar_with_no_python_nodes(
    pl0: Modules,
) -> None:
    """`taken_names` said no name was taken, and did not raise saying so.

    Every name query in `hygiene` is computed from the grammar's identifier
    slots — except the walk, which was `ast.walk` and reads `node._fields`. A
    PL/0 node has no `_fields`, so the walk yielded nothing and every query
    over it answered emptily. `rename` was the loud half: it raised. These
    were the quiet half, and a caller generating fresh names against an empty
    `taken_names` would have collided with every name in the program.

    The same mistake is recorded twice already in `scopes`: `_is_node`'s note
    about testing `isinstance(value, ast.AST)`, and `_fields_of`'s about
    `ast.iter_fields`. `scopes.walk` is the third fix and the shared one.
    """
    grammar, syntax = pl0["grammar"], pl0["syntax"]
    tree = syntax.Block(
        variables=[syntax.Var(name="x")],
        body=syntax.Begin(
            body=[
                syntax.Assign(
                    name="x",
                    value=syntax.BinOp(
                        op="+", left=syntax.Name(name="x"), right=syntax.Number(value=1)
                    ),
                )
            ]
        ),
    )

    assert taken_names([tree], grammar.PL0) == {"x"}
    assert all_names(tree, grammar.PL0) == {"x"}
    assert free_names(tree, grammar.PL0, grammar.VARS) == set()

    renamed = rename(tree, {"x": "y"}, grammar.PL0, grammar.VARS)
    assert renamed.variables[0].name == "y"
    assert renamed.body.body[0].name == "y"
    assert renamed.body.body[0].value.left.name == "y"


def test_the_walk_reaches_every_pl0_node(pl0: Modules) -> None:
    """The piece the queries above are built on, checked on its own."""
    grammar, syntax = pl0["grammar"], pl0["syntax"]
    tree = syntax.Block(
        variables=[syntax.Var(name="x")],
        body=syntax.Begin(body=[syntax.Assign(name="x", value=syntax.Number(value=1))]),
    )
    seen = {type(node).__name__ for node in walk(tree, grammar.PL0)}
    assert seen == {"Block", "Var", "Begin", "Assign", "Number"}
