"""A grammar built for a host that has its own node classes.

prescrypt-ng generates an AST whose classes subclass CPython's and carry a
mixin its later passes read. Matching already worked there, because every
dispatch in the engine is an `isinstance`. Construction did not: a rule built
`ast.Assign` where the host needs its own.

The host here is synthetic, so these tests pin the contract without depending
on a checkout. `tests/b_integration/test_hosted_prescrypt.py` runs the same
claims against the real one.
"""

from __future__ import annotations

import ast
import sys
from types import ModuleType

import pytest

from astero.python import PY, Pass, build, rules
from astero.python.rewriting import fix_contexts

#: The productions a host that only desugars needs. Deliberately not all of
#: Python: a host missing a production is the case worth pinning.
HOSTED = (
    "AST",
    "mod",
    "stmt",
    "expr",
    "expr_context",
    "operator",
    "Module",
    "Assign",
    "AugAssign",
    "Expr",
    "BinOp",
    "Add",
    "Name",
    "Constant",
    "Subscript",
    "Load",
    "Store",
    "Del",
    "Delete",
)


def _host() -> ModuleType:
    """A module of node classes subclassing CPython's, as a host generates.

    The shape is prescrypt-ng's: each class inherits from its CPython
    counterpart and from the host's version of that counterpart's base, so
    `isinstance(node, ast.Assign)` holds while `type(node) is ast.Assign` does
    not. That is exactly what makes matching work and construction fail.
    """
    module = ModuleType("fake_host")
    for name in HOSTED:
        base = getattr(ast, name)
        bases = (
            base,
            *(
                getattr(module, b.__name__)
                for b in base.__bases__
                if b.__name__ in HOSTED
            ),
        )
        setattr(module, name, type(name, bases, {"_host": True}))
    return module


@pytest.fixture(scope="module")
def host() -> ModuleType:
    return _host()


def test_the_roles_are_reused_verbatim_for_a_second_host(host: ModuleType) -> None:
    """A host authors nothing. Only which productions exist differs."""
    hosted = build(module=host, name="fake")
    assert hosted.name == "fake"
    assert set(hosted.productions) == set(HOSTED)
    # The role that makes `ctx` derivable is the same fact about the same
    # language, so it carries over without being restated.
    mine = hosted["Assign"].field("targets")
    theirs = PY["Assign"].field("targets")
    assert mine is not None
    assert theirs is not None
    assert mine.role == theirs.role


def test_a_grammar_carries_each_productions_constructor(host: ModuleType) -> None:
    hosted = build(module=host, name="fake")
    assert hosted.constructor("Assign") is host.Assign
    assert hosted.constructor("Assign") is not ast.Assign


def test_a_rewrite_builds_the_hosts_classes(host: ModuleType) -> None:
    hosted = build(module=host, name="fake")
    desugar = Pass(
        "desugar",
        rules("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"),
        eliminates=(ast.AugAssign,),
        grammar=hosted,
    )
    out = desugar(ast.parse("b[1] += 5"))
    built = out.body[0]

    # What the rule constructs is the host's. That is `Assign` and `BinOp`
    # here: the rest of the result is metavariables.
    assert isinstance(built, host.Assign)
    assert isinstance(built.value, host.BinOp)

    # What a metavariable carries over keeps the class it was matched with, so
    # `_t` and `_o` stay CPython's because CPython parsed the input. A host
    # parsing its own source never sees the mixture, which the prescrypt-ng
    # integration test checks.
    assert type(built.targets[0]) is ast.Subscript
    assert type(built.value.op) is ast.Add


def test_the_derived_contexts_are_the_hosts_too(host: ModuleType) -> None:
    hosted = build(module=host, name="fake")
    tree = ast.parse("b[1] += 5")
    desugar = Pass(
        "desugar",
        rules("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"),
        grammar=hosted,
    )
    built = desugar(tree).body[0]
    # The bug this project opened with: the read side must be Load, and it is
    # derived from the position rather than copied from the target.
    assert isinstance(built.value.left.ctx, host.Load)
    assert isinstance(built.targets[0].ctx, host.Store)


def test_a_production_the_host_lacks_is_an_error_not_a_fallback(
    host: ModuleType,
) -> None:
    """Silently building CPython's class would defer the failure downstream."""
    hosted = build(module=host, name="fake")
    with pytest.raises(KeyError, match="no production 'Lambda'"):
        hosted.constructor("Lambda")

    bad = Pass(
        "bad",
        rules("ast.Assign(_t, _v) => ast.AnnAssign(_t, ast.Name('int'), _v, 1)"),
        grammar=hosted,
    )
    with pytest.raises(KeyError, match="no production 'AnnAssign'"):
        bad(ast.parse("x = 1"))


def test_a_grammar_without_classes_refuses_to_construct() -> None:
    from postpile_ir.grammar import SSA

    with pytest.raises(KeyError, match="declares no class"):
        SSA.constructor(next(iter(SSA.productions)))


def test_the_default_grammar_is_still_cpythons() -> None:
    """Passing no grammar keeps building `ast` classes, as before."""
    desugar = Pass(
        "desugar",
        rules("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"),
    )
    out = desugar(ast.parse("b[1] += 5"))
    assert type(out.body[0]) is ast.Assign
    assert isinstance(fix_contexts(out), ast.Module)


@pytest.mark.skipif(
    sys.version_info < (3, 13), reason="_field_types supplies shapes from 3.13"
)
def test_shapes_survive_the_second_host(host: ModuleType) -> None:
    from astero.grammar import Shape

    hosted = build(module=host, name="fake")
    targets = hosted["Assign"].field("targets")
    assert targets is not None
    assert targets.shape is Shape.SEQ


def test_concrete_drops_the_productions_with_no_instances(host: ModuleType) -> None:
    """A dispatch table owes handlers for what can appear, not for `stmt`."""
    hosted = build(module=host, name="fake")
    concrete = hosted.concrete()
    assert "Assign" in concrete
    for abstract in ("AST", "mod", "stmt", "expr", "expr_context", "operator"):
        assert abstract not in concrete, abstract


def test_concrete_can_be_restricted_to_one_base(host: ModuleType) -> None:
    hosted = build(module=host, name="fake")
    statements = hosted.concrete("stmt")
    assert {"Assign", "AugAssign", "Expr", "Delete"} <= statements
    assert "BinOp" not in statements
    assert "Load" not in statements


def test_concrete_needs_a_grammar_that_carries_classes() -> None:
    from postpile_ir.grammar import SSA

    with pytest.raises(ValueError, match="declares no classes"):
        SSA.concrete()


def test_concrete_rejects_an_unknown_base(host: ModuleType) -> None:
    hosted = build(module=host, name="fake")
    with pytest.raises(KeyError, match="no production 'Nope'"):
        hosted.concrete("Nope")


def test_python_has_no_abstract_production_in_concrete() -> None:
    """Checked against `ast` itself, so a new abstract base cannot slip in."""
    concrete = PY.concrete()
    # The floor only guards against a vacuous pass: every assertion here is
    # inside the loop, so an empty `concrete()` would check nothing. Python
    # has had at least a hundred productions since 3.8.
    assert len(concrete) > 100, f"only {len(concrete)} productions"
    for name in concrete:
        cls = PY[name].cls
        assert cls is not None
        # Compare identity, not names. `__subclasses__` is global, and the
        # synthetic host above puts a class called `Assign` under `ast.Assign`.
        assert not [
            sub
            for sub in cls.__subclasses__()
            if PY.productions.get(sub.__name__) is not None
            and PY[sub.__name__].cls is sub
        ], name
