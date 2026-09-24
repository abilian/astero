"""A use spelled as an object, not as a bare identifier.

A language names a use one of three ways. Python puts a `Name` node in
expression position. PL/0 puts a bare string in a field. postpile's SSA puts a
`Value(name, dtype)` object there, and the identifier is one level down.

astero handled the first two. For the third, `ident_slots` reported nothing —
the field's sort is `Value`, not `ident` — so `all_names` answered emptily and
`rename` was a silent no-op over a whole IR. Not a crash: the wrong answer,
which is the failure this library exists to remove.

`reference_sorts` is what a grammar declares to close it: the sort, and the
field of that sort holding the name. One entry, and the queries reach it.
postpile's `backends/qbe/passes.py::_rename_instr` is twenty hand-written lines
doing this walk over `dataclasses.fields`, which is what it replaces.
"""

from __future__ import annotations

import dataclasses

import pytest

from astero.grammar import defines, from_dataclasses, uses
from astero.python.hygiene import all_names, rename

VALS = "vals"

ROLES = {"Add": {"result": defines(VALS), "left": uses(VALS), "right": uses(VALS)}}


@dataclasses.dataclass
class Val:
    """A reference: the name lives here, not in the field that holds it."""

    name: str
    width: int = 64


@dataclasses.dataclass
class Add:
    result: Val
    left: Val
    right: Val


def _grammar(*, references: bool):
    """The same IR, declared with and without its reference sort."""
    return from_dataclasses(
        "tiny",
        [Add],
        roles=ROLES,
        namespaces={VALS},
        reference_sorts={"Val": "name"} if references else None,
    )


def _tree() -> Add:
    return Add(Val("t1"), Val("a"), Val("b"))


def test_without_the_declaration_the_names_are_invisible() -> None:
    """The state before this feature, pinned so the gap stays legible."""
    grammar = _grammar(references=False)
    assert grammar.reference_slots(VALS) == {}
    assert all_names(_tree(), grammar) == set()

    tree = _tree()
    rename(tree, {"a": "z"}, grammar, VALS)
    assert tree.left.name == "a", "a silent no-op, which is the bug"


def test_one_declared_sort_makes_every_query_reach_them() -> None:
    grammar = _grammar(references=True)
    assert grammar.reference_slots(VALS) == {
        "Add": (("result", "name"), ("left", "name"), ("right", "name"))
    }
    assert all_names(_tree(), grammar) == {"t1", "a", "b"}


def test_rename_rewrites_the_object_not_the_field() -> None:
    grammar = _grammar(references=True)
    tree = _tree()
    rename(tree, {"a": "z"}, grammar, VALS)
    assert tree.left.name == "z"
    assert tree.right.name == "b"
    assert tree.result.name == "t1"
    assert isinstance(tree.left, Val), "the reference object survives the rename"


def test_a_namespace_still_separates_them() -> None:
    """`reference_slots(ns)` filters by role the way `ident_slots` does."""
    grammar = _grammar(references=True)
    assert grammar.reference_slots("labels") == {}
    assert grammar.reference_slots() == {
        "Add": (("result", "name"), ("left", "name"), ("right", "name"))
    }


def test_a_grammar_declaring_none_pays_nothing() -> None:
    """The default is empty, so no existing grammar changes behaviour."""
    from astero.python import PY

    assert PY.reference_sorts == {}
    assert PY.reference_slots() == {}


# ------------------------------------------------------------------- copying


def test_copy_tree_without_a_grammar_refuses_a_foreign_node() -> None:
    """The forgotten second argument, made loud.

    `copy_tree` reads `node._fields`, which only a Python AST has, so it
    cannot copy a node of any other kind. It used to fall through and return
    the input — not a copy, and not a refusal — and a caller who then mutated
    the "copy" had mutated the original. The `grammar` parameter exists to
    serve exactly the callers who would hit that, so omitting it is the
    mistake worth naming rather than absorbing.
    """
    from astero.python.rewriting import copy_tree

    with pytest.raises(TypeError, match=r"Add.*Pass `grammar=`"):
        copy_tree(_tree())


def test_a_value_a_python_field_can_hold_still_passes_through() -> None:
    """The refusal is for nodes, not for the leaves every copy bottoms out in."""
    from astero.python.rewriting import copy_tree

    for leaf in ("x", b"x", 1, True, 1.0, 1j, None, ...):
        assert copy_tree(leaf) is leaf


def test_copy_tree_with_a_grammar_copies_a_tree_of_any_kind() -> None:
    from astero.python.rewriting import copy_tree

    grammar = _grammar(references=True)
    tree = _tree()
    clone = copy_tree(tree, grammar)
    assert clone is not tree
    assert clone.left.name == "a"


def test_a_reference_object_is_copied_rather_than_shared() -> None:
    """Sharing one would make `rename` on the clone rewrite the original too.

    This is what postpile's `_rename_instr` keeps a per-clone cache to avoid,
    and it is why a reference sort is copied where an undeclared leaf is not.
    """
    from astero.python.rewriting import copy_tree

    grammar = _grammar(references=True)
    tree = _tree()
    clone = copy_tree(tree, grammar)
    assert clone.left is not tree.left
    assert isinstance(clone.left, Val)


def test_clone_then_rename_leaves_the_original_alone() -> None:
    """The whole operation a loop-unroller needs, from two declared queries."""
    from astero.python.rewriting import copy_tree

    grammar = _grammar(references=True)
    tree = _tree()
    clone = rename(copy_tree(tree, grammar), {"a": "ur0.a"}, grammar, VALS)

    assert clone.left.name == "ur0.a"
    assert tree.left.name == "a"
