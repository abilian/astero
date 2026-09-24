"""TinyPy to C: the same front end, a structured target.

The stack machine in `compiler.py` is flat — post-order, labels and jumps,
no brackets. C is the opposite on every axis, which is the point of having
both: infix with precedence, braces rather than labels, and statements that
nest. The grammar, the desugaring and the name binding do not move.

Two things this exercises that a flat target cannot:

* **`levels`.** A precedence table, so brackets are derived. No rule mentions
  a parenthesis, and `(n * 3 + 7) // 2` comes out with exactly the brackets it
  needs and no others.
* **Braces as literals.** `{{` and `}}` in a template are one brace each, as
  in `str.format`, so a block is written the way it reads.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from astero.emit import Assoc, Level
from astero.emit_rules import Emitter

if TYPE_CHECKING:
    from astero.grammar import Grammar

#: C's binding powers. The one table brackets come from.
C_LEVELS = {
    ast.Lt: Level(6, Assoc.NONE),
    ast.Gt: Level(6, Assoc.NONE),
    ast.LtE: Level(6, Assoc.NONE),
    ast.GtE: Level(6, Assoc.NONE),
    ast.Eq: Level(5, Assoc.NONE),
    ast.NotEq: Level(5, Assoc.NONE),
    ast.Add: Level(11),
    ast.Sub: Level(11),
    ast.Mult: Level(12),
    ast.FloorDiv: Level(12),
    ast.Mod: Level(12),
}

SYMBOLS = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.FloorDiv: "/",
    ast.Mod: "%",
    ast.Lt: "<",
    ast.Gt: ">",
    ast.LtE: "<=",
    ast.GtE: ">=",
    ast.Eq: "==",
    ast.NotEq: "!=",
}


def emitter(grammar: Grammar) -> Emitter:
    c = Emitter(grammar, levels=C_LEVELS)
    c.projection("name", str)
    c.projection("lit", str)
    c.projection("sym", lambda op: SYMBOLS[type(op)])
    c.projection("target", lambda t: t.id)

    c.rule("Name", "{id:name}")
    c.rule("Constant", "{value:lit}")
    c.rule("BinOp", "{left} {op:sym} {right}")
    c.rule("Compare", "{left} {ops:sym} {comparators}")

    c.rule("Assign", "{targets:target} = {value};")
    c.rule("Return", "return {value};")
    c.rule("Pass", ";")
    c.rule("Expr", "{value};")
    # TinyPy admits exactly one call, `print`, as the stack target's rules say.
    # The cast binds tighter than anything it can hold and C's table does not
    # state that, so the template writes the brackets: a hole its own template
    # delimits is emitted unbracketed, whatever it is.
    c.rule("Call", 'printf("%ld\\n", (long)({args}))')
    c.rule("While", "while ({test}) {{\n{body:\n}\n}}")
    c.rule("If", "if ({test}) {{\n{body:\n}\n}} else {{\n{orelse:\n}\n}}")
    return c


def compile_function(fn: ast.FunctionDef, grammar: Grammar, names: set[str]) -> str:
    """One C function. Every local is a `long`, declared up front."""
    c = emitter(grammar)
    params = ", ".join(f"long {a.arg}" for a in fn.args.args)
    locals_ = sorted(names - {a.arg for a in fn.args.args})
    body = [f"long {n} = 0;" for n in locals_]
    for stmt in fn.body:
        body += c.to_lines(stmt)
    inner = "\n".join("    " + line for line in body if line)
    return f"long {fn.name}({params}) {{\n{inner}\n}}\n"
