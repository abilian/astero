"""PL/0 to P-code, as a table of templates.

The P-machine is Wirth's: a stack, a frame per active procedure, and
level-difference addressing so a nested procedure can reach an enclosing
one's variables. Emission is post-order, so `levels=None` and the operator
goes last in each template, exactly as for any stack target.

One rule per production, and control flow is a rule like the others because
`{&label}` names a label unique to its node.

Where this stops, and why it is worth seeing: `Name` cannot be two rules
under a guard, one for a constant and one for a variable. Which of the two a
name is depends on what the *scopes* say, and the guard vocabulary asks only
about a node's type and shape. So the resolution happens in a projection,
which is host code by design, and the template stays a template.
"""

from __future__ import annotations

from astero.coverage import Coverage
from astero.emit_rules import Emitter

from . import syntax
from .analyze import Frame, frames
from .grammar import PL0

#: Arithmetic and comparison, as the machine spells them.
OPS = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
RELS = {"=": "eq", "#": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}


def emitter(frame: Frame) -> Emitter:
    """The rules for code running inside `frame`."""
    p = Emitter(PL0, levels=None)

    def load(name: str) -> str:
        kind, *rest = frame.lookup(name)
        if kind == "const":
            return f"LIT {rest[0]}"
        return f"LOD {rest[0]} {rest[1]}"

    def store(name: str) -> str:
        kind, *rest = frame.lookup(name)
        if kind == "const":
            raise ValueError(f"cannot assign to the constant {name!r}")
        return f"STO {rest[0]} {rest[1]}"

    p.projection("lit", str)
    p.projection("load", load)
    p.projection("store", store)
    p.projection("proc", frame.procedure)
    p.projection("op", lambda op: f"OPR {OPS[op]}")
    p.projection("rel", lambda op: f"OPR {RELS[op]}")

    p.rule("Number", "LIT {value:lit}")
    p.rule("Name", "{name:load}")
    p.rule("Neg", "{value}\nOPR neg")
    p.rule("BinOp", "{left}\n{right}\n{op:op}")
    p.rule("Odd", "{value}\nOPR odd")
    p.rule("Compare", "{left}\n{right}\n{op:rel}")

    p.rule("Assign", "{value}\n{name:store}")
    p.rule("Call", "CAL {name:proc}")
    p.rule("Write", "{value}\nWRT")
    p.rule("Empty", "")
    p.rule("Begin", "{body:\n}")
    p.rule("If", "{cond}\nJPC {&done}\n{then}\n{&done}:")
    p.rule("While", "{&top}:\n{cond}\nJPC {&done}\n{body}\nJMP {&top}\n{&done}:")
    return p


def coverage() -> Coverage:
    """Every statement and expression PL/0 has must have a rule.

    `concrete` reads the class hierarchy in `syntax.py`, so adding a
    production there and forgetting its rule fails here by name.
    """
    handled = emitter(Frame(name="probe", level=0)).covered()
    expected = PL0.concrete("Stmt") | PL0.concrete("Expr") | PL0.concrete("Cond")
    return Coverage(handled=handled, expected=expected)


def compile_program(program: syntax.Program) -> list[str]:
    """The whole program as P-code lines, procedures first."""
    table = frames(program)
    code: list[str] = ["JMP main"]

    def emit_block(block: syntax.Block, label: str) -> None:
        frame = table[id(block)]
        for proc in block.procedures:
            emit_block(proc.block, frame.procedures[proc.name])
        code.append(f"{label}:")
        code.append(f"INT {frame.size}")
        code.extend(emitter(frame).to_lines(block.body))
        code.append("RET")

    for proc in program.block.procedures:
        emit_block(proc.block, table[id(program.block)].procedures[proc.name])
    main = table[id(program.block)]
    code.extend(("main:", f"INT {main.size}"))
    code.extend(emitter(main).to_lines(program.block.body))
    code.append("HALT")
    return [line for line in code if line]
