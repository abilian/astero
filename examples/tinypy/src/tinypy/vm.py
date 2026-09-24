"""A stack machine for TinyPy, so the compiler can be checked against CPython."""

from __future__ import annotations

import operator
from collections.abc import Callable


def _cmp(op):
    """A comparison yields 0 or 1: the machine has only integers."""
    return lambda a, b: int(op(a, b))


OPS: dict[str, Callable[..., int]] = {
    "ADD": operator.add,
    "SUB": operator.sub,
    "MUL": operator.mul,
    "DIV": operator.floordiv,
    "MOD": operator.mod,
    "LT": _cmp(operator.lt),
    "LE": _cmp(operator.le),
    "GT": _cmp(operator.gt),
    "GE": _cmp(operator.ge),
    "EQ": _cmp(operator.eq),
    "NE": _cmp(operator.ne),
}


class Machine:
    """The state one instruction can touch, so `step` takes one argument."""

    def __init__(self, code: list[str], args: tuple[int, ...]) -> None:
        self.code = code
        self.labels = {ln[:-1]: i for i, ln in enumerate(code) if ln.endswith(":")}
        self.stack: list[int] = list(args)
        self.local: dict[int, int] = {}
        self.out: list[int] = []
        self.pc = 0

    def step(self, op: str, rest: str) -> bool:
        """Run one instruction. False means halt."""
        match op:
            case "CONST":
                self.stack.append(int(rest))
            case "PUSH":
                self.stack.append(self.local[int(rest)])
            case "STORE":
                self.local[int(rest)] = self.stack.pop()
            case "PRINT":
                self.out.append(self.stack.pop())
            case "JMP":
                self.pc = self.labels[rest]
            case "JZ":
                if not self.stack.pop():
                    self.pc = self.labels[rest]
            case "RET":
                return False
            case _:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(OPS[op](a, b))
        return True


def run(code: list[str], *args: int) -> int | None:
    """Run `code` with `args` already on the stack, as the calling convention."""
    m = Machine(code, args)
    while m.pc < len(m.code):
        line = m.code[m.pc]
        m.pc += 1
        if line.endswith(":"):
            continue
        op, _, rest = line.partition(" ")
        if not m.step(op, rest):
            return m.stack.pop()
    return m.out[-1] if m.out else None
