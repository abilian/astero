"""Short ways to build Python syntax nodes.

The compiler builds a Python `ast` tree and hands it to
`astero.python.emit`. Writing `ast.Subscript(value=ast.Attribute(...), ...)`
out in full every time would bury the interesting part, so these are the
half-dozen shapes it needs, named. Nothing here decides anything;
`compile.py` and `patterns.py` both build with it.
"""

from __future__ import annotations

import ast
import keyword
from typing import Any

#: The name the emitted module binds the runtime to.
RUNTIME = "_rt"


def name(text: str) -> ast.Name:
    return ast.Name(id=text, ctx=ast.Load())


#: What `ast.Constant` accepts. Every caml-prépa literal is one of these,
#: since `char` is a one-character `str` and `unit` is `None`.
Literal = str | complex | None


def const(value: Literal) -> ast.Constant:
    return ast.Constant(value=value)


def attribute(value: ast.expr, label: str) -> ast.Attribute:
    return ast.Attribute(value=value, attr=label, ctx=ast.Load())


def call(fn: ast.expr, *args: ast.expr) -> ast.Call:
    return ast.Call(func=fn, args=list(args), keywords=[])


def runtime(label: str) -> ast.Attribute:
    return attribute(name(RUNTIME), label)


def field_of(value: ast.expr, label: str) -> ast.Subscript:
    """`x.fields['l']`, which is how a record and a `ref` are both read."""
    return ast.Subscript(
        value=attribute(value, "fields"), slice=const(label), ctx=ast.Load()
    )


def item(value: ast.expr, index: int) -> ast.Subscript:
    return ast.Subscript(value=value, slice=const(index), ctx=ast.Load())


def store(target: str, value: ast.expr) -> ast.Assign:
    return ast.Assign(targets=[ast.Name(id=target, ctx=ast.Store())], value=value)


def sanitize(text: str) -> str | None:
    """An OCaml name as a Python one, or None where none exists.

    `x'` is `x_` and `List.map` is `List_map`. An operator such as `+` has
    no Python spelling at all, so it is read out of `runtime.ENV` instead.
    """
    made = text.replace("'", "_").replace(".", "_")
    if not made.isidentifier():
        return None
    return f"{made}_" if keyword.iskeyword(made) else made


def arguments(labels: list[str]) -> ast.arguments:
    return ast.arguments(
        posonlyargs=[],
        args=[ast.arg(arg=label) for label in labels],
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
    )


def function_def(label: str, args: ast.arguments, body: list[ast.stmt]) -> ast.stmt:
    """A `def`, on every interpreter this runs on.

    `ast.FunctionDef` grew a `type_params` field in 3.12, and `ast.unparse`
    reads it there, so it has to be set on 3.12 and cannot be passed on
    3.11. `_fields` is what the interpreter itself says.
    """
    extra: dict[str, Any] = (
        {"type_params": []} if "type_params" in ast.FunctionDef._fields else {}
    )
    return ast.FunctionDef(
        name=label, args=args, body=body, decorator_list=[], returns=None, **extra
    )
