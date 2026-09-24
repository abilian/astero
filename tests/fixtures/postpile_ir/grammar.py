"""postpile's typed SSA IR, declared.

Transcribed by hand from `postpile/src/postpile/compiler/ir.py`. astero does not
import postpile, and postpile does not know about astero: this is a read-only
mirror, present to answer one question. Does the notation that declares a tree
AST also declare a flat SSA IR, or does the core need a disjunction?

Three things this grammar has that the Python one does not:

- **A value operand is a reference by name**, not a child node. `BinOpInstr.left`
  names a definition made elsewhere in the same function. The claim under test
  is that this is `use(vals)` and nothing more, differing from a Python `Name`
  only in how the namespace resolves.
- **Three namespaces.** Values are SSA definitions, slots are mutable storage,
  blocks are branch targets. postpile's value numbering skips
  `AssignValue.target` with a comment saying it "names a mutable slot"; here
  that is `def(slots)`, and a pass over `vals` never reaches it.
- **Traits.** `pure` is what a common-subexpression pass keys on, replacing an
  enumeration written out per instruction.
"""

from __future__ import annotations

from astero.grammar import (
    ATTR,
    CHILD,
    Grammar,
    GrammarBuilder,
    Shape,
    defines,
    field_of,
    uses,
)

VALS = "vals"
SLOTS = "slots"
BLOCKS = "blocks"

#: Sorts that hold a name rather than a node.
VALUE = "value"
LABEL = "label"


def _attr(name: str, sort: str) -> object:
    return field_of(name, ATTR, Shape.ONE, sort)


def build() -> Grammar:
    b = GrammarBuilder(
        name="postpile-ssa",
        namespaces={VALS, SLOTS, BLOCKS},
        ident_sorts={VALUE, LABEL},
    )

    def instr(name: str, *fields, traits=()) -> None:
        b.production(name, *fields, sort="Instr", traits=traits)

    def term(name: str, *fields) -> None:
        b.production(name, *fields, sort="Term", traits=("terminator",))

    instr(
        "Const",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        _attr("value", "ConstValue"),
        traits=("pure",),
    )
    instr(
        "BinOpInstr",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        _attr("op", "BinOp"),
        field_of("left", uses(VALS), Shape.ONE, VALUE),
        field_of("right", uses(VALS), Shape.ONE, VALUE),
        traits=("pure",),
    )
    instr(
        "UnaryOpInstr",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        _attr("op", "UnaryOp"),
        field_of("operand", uses(VALS), Shape.ONE, VALUE),
        traits=("pure",),
    )
    instr(
        "Cast",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        field_of("operand", uses(VALS), Shape.ONE, VALUE),
        traits=("pure",),
    )
    instr(
        "Select",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        field_of("cond", uses(VALS), Shape.ONE, VALUE),
        field_of("if_true", uses(VALS), Shape.ONE, VALUE),
        field_of("if_false", uses(VALS), Shape.ONE, VALUE),
        traits=("pure",),
    )
    instr(
        "ArrayDim",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        field_of("array", uses(VALS), Shape.ONE, VALUE),
        _attr("axis", "int"),
        traits=("pure",),
    )
    instr(
        "ArrayStride",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        field_of("array", uses(VALS), Shape.ONE, VALUE),
        _attr("axis", "int"),
        traits=("pure",),
    )
    # A load is not pure: a store or call in between may have written the cell.
    instr(
        "ArrayLoad",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        field_of("array", uses(VALS), Shape.ONE, VALUE),
        field_of("index", uses(VALS), Shape.ONE, VALUE),
        traits=("load",),
    )
    instr(
        "ArrayStore",
        field_of("array", uses(VALS), Shape.ONE, VALUE),
        field_of("index", uses(VALS), Shape.ONE, VALUE),
        field_of("value", uses(VALS), Shape.ONE, VALUE),
        traits=("store",),
    )
    instr(
        "Call",
        field_of("result", defines(VALS), Shape.OPT, VALUE),
        _attr("func", "str"),
        field_of("args", uses(VALS), Shape.SEQ, VALUE),
        traits=("effects",),
    )
    # `target` names a mutable slot, so it is a different namespace from the
    # SSA values and value numbering never rewrites it.
    instr(
        "AssignValue",
        field_of("target", defines(SLOTS), Shape.ONE, VALUE),
        field_of("value", uses(VALS), Shape.ONE, VALUE),
        _attr("declare", "bool"),
        traits=("effects",),
    )
    instr(
        "Alloc",
        field_of("result", defines(VALS), Shape.ONE, VALUE),
        field_of("length", uses(VALS), Shape.ONE, VALUE),
        traits=("effects",),
    )

    term("Return", field_of("value", uses(VALS), Shape.OPT, VALUE))
    term("Branch", field_of("target", uses(BLOCKS), Shape.ONE, LABEL))
    term(
        "CondBranch",
        field_of("cond", uses(VALS), Shape.ONE, VALUE),
        field_of("true_target", uses(BLOCKS), Shape.ONE, LABEL),
        field_of("false_target", uses(BLOCKS), Shape.ONE, LABEL),
    )

    # Containment. `instructions` is a list and `terminator` closes the block:
    # the CFG lives in the terminators' `use(blocks)` fields, not in the nesting.
    b.production(
        "BasicBlock",
        field_of("label", defines(BLOCKS), Shape.ONE, LABEL),
        field_of("instructions", CHILD, Shape.SEQ, "Instr"),
        field_of("terminator", CHILD, Shape.OPT, "Term"),
        sort="Block",
        traits=("block",),
    )
    return b.build()


SSA = build()
