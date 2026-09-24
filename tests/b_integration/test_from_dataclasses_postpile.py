"""The dataclass front door against postpile's real IR.

The claim: postpile declares its SSA grammar from its own dataclasses, with
only the roles authored, and the derived answers are the ones its hand-written
pass gave. postpile now *ships* that declaration in `compiler/grammar.py`, and
this reads it rather than restating it, so a role changing there is seen here.

**The oracle is frozen, deliberately.** `verify.uses` and `verify.defines` were
a `match` per instruction until 2026-08-13 and are now three lines over the
grammar, so comparing against the live functions would compare the derivation
with itself. :data:`REPLACED` is the pass as it stood at 71e1b22, copied here
and nowhere else, and it is what the derivation is held to. It is authored data
gated against what it mirrors, which is the same shape as `CTX_NODES`.

A field added to `ir.py` makes this disagree, which is correct: the frozen
answer cannot know whether a new slot reads or defines, and someone has to say.
postpile's own `test_ir_grammar.py` asks that question from the other side.

postpile is imported rather than read, because the point is its actual classes.
It is not a dependency: a missing checkout, or one whose own dependencies are
not installed, skips. It skips in astero's own environment, which lacks
postpile's `postyp`, so run it where postpile lives:

    cd sandbox/postpile
    PYTHONPATH=../../src uv run --with pytest python -m pytest \
        ../../tests/b_integration/test_from_dataclasses_postpile.py

All four pass there, checked 2026-08-13.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from astero.grammar import Grammar

VALS = "vals"

_CANDIDATES = [
    Path(os.environ["POSTPILE_SRC"]) if os.environ.get("POSTPILE_SRC") else None,
    Path(__file__).resolve().parents[2] / "sandbox" / "postpile",
    Path(__file__).resolve().parents[3] / "postpile",
    Path.home() / "projects" / "compilers" / "postpile",
]

#: `verify.py` at 71e1b22, as field names rather than as a `match`. Every row is
#: a hand copy of a dataclass's field list, which is what the roles removed.
#: `(uses, defines)`, where `defines` is one field name or None.
REPLACED: dict[str, tuple[tuple[str, ...], str | None]] = {
    "Const": ((), "result"),
    "BinOpInstr": (("left", "right"), "result"),
    "UnaryOpInstr": (("operand",), "result"),
    "ArrayLoad": (("array", "index"), "result"),
    "ArrayStore": (("array", "index", "value"), None),
    "ArrayDim": (("array",), "result"),
    "ArrayStride": (("array",), "result"),
    "Call": (("args",), "result"),
    "Cast": (("operand",), "result"),
    "Select": (("cond", "if_true", "if_false"), "result"),
    "Alloc": (("length",), "result"),
    # The `match` spelled this one as a conditional expression inside its arm:
    #     return (value,) if declare else (target, value)
    "AssignValue+declare": (("value",), "target"),
    "AssignValue": (("target", "value"), None),
}


def _postpile() -> ModuleType:
    for root in _CANDIDATES:
        if root and (root / "src/postpile/compiler/ir.py").exists():
            src = str(root / "src")
            if src not in sys.path:
                sys.path.insert(0, src)
            try:
                return importlib.import_module("postpile.compiler.ir")
            except ImportError as error:
                pytest.skip(f"postpile found but not importable: {error}")
    pytest.skip("no postpile checkout found; set POSTPILE_SRC")
    raise AssertionError  # unreachable, satisfies the type checker


@pytest.fixture(scope="module")
def ir() -> ModuleType:
    return _postpile()


@pytest.fixture(scope="module")
def declaration(ir: ModuleType) -> ModuleType:
    """postpile's own declaration, not a copy of it."""
    return importlib.import_module("postpile.compiler.grammar")


@pytest.fixture(scope="module")
def ssa(declaration: ModuleType) -> Grammar:
    return declaration.SSA


def _names(value, value_cls) -> set[str]:
    if isinstance(value, list):
        return {x.name for x in value if isinstance(x, value_cls)}
    return {value.name} if isinstance(value, value_cls) else set()


