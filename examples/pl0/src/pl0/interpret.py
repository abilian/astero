"""A direct interpreter for PL/0, used as the compiler's oracle.

The tutorial for TinyPy could check its compiler against CPython, because
TinyPy is a subset of Python. PL/0 is nobody's subset, so the oracle has to
be built: this walks the tree and runs it, with an environment chain where
the compiler uses static links.

It shares the parser and nothing else. In particular it does not use the
grammar, the scope tree, or the frame layout, so agreeing with
`codegen` + `machine` is evidence about both.

This is a weaker oracle than CPython and it is worth being clear about that:
two implementations by one author can share a misreading of the language.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import syntax
from .codegen import OPS, RELS
from .machine import BINARY


@dataclass
class Env:
    """One block's names, and the block that encloses it."""

    parent: Env | None = None
    values: dict[str, int] = field(default_factory=dict)
    consts: dict[str, int] = field(default_factory=dict)
    procs: dict[str, tuple[syntax.Block, Env]] = field(default_factory=dict)

    def get(self, name: str) -> int:
        env: Env | None = self
        while env is not None:
            if name in env.consts:
                return env.consts[name]
            if name in env.values:
                return env.values[name]
            env = env.parent
        raise KeyError(name)

    def set(self, name: str, value: int) -> None:
        env: Env | None = self
        while env is not None:
            if name in env.values:
                env.values[name] = value
                return
            env = env.parent
        raise KeyError(name)

    def procedure(self, name: str) -> tuple[syntax.Block, Env]:
        env: Env | None = self
        while env is not None:
            if name in env.procs:
                return env.procs[name]
            env = env.parent
        raise KeyError(name)


def run(program: syntax.Program, *, limit: int = 200_000) -> list[int]:
    written: list[int] = []
    steps = 0

    def enter(block: syntax.Block, parent: Env | None) -> Env:
        env = Env(parent=parent)
        for const in block.consts:
            env.consts[const.name] = const.value
        for var in block.variables:
            env.values[var.name] = 0
        for proc in block.procedures:
            env.procs[proc.name] = (proc.block, env)
        return env

    def expr(node, env: Env) -> int:
        match node:
            case syntax.Number(value=v):
                return v
            case syntax.Name(name=n):
                return env.get(n)
            case syntax.Neg(value=v):
                return -expr(v, env)
            case syntax.BinOp(op=op, left=a, right=b):
                return BINARY[OPS[op]](expr(a, env), expr(b, env))
        raise TypeError(node)

    def cond(node, env: Env) -> bool:
        match node:
            case syntax.Odd(value=v):
                return expr(v, env) % 2 == 1
            case syntax.Compare(op=op, left=a, right=b):
                return bool(BINARY[RELS[op]](expr(a, env), expr(b, env)))
        raise TypeError(node)

    def stmt(node, env: Env) -> None:
        nonlocal steps
        steps += 1
        if steps > limit:
            raise RuntimeError("program did not terminate")
        match node:
            case syntax.Empty():
                return
            case syntax.Assign(name=n, value=v):
                env.set(n, expr(v, env))
            case syntax.Write(value=v):
                written.append(expr(v, env))
            case syntax.Begin(body=body):
                for inner in body:
                    stmt(inner, env)
            case syntax.If(cond=c, then=t):
                if cond(c, env):
                    stmt(t, env)
            case syntax.While(cond=c, body=b):
                while cond(c, env):
                    stmt(b, env)
            case syntax.Call(name=n):
                block, declared_in = env.procedure(n)
                stmt(block.body, enter(block, declared_in))
            case _:
                raise TypeError(node)

    root = enter(program.block, None)
    stmt(program.block.body, root)
    return written
