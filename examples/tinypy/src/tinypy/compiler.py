"""A whole compiler for a Python subset, written with astero and nothing else.

The experiment this exists for: every finding about astero so far came from
retrofitting it into three finished compilers, which says what it *fits* and
never what it is *missing to begin with*. Cocktail's question is the other
one — can you build a compiler with this? — and it had not been asked.

TinyPy: integers, variables, `if`/`while`, comparison and arithmetic, `print`.
Target: a stack machine, because a stack target makes emission post-order and
so exercises the same path p2w's WAT does.

Every place this file works around a gap is marked `GAP:` and the gaps are the
result. Nothing here is a workaround for the *language* being small.
"""

from __future__ import annotations

import ast

from astero.coverage import Coverage
from astero.emit_rules import Emitter
from astero.python import PY, VARS, Pass, rules
from astero.scopes import names_bound_by

# --------------------------------------------------------------------- grammar
#
# TinyPy is a subset of Python, so its grammar is Python's restricted to the
# productions it admits. astero declares Python once; a subset is a filter.

ADMITTED = frozenset({
    "Module",
    "FunctionDef",
    "arguments",
    "arg",
    "Return",
    "Assign",
    "AugAssign",
    "If",
    "While",
    "Expr",
    "Pass",
    "Name",
    "Constant",
    "BinOp",
    "Compare",
    "Call",
    "Add",
    "Sub",
    "Mult",
    "FloorDiv",
    "Mod",
    "Lt",
    "LtE",
    "Gt",
    "GtE",
    "Eq",
    "NotEq",
})

TINYPY = PY.subset(ADMITTED, name="tinypy")


def check(tree: ast.AST) -> list[str]:
    """Refuse what TinyPy does not admit, naming the production."""
    return [
        f"line {n.lineno}: {type(n).__name__} is not TinyPy"
        for n in ast.walk(tree)
        if isinstance(n, (ast.stmt, ast.expr)) and type(n).__name__ not in ADMITTED
    ]


# -------------------------------------------------------------------- desugar

DESUGAR = Pass(
    "desugar",
    rules("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"),
    eliminates=(ast.AugAssign,),
    grammar=TINYPY,
)


# --------------------------------------------------------------------- naming
#
# Locals get a slot each. `names_bound_by` answers which names a node binds,
# from the roles, so this never enumerates target shapes.


def slots(fn: ast.FunctionDef) -> dict[str, int]:
    names = [a.arg for a in fn.args.args]
    # The body, not the whole node: a function binds its own name in the
    # scope that encloses it, so walking `fn` allocated a slot for `f` that
    # nothing ever loaded.
    for stmt in fn.body:
        for node in ast.walk(stmt):
            names += sorted(names_bound_by(node, TINYPY, VARS))
    return {n: i for i, n in enumerate(dict.fromkeys(names))}


# -------------------------------------------------------------------- emission
#
# A stack machine, so the operator follows its operands and template
# composition produces post-order. `levels=None`: no precedence, because a
# stack has no brackets.

BINOPS = {
    ast.Add: "ADD",
    ast.Sub: "SUB",
    ast.Mult: "MUL",
    ast.FloorDiv: "DIV",
    ast.Mod: "MOD",
}
COMPARES = {
    ast.Lt: "LT",
    ast.LtE: "LE",
    ast.Gt: "GT",
    ast.GtE: "GE",
    ast.Eq: "EQ",
    ast.NotEq: "NE",
}


def emitter(local: dict[str, int]) -> Emitter:
    """The whole compiler, expressions and statements alike, as rules.

    Control flow is a template like any other once the notation can name a
    label. `{&top}` is a label unique to this node, so the same name twice in
    one template is the same label, and a second `while` gets a different one.

    Statement *structure* needed nothing new: a body hole renders the list and
    a newline separator joins it. That was the surprise — "statements have no
    notation" turned out to be "labels have no notation".
    """
    vm = Emitter(TINYPY, levels=None)
    vm.projection("slot", lambda name: str(local[name]))
    vm.projection("store", lambda target: str(local[target.id]))
    vm.projection("lit", str)
    vm.projection("binop", lambda op: BINOPS[type(op)])
    vm.projection("cmp", lambda ops: COMPARES[type(ops)])

    vm.rule("Name", "PUSH {id:slot}")
    vm.rule("Constant", "CONST {value:lit}")
    vm.rule("BinOp", "{left}\n{right}\n{op:binop}")
    vm.rule("Compare", "{left}\n{comparators}\n{ops:cmp}")

    vm.rule("Assign", "{value}\nSTORE {targets:store}")
    vm.rule("Return", "{value}\nRET")
    vm.rule("Pass", "")
    vm.rule("Expr", "{value}")
    # TinyPy admits exactly one call, `print`, so the rule needs no guard. A
    # language with more would want one, and `OpIs`/`Is` cannot ask "is the
    # callee named `print`" — the guard vocabulary is about a node's types and
    # shape, not its contents.
    vm.rule("Call", "{args}\nPRINT")
    vm.rule(
        "While",
        "{&top}:\n{test}\nJZ {&done}\n{body:\n}\nJMP {&top}\n{&done}:",
    )
    vm.rule(
        "If",
        "{test}\nJZ {&else}\n{body:\n}\nJMP {&end}\n{&else}:\n{orelse:\n}\n{&end}:",
    )
    return vm


STATEMENTS = frozenset({"Assign", "Return", "If", "While", "Expr", "Pass"})


def coverage() -> Coverage:
    """Every statement TinyPy admits has a rule. The gate, from the grammar."""
    return Coverage(handled=emitter({}).covered(), expected=STATEMENTS)


def compile_function(fn: ast.FunctionDef) -> list[str]:
    vm = emitter(slots(fn))
    code = [f"STORE {i}" for i, _ in enumerate(fn.args.args)]
    for stmt in fn.body:
        # `to_lines`, not `to_text().splitlines()`: a break a template wrote is
        # structure, a newline inside a value is not. TinyPy has no strings, so
        # both agree here — but the right one costs nothing.
        code += vm.to_lines(stmt)
    return [line for line in code if line]


def compile_source(source: str) -> list[str]:
    tree = ast.parse(source)
    problems = check(tree)
    if problems:
        raise SyntaxError("; ".join(problems))
    return compile_function(DESUGAR(tree).body[0])