def _sample(cls, ir: ModuleType, **overrides):
    """One instance of `cls`, with a distinct value in every Value-typed slot."""
    from postyp import Int64

    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        text = str(f.type)
        if "list[" in text:
            kwargs[f.name] = [ir.Value(name=f.name + "1", dtype=Int64)]
        elif "Value" in text and "ConstValue" not in text:
            kwargs[f.name] = ir.Value(name=f.name, dtype=Int64)
        elif text.startswith("bool"):
            kwargs[f.name] = False
        elif "BinOp" in text:
            kwargs[f.name] = next(iter(ir.BinOp))
        elif "UnaryOp" in text:
            kwargs[f.name] = next(iter(ir.UnaryOp))
        elif "ConstValue" in text:
            kwargs[f.name] = 1
        elif "str" in text:
            kwargs[f.name] = "f"
        elif "DType" in text:
            kwargs[f.name] = Int64
        else:
            kwargs[f.name] = None
    return cls(**{**kwargs, **overrides})


def _authored_roles(declaration: ModuleType) -> dict:
    """Every role table the declaration carries, as one mapping.

    postpile splits them: `ROLES` for instructions and `TERMINATOR_ROLES`
    for `Branch`, `CondBranch` and `Return`, which read a label as well as a
    value. Reading only `ROLES` made the three terminators look like
    productions nobody had given a role, which is the opposite of true.

    Naming both is deliberate. A third table added there should fail here
    until someone looks, because "which productions carry roles" is the
    thing this file exists to check.
    """
    return {**declaration.ROLES, **declaration.TERMINATOR_ROLES}


def test_h1_the_grammar_is_declared_from_postpiles_own_classes(
    ssa, declaration, ir
) -> None:
    roles = _authored_roles(declaration)
    assert ssa.check() == []
    assert len(ssa.productions) == len(roles)
    for name in roles:
        assert ssa[name].cls is getattr(ir, name)


def test_h2_the_derived_answers_are_the_ones_the_match_gave(ssa, ir) -> None:
    """The claim that matters, held to the frozen pass rather than the live one."""
    checked = 0
    for key, (want_uses, want_defines) in REPLACED.items():
        name, _, flag = key.partition("+")
        node = _sample(getattr(ir, name), ir, **({flag: True} if flag else {}))

        expect_uses: set[str] = set()
        for f in want_uses:
            expect_uses |= _names(getattr(node, f), ir.Value)
        expect_defs = (
            set()
            if want_defines is None
            else _names(getattr(node, want_defines), ir.Value)
        )

        assert {v.name for v in ssa.reads(node, VALS)} == expect_uses, f"{key} uses"
        assert {v.name for v in ssa.binds(node, VALS)} == expect_defs, f"{key} defines"
        checked += 1
    assert checked == 13


def test_h3_the_conditional_role_is_what_the_match_spelled_by_hand(ssa, ir) -> None:
    """`AssignValue` reads its target only when it is not declaring it."""
    from postyp import Int64

    target = ir.Value(name="target", dtype=Int64)
    value = ir.Value(name="value", dtype=Int64)
    for declare, want_uses, want_defs in [
        (True, {"value"}, {"target"}),
        (False, {"target", "value"}, set()),
    ]:
        node = ir.AssignValue(target=target, value=value, declare=declare)
        assert {v.name for v in ssa.reads(node, VALS)} == want_uses
        assert {v.name for v in ssa.binds(node, VALS)} == want_defs


def test_h4_the_switch_over_landed(ir) -> None:
    """`verify.py`'s two functions are the grammar's, not a `match` of their own.

    Without this the frozen oracle above could go on passing beside a pass that
    was never replaced, which is the claim this file exists to make.
    """
    verify = importlib.import_module("postpile.compiler.verify")
    for fn in (verify.uses, verify.defines):
        source = inspect.getsource(fn)
        assert "match instr" not in source
        assert "SSA." in source
