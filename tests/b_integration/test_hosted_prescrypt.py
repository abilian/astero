"""G1 against prescrypt-ng's real generated AST.

The synthetic host in `tests/a_unit/test_hosted.py` pins the contract. This
checks it against the compiler it was built for, which is the only thing that
can falsify the claim that a host authors nothing.

prescrypt-ng is imported here rather than read, because the point is its actual
node classes. It is not a dependency: a missing checkout, or one whose own
dependencies are not installed, skips.
"""

from __future__ import annotations

import ast
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from astero.grammar import Grammar
from astero.python import (
    DEPRECATED_ALIASES,
    PY,
    SCOPES,
    VARS,
    Pass,
    build,
    mangle,
    rules,
)
from astero.scopes import scope_tree

_CANDIDATES = [
    Path(os.environ["PRESCRYPT_SRC"]) if os.environ.get("PRESCRYPT_SRC") else None,
    Path(__file__).resolve().parents[2] / "sandbox" / "prescrypt-ng",
    Path(__file__).resolve().parents[3] / "prescrypt-ng",
    Path.home() / "projects" / "compilers" / "prescrypt-ng",
]

#: The rule that carried the bug this project opened with. Nothing in it names
#: a context, so `b[1] += 5` and `x += 5` cannot diverge.
DESUGAR_AUG = "ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"


def _prescrypt_ast() -> ModuleType:
    for root in _CANDIDATES:
        if root and (root / "src/prescrypt/front/ast/ast.py").exists():
            src = str(root / "src")
            if src not in sys.path:
                sys.path.insert(0, src)
            try:
                # Imported by name, because it resolves from a checkout on
                # disk rather than from anything astero depends on.
                return importlib.import_module("prescrypt.front.ast.ast")
            except ImportError as error:
                pytest.skip(f"prescrypt-ng found but not importable: {error}")
    pytest.skip("no prescrypt-ng checkout found; set PRESCRYPT_SRC")
    raise AssertionError  # unreachable, satisfies the type checker


@pytest.fixture(scope="module")
def pre() -> ModuleType:
    return _prescrypt_ast()


@pytest.fixture(scope="module")
def prescrypt(pre: ModuleType) -> Grammar:
    return build(module=pre, name="prescrypt")


def test_h1_the_host_is_declared_without_authoring_anything(
    prescrypt: Grammar, pre: ModuleType
) -> None:
    """prescrypt's grammar is `lang_py`'s roles over prescrypt's classes.

    Every production it has, it has with CPython's fields under CPython's
    names, because it generates them from CPython's. So the 36 authored facts
    are reused whole and the second host adds none.
    """
    cpython = {p.name for p in PY}
    theirs = {p.name for p in prescrypt}
    # prescrypt generated its classes from an `ast` that still exposed the
    # 3.8/3.9 compatibility shims, so it has a few `astero.python.PY` drops: `slice`
    # stopped being a sort in 3.9 and is an alias for `expr` now. Derived the
    # same way `lang_py` drops them, so this cannot become a list to maintain.
    shims = DEPRECATED_ALIASES
    assert theirs <= cpython | shims, sorted(theirs - cpython - shims)
    assert len(theirs) > 100

    for name in theirs & cpython:
        assert prescrypt[name].cls is getattr(pre, name)
        mine = [(f.name, str(f.role)) for f in prescrypt[name].fields]
        assert mine == [(f.name, str(f.role)) for f in PY[name].fields]


def test_h2_a_rewrite_builds_prescrypts_classes(
    prescrypt: Grammar, pre: ModuleType
) -> None:
    """The single narrowest blocker: matching already worked, building did not."""
    desugar = Pass(
        "desugar",
        rules(DESUGAR_AUG),
        eliminates=(ast.AugAssign,),
        grammar=prescrypt,
    )
    out = desugar(pre.parse("b[1] += 5"))

    # Every node, not only the constructed spine: the input was prescrypt's, so
    # a CPython class anywhere in the result is a leak.
    modules = {type(n).__module__ for n in ast.walk(out)}
    assert modules == {pre.__name__}

    # And the mixin prescrypt's later passes read is present on what was built.
    assert hasattr(out.body[0], "_scope")


def test_h3_the_augmented_assignment_bug_cannot_be_written(
    prescrypt: Grammar, pre: ModuleType
) -> None:
    """`b[1] += 5` read its target in Store context, and emitted a raw index.

    The hand-written pass guarded its context fixup with `isinstance(_, Name)`,
    so a subscript target kept Store on the read side. Here the context is not
    written at all, so the plain and the subscripted form cannot disagree.
    """
    desugar = Pass("desugar", rules(DESUGAR_AUG), grammar=prescrypt)

    for source, expected in [("x += 5", "x = x + 5"), ("b[1] += 5", "b[1] = b[1] + 5")]:
        built = desugar(pre.parse(source)).body[0]
        assert ast.unparse(built) == expected
        assert isinstance(built.value.left.ctx, pre.Load)
        assert isinstance(built.targets[0].ctx, pre.Store)


def test_h4_scopes_run_on_prescrypts_trees(prescrypt: Grammar, pre: ModuleType) -> None:
    """The other half of the front end, on the host's own nodes."""
    tree = pre.parse("class C:\n    def m(self, a):\n        b = a\n        return b\n")
    top = scope_tree(
        tree,
        prescrypt,
        SCOPES,
        VARS,
        mangle=mangle,
    )

    assert top.kind == "module"
    assert top.owns() == {"C"}
    klass = top.children[0]
    assert (klass.kind, klass.name, klass.owns()) == ("class", "C", {"m"})
    method = klass.children[0]
    assert (method.kind, method.name) == ("function", "m")
    assert method.owns() == {"self", "a", "b"}


def test_h5_a_production_prescrypt_lacks_fails_at_the_rewrite(
    prescrypt: Grammar,
) -> None:
    """prescrypt has no PEP 695, so building one is an error and not a surprise."""
    assert "TypeAlias" not in prescrypt
    with pytest.raises(KeyError, match="no production 'TypeAlias'"):
        prescrypt.constructor("TypeAlias")
