"""The SSA declaration, checked against itself.

`lang_ssa` is a read-only mirror of postpile's IR, transcribed by hand.
`test_lang_ssa.py` in `b_integration` checks it against postpile's own
source, which is the real oracle and needs a checkout; without one, nothing
looked at this module beyond importing it.

These are the questions that need no checkout: is the declaration
well-formed, does it say what it was written to say, and do the two
namespaces stay apart. A typo in a role changes an answer here.
"""

from __future__ import annotations

from postpile_ir.grammar import BLOCKS, SLOTS, SSA, VALS

from astero.grammar import Kind

#: postpile's instruction set as this module mirrors it. Written out so a
#: production appearing or vanishing is a visible edit rather than a silent
#: change of answer everywhere below.
PRODUCTIONS = frozenset({
    "Alloc",
    "ArrayDim",
    "ArrayLoad",
    "ArrayStore",
    "ArrayStride",
    "AssignValue",
    "BasicBlock",
    "BinOpInstr",
    "Branch",
    "Call",
    "Cast",
    "CondBranch",
    "Const",
    "Return",
    "Select",
    "UnaryOpInstr",
})


def test_the_declaration_is_well_formed() -> None:
    assert SSA.check() == []


def test_the_productions_are_the_ones_transcribed() -> None:
    assert set(SSA.productions) == PRODUCTIONS


def test_three_namespaces_stay_apart() -> None:
    """A value, a mutable slot and a block label are all named things.

    `AssignValue.target` is a slot and `AssignValue.value` a value, so a
    pass over values must not see the target. That separation is the reason
    the namespaces exist.
    """
    assert SSA.namespaces == frozenset({VALS, SLOTS, BLOCKS})
    assert "AssignValue" not in SSA.definitions(VALS)
    assert SSA.definitions(SLOTS) == {"AssignValue": ("target",)}
    assert SSA.operands(VALS)["AssignValue"] == ("value",)


def test_every_instruction_that_produces_a_value_defines_one() -> None:
    """Ten of them, each through a field called `result`."""
    defines = SSA.definitions(VALS)
    assert set(defines) == {
        "Alloc",
        "ArrayDim",
        "ArrayLoad",
        "ArrayStride",
        "BinOpInstr",
        "Call",
        "Cast",
        "Const",
        "Select",
        "UnaryOpInstr",
    }
    assert all(fields == ("result",) for fields in defines.values())


def test_the_instructions_that_only_read() -> None:
    """`ArrayStore` and the terminators produce nothing."""
    reads_only = set(SSA.operands(VALS)) - set(SSA.definitions(VALS))
    assert reads_only == {"ArrayStore", "AssignValue", "CondBranch", "Return"}


def test_a_control_flow_edge_is_a_label_use() -> None:
    """Branch targets are names in `blocks`, which is what makes the CFG
    derivable rather than a second table."""
    assert SSA.operands(BLOCKS) == {
        "Branch": ("target",),
        "CondBranch": ("true_target", "false_target"),
    }
    assert SSA.definitions(BLOCKS) == {"BasicBlock": ("label",)}


def test_positions_spans_both_roles_of_a_field() -> None:
    """The static query, which must report a field under every role it can
    carry. `reads`/`binds` are the instance questions and apply conditions."""
    both = SSA.positions((Kind.DEF, Kind.USE), VALS)
    assert both["BinOpInstr"] == ("result", "left", "right")
