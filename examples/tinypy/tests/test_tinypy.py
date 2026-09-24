"""The documentation's code is code, and it is checked.

The home page's examples each claim an output in a comment. Three claims in
the first draft of these docs were wrong — a count, a function signature, and
an object that turned out not to be iterable — and none of them would have
been caught by reading. So the claimed outputs are asserted here.

Below that: the tutorial's code is the example's code.

`docs/tutorial.md` walks through `examples/tinypy/`. A tutorial whose snippets
have drifted from the thing they describe is worse than none, and this project
has a name for that failure: authored data must be gated against what it
mirrors. So every fenced Python block in the tutorial is checked to appear in
the example, and the example is checked to still compile and run.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[1]
SOURCE = EXAMPLE / "src/tinypy"
ROOT = EXAMPLE.parents[1]
TUTORIAL = ROOT / "docs/src/tutorial.md"

#: Snippets that are deliberately not verbatim: output, an ellipsis, or a call
#: a reader makes rather than something the example contains.
ILLUSTRATIVE = ("STORE 0", "code = compile_source(")


def _python_blocks(text: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", text, re.DOTALL)


def _normalise(code: str) -> str:
    """Compare on tokens, not layout: the example is ruff-formatted."""
    return " ".join(code.split())


@pytest.fixture(scope="module")
def sources() -> str:
    return "\n".join(f.read_text(encoding="utf-8") for f in sorted(SOURCE.glob("*.py")))


def test_no_module_shadows_a_standard_library_one() -> None:
    """A package cannot shadow a standard module, and this holds it that way.

    `pl0` and `tinypy` used to be directories of top-level modules put on
    `sys.path`, where `syntax`, `parser` or `types` would shadow the
    standard one for everything imported afterwards. They are packages now,
    and this is what keeps a module from being named as if they were not.
    """

    found = {path.stem for path in SOURCE.glob("*.py")}
    assert found & sys.stdlib_module_names == set()


def test_the_tutorial_and_the_example_exist() -> None:
    assert TUTORIAL.is_file()
    assert (SOURCE / "compiler.py").is_file()
    assert len(_python_blocks(TUTORIAL.read_text(encoding="utf-8"))) >= 6


def test_every_snippet_appears_in_the_example(sources: str) -> None:
    """A snippet that no longer matches is a tutorial that lies."""
    flat = _normalise(sources)
    missing = []
    for block in _python_blocks(TUTORIAL.read_text(encoding="utf-8")):
        if any(mark in block for mark in ILLUSTRATIVE) or "..." in block:
            continue
        if _normalise(block) not in flat:
            missing.append(block.strip().splitlines()[0])
    assert not missing, f"snippets not found in examples/tinypy: {missing}"


PROGRAMS = [
    (
        "def f(n):\n    t = 0\n    i = 0\n    while i < n:\n        t += i\n"
        "        i = i + 1\n    return t\n"
    ),
    "def f(n):\n    if n > 10:\n        return n * 2\n    else:\n        return n - 1\n",
    (
        "def f(n):\n    t = 0\n    i = 0\n    while i < n:\n        if i % 2 == 0:\n"
        "            t += i\n        i += 1\n    return t\n"
    ),
    "def f(n):\n    return (n * 3 + 7) // 2 - n % 4\n",
]


@pytest.mark.parametrize("source", PROGRAMS)
@pytest.mark.parametrize("argument", [0, 1, 7, 12, 25])
def test_the_example_agrees_with_cpython(source: str, argument: int) -> None:
    """The tutorial claims the compiler is correct. This is that claim."""
    from tinypy import compiler as tinypy, vm

    expected: dict = {}
    exec(compile(source, "<program>", "exec"), expected)
    assert vm.run(tinypy.compile_source(source), argument) == expected["f"](argument)


def test_the_example_refuses_what_it_does_not_admit() -> None:
    from tinypy import compiler as tinypy

    problems = tinypy.check(ast.parse("def f():\n    return [x for x in y]\n"))
    assert problems
    assert "ListComp" in problems[0]


# ---------------------------------------------------------------------------
# The home page's examples, and the outputs they claim
# ---------------------------------------------------------------------------


def test_the_query_examples() -> None:
    from astero.python import PY, VARS

    assert PY.ident_slots(VARS)["arg"] == ("arg",)
    assert PY.definitions(VARS)["For"] == ("target",)
    assert PY.definitions(VARS)["FunctionDef"] == ("name",)
    # The page claims a namespace narrows the answer, not a particular count:
    # the exact set moves with the Python version, which is the point.
    assert set(PY.ident_slots(VARS)) < set(PY.ident_slots())


def test_the_rewrite_example() -> None:
    from astero.python import PY, Pass, rules

    desugar = Pass(
        "desugar",
        rules("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"),
        eliminates=(ast.AugAssign,),
        grammar=PY,
    )
    assert ast.unparse(desugar(ast.parse("b[1] += 5"))) == "b[1] = b[1] + 5"


def test_the_substitution_example() -> None:
    from astero.python import PY, VARS
    from astero.python.hygiene import Fresh, substitute

    body = ast.parse("[n + k for k in xs]", mode="eval").body
    out = substitute(
        body, {"n": ast.parse("k", mode="eval").body}, PY, VARS, fresh=Fresh()
    )
    assert ast.unparse(out) == "[k + _t1 for _t1 in xs]"


def test_the_emission_example() -> None:
    from astero.emit_rules import All, Both, Emitter, OpIs
    from astero.python import PY

    def type_of(node):
        return int if isinstance(node, ast.Constant) else None

    js = Emitter(PY, typer=type_of)
    js.projection("lit", str)
    js.projection("name", str)
    js.rule("BinOp", "{left} + {right}", All((OpIs((ast.Add,)), Both((int,)))))
    js.rule("BinOp", "add({left}, {right})", OpIs((ast.Add,)))
    js.rule("Constant", "{value:lit}")
    js.rule("Name", "{id:name}")

    assert js.to_text(ast.parse("1 + 2", mode="eval").body) == "1 + 2"
    assert js.to_text(ast.parse("a + b", mode="eval").body) == "add(a, b)"


# ---------------------------------------------------------------------------
# Two targets, one front end
# ---------------------------------------------------------------------------


def _has_cc() -> bool:
    import shutil

    return shutil.which("cc") is not None


@pytest.mark.skipif(not _has_cc(), reason="no C compiler")
@pytest.mark.parametrize("source", PROGRAMS)
@pytest.mark.parametrize("argument", [0, 1, 7, 25])
def test_both_targets_agree_with_cpython(source: str, argument: int) -> None:
    """The tutorial's claim: the front end does not move between targets.

    A compiler that agrees with itself proves nothing. CPython says what the
    program means, and both back ends have to agree with it.
    """
    from tinypy import compiler as tinypy, run_c, vm

    expected: dict = {}
    exec(compile(source, "<program>", "exec"), expected)
    want = expected["f"](argument)
    assert vm.run(tinypy.compile_source(source), argument) == want
    assert run_c.run(source, argument) == want


# ---------------------------------------------------------------------------
# The pages that claim their code runs
# ---------------------------------------------------------------------------

RUNNABLE = [
    ROOT / "docs/src/index.md",
    ROOT / "docs/src/getting-started.md",
    # Not a page that claims to run, but its entry-point block is a
    # hand-written mirror of the public API, so it is gated like one.
    ROOT / "docs/src/reference/modules.md",
]

#: A block that is deliberately not self-contained: a signature sketch, or a
#: call whose arguments are the reader's own code.
SKETCH = ("astero.python.build(module=my_ast)", "MY_GRAMMAR")


@pytest.mark.parametrize("page", RUNNABLE, ids=lambda p: p.name)
def test_the_page_runs_as_written(page: Path) -> None:
    """Both pages say their snippets run. This is that claim.

    Asserting the *outputs* below is not the same test and does not catch
    this: those assertions are re-typed copies, so a snippet on the page
    could reference an undefined name and stay green. Two did.
    """
    namespace: dict = {}
    for block in _python_blocks(page.read_text(encoding="utf-8")):
        if any(mark in block for mark in SKETCH) or "..." in block:
            continue
        exec(compile(block, str(page), "exec"), namespace)
