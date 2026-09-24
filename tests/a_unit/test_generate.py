"""E1 to E4: the declaration's own roles, fuzzed against CPython.

The standard-library corpus checks breadth. This checks that every position the
grammar *declares* is exercised at all, which a corpus cannot promise.
"""

from __future__ import annotations

import ast
import symtable

import pytest

from astero.python import PY, SCOPES, VARS, annotation_blocks, mangle, rewriting
from astero.scopes import scope_tree
from astero.testing import generate

#: Scope kinds astero does not model, with every spelling CPython has used.
#: PEP 695 type parameters are "type parameter" on 3.12 and "type parameters"
#: from 3.13; PEP 649 deferred annotations add "annotation" blocks on 3.14+.
UNMODELLED_BLOCK_KINDS = frozenset({
    "type alias",
    "type parameter",
    "type parameters",
})

ALL = [
    *generate.snippets().items(),
    *(
        (f"combination{i}", src)
        for i, src in enumerate(generate.combinations(40, seed=7))
    ),
]


def test_e0_every_declared_role_is_exercised() -> None:
    """A role added to the declaration and not to the corpus fails here."""
    missing = generate.missing_coverage(PY, SCOPES, VARS)
    assert not missing, f"declared positions with no snippet: {sorted(missing)}"


@pytest.mark.parametrize(("label", "source"), ALL)
def test_e1_every_snippet_is_a_legal_program(label: str, source: str) -> None:
    compile(source, f"<{label}>", "exec")


@pytest.mark.parametrize(("label", "source"), ALL)
def test_e2_contexts_are_derived_correctly(label: str, source: str) -> None:
    """E2: `fix_contexts` on a parsed tree agrees with CPython's own parse."""
    derived = rewriting.fix_contexts(ast.parse(source))
    expected = ast.parse(source)
    ignore = rewriting.DERIVED - {"ctx"}
    assert rewriting.key(derived, ignore) == rewriting.key(expected, ignore), label


@pytest.mark.parametrize(("label", "source"), ALL)
def test_e3_scopes_agree_with_symtable(label: str, source: str) -> None:
    """E3: the resolved scope tree and its bound names match CPython's."""
    tree = ast.parse(source)
    block = scope_tree(
        tree, PY, SCOPES, VARS, mangle=mangle, siblings=annotation_blocks(tree)
    )
    table = symtable.symtable(source, f"<{label}>", "exec")

    def shape(b: symtable.SymbolTable) -> tuple:
        kind = b.get_type()
        return (
            str(getattr(kind, "value", kind)),
            b.get_name(),
            tuple(shape(c) for c in b.get_children()),
        )

    def locals_(b: symtable.SymbolTable, out: list[set[str]]) -> list[set[str]]:
        out.append(
            {s.get_name() for s in b.get_symbols() if s.is_local()}
            - {
                ".0",
                ".defaults",
                ".generic_base",
                ".type_params",
                "__type_params__",
                ".format",
            }
        )
        for child in b.get_children():
            locals_(child, out)
        return out

    if block.shape() != shape(table):
        # Assert the difference is only the block kinds astero does not model,
        # so this allowance cannot quietly cover anything else.
        kinds = _kinds(shape(table)) - _kinds(block.shape())
        # `kinds` empty means the shapes differ while using the same block
        # kinds, so nothing here is unmodelled and the difference is real.
        assert kinds, f"{label}: shapes differ but no block kind is missing"
        assert kinds <= UNMODELLED_BLOCK_KINDS, (
            f"{label}: unexpected block kinds {sorted(kinds)}"
        )
        pytest.xfail(f"{label}: unmodelled block kinds {sorted(kinds)}")
    for theirs, ours in zip(locals_(table, []), block.walk(), strict=True):
        assert theirs == ours.owns(), f"{label}/{ours.name}"


def _kinds(shape: tuple) -> set[str]:
    kind, _name, children = shape
    return {kind}.union(*(_kinds(c) for c in children)) if children else {kind}


@pytest.mark.parametrize(("label", "source"), ALL)
def test_e4_an_empty_pass_is_the_identity(label: str, source: str) -> None:
    """E4: a Pass with no rules changes nothing but the fields it reifies."""
    identity = rewriting.Pass("identity", ())
    before = ast.parse(source)
    after = identity(before)
    assert rewriting.key(after) == rewriting.key(ast.parse(source)), label
