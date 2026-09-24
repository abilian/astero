"""The second back end: caml-prépa in, Python source out.

The interpreter runs the tree directly. This turns it into a Python
programme that does the same thing, which you can read, save, and run
without this compiler. `python -m ocaml --python yours.ml` prints it.

    let rec fact n = if n <= 1 then 1 else n * fact (n - 1)

becomes

    def fact(n):
        return 1 if _rt.BINARY_OPS['<='](n, 1) else n * fact(n - 1)

It costs an emitter and nothing else, because the values and the standard
library are `back/runtime.py`, already written for the interpreter, and the
emitted programme calls the same functions. So running a programme both
ways and comparing is a test of this file rather than a comparison of two
languages.

Three things it decides that the interpreter does not:

* **Arity.** `let f x y = e` is known to take two parameters, because
  `Binding.params` kept them, so it becomes `def f(x, y)` and a saturated
  `f a b` becomes `f(a, b)`. Everything else goes through `runtime.apply`,
  which works out at run time how many arguments the callee wants.

* **Or-patterns are expanded** into one case per alternative, so the tests
  in `patterns.py` are paths into the value and never a disjunction.

* **Names.** OCaml identifiers may contain `'` and Python's may not, and a
  `let` shadows where a Python assignment rebinds. Every binder gets a
  fresh Python name, seeded from `astero.python.hygiene.all_names` over the
  OCaml tree, so a generated temporary cannot collide with one the
  programme already uses.

The Python is built as an `ast` tree and rendered by
`astero.python.emit`, which is that emitter's first source language that is
not Python.
"""

from __future__ import annotations

import ast
import keyword
from dataclasses import dataclass, field
from typing import Any

from astero.python.emit import emit_module
from astero.python.hygiene import all_names
from ocaml import syntax as s
from ocaml.front.parser import parse
from ocaml.middle.grammar import OCAML

from .patterns import bindings, expand, tests
from .pyast import (
    RUNTIME,
    arguments,
    attribute,
    call,
    const,
    field_of,
    function_def,
    name,
    runtime,
    sanitize,
    store,
)


@dataclass
class Scope:
    """OCaml name to Python name, one level per binding form."""

    names: dict[str, str] = field(default_factory=dict)
    parent: Scope | None = None

    def child(self) -> Scope:
        return Scope(parent=self)

    def lookup(self, key: str) -> str | None:
        found: Scope | None = self
        while found is not None:
            if key in found.names:
                return found.names[key]
            found = found.parent
        return None


#: Operators whose Python spelling means the same thing. Everything else
#: goes through `runtime.BINARY_OPS`, which is where `/`, `mod`, `lsr`, the
#: comparisons and structural equality differ from Python's.
DIRECT_BINOPS: dict[str, type[ast.operator]] = {
    "+": ast.Add,
    "-": ast.Sub,
    "*": ast.Mult,
    "+.": ast.Add,
    "-.": ast.Sub,
    "*.": ast.Mult,
    "**": ast.Pow,
    "^": ast.Add,
    "land": ast.BitAnd,
    "lor": ast.BitOr,
    "lxor": ast.BitXor,
    "lsl": ast.LShift,
    "asr": ast.RShift,
}

BOOL_OPS: dict[str, type[ast.boolop]] = {"&&": ast.And, "||": ast.Or}

Lowered = tuple[list[ast.stmt], ast.expr]


@dataclass
class Compiler:
    """One compilation. Holds the names taken and the arities known."""

    #: Python names already handed out.
    used: set[str]
    #: Names the source itself uses. A binder may still take its own
    #: spelling; a *generated* name may not, or a temporary could shadow one.
    reserved: set[str] = field(default_factory=set)
    prelude: set[str] = field(default_factory=set)
    arity: dict[str, int] = field(default_factory=dict)
    counter: int = 0

    def fresh(self, hint: str = "t") -> str:
        while True:
            self.counter += 1
            made = f"_{hint}{self.counter}"
            if made not in self.used and made not in self.reserved:
                self.used.add(made)
                return made

    def define(self, scope: Scope, key: str) -> str:
        """A Python name for an OCaml binder, freshened where it shadows."""
        wanted = sanitize(key) or "_v"
        made = wanted
        suffix = 1
        while made in self.used:
            suffix += 1
            made = f"{wanted}_{suffix}"
        self.used.add(made)
        scope.names[key] = made
        return made

    def value(self, scope: Scope, key: str) -> ast.expr:
        """A use: a local, or a prelude name bound in the preamble."""
        found = scope.lookup(key)
        if found is not None:
            return name(found)
        label = sanitize(key)
        if label is None:
            return ast.Subscript(value=runtime("ENV"), slice=const(key), ctx=ast.Load())
        self.prelude.add(key)
        return name(label)


# ---------------------------------------------------------------- lowering


def _expr_stmt(value: ast.expr) -> ast.stmt:
    return ast.Expr(value=value)


class Lowering(Compiler):
    """The lowering itself. `Compiler` holds the naming; this holds the rules."""

    # ------------------------------------------------------------ helpers

    def into(self, node: Any, scope: Scope, target: str) -> list[ast.stmt]:
        """Lower `node` and put its value in `target`."""
        stmts, value = self.expr(node, scope)
        return [*stmts, store(target, value)]

    def destructure(
        self, pattern: Any, subject: ast.expr, scope: Scope
    ) -> list[ast.stmt]:
        """Bind through an irrefutable pattern, checking it anyway."""
        only = expand(pattern)[0]
        out: list[ast.stmt] = []
        checks = tests(only, subject)
        if checks:
            out.append(
                ast.If(
                    test=ast.UnaryOp(op=ast.Not(), operand=_all_of(checks)),
                    body=[_expr_stmt(call(runtime("fail"), const("Match_failure")))],
                    orelse=[],
                )
            )
        for label, path in bindings(only, subject):
            out.append(store(self.define(scope, label), path))
        return out

    def parameters(
        self, params: list[Any], scope: Scope
    ) -> tuple[list[str], list[ast.stmt]]:
        """One Python parameter per OCaml one, destructuring where it is not
        a plain variable."""
        labels: list[str] = []
        prologue: list[ast.stmt] = []
        for param in params:
            if isinstance(param, s.PVar):
                labels.append(self.define(scope, param.name))
                continue
            holder = self.fresh("p")
            labels.append(holder)
            prologue += self.destructure(param, name(holder), scope)
        return labels, prologue

    def function(self, params: list[Any], body: Any, scope: Scope) -> Lowered:
        """`fun x -> e`: a lambda where it fits, a `def` where it does not."""
        inner = scope.child()
        labels, prologue = self.parameters(params, inner)
        stmts, value = self.expr(body, inner)
        if not prologue and not stmts:
            return [], ast.Lambda(args=arguments(labels), body=value)
        made = self.fresh("fn")
        body_stmts = [*prologue, *stmts, ast.Return(value=value)]
        return [function_def(made, arguments(labels), body_stmts)], name(made)

    def cases(
        self,
        subject: ast.expr,
        cases: list[s.Case],
        scope: Scope,
        unmatched: list[ast.stmt],
    ) -> Lowered:
        """A `match`, as one guarded `if` per or-free alternative.

        A flag rather than `elif`, because a guard that fails has to fall
        through to the next case and an `elif` chain cannot.
        """
        holder = self.fresh("s")
        result = self.fresh("m")
        matched = self.fresh("ok")
        out: list[ast.stmt] = [
            store(holder, subject),
            store(matched, const(False)),
            store(result, const(None)),
        ]
        for case in cases:
            for pattern in expand(case.pattern):
                out.append(
                    self._case(
                        pattern,
                        case,
                        name(holder),
                        scope,
                        result=result,
                        matched=matched,
                    )
                )
        out.append(
            ast.If(
                test=ast.UnaryOp(op=ast.Not(), operand=name(matched)),
                body=unmatched,
                orelse=[],
            )
        )
        return out, name(result)

    def _case(
        self,
        pattern: Any,
        case: s.Case,
        subject: ast.expr,
        scope: Scope,
        *,
        result: str,
        matched: str,
    ) -> ast.stmt:
        inner = scope.child()
        body: list[ast.stmt] = [
            store(self.define(inner, label), path)
            for label, path in bindings(pattern, subject)
        ]
        taken: list[ast.stmt] = [
            *self.into(case.body, inner, result),
            store(matched, const(True)),
        ]
        if case.guard is not None:
            guard_stmts, guard = self.expr(case.guard, inner)
            body += guard_stmts
            body.append(ast.If(test=guard, body=taken, orelse=[]))
        else:
            body += taken
        unless = ast.UnaryOp(op=ast.Not(), operand=name(matched))
        guard = _all_of([unless, *tests(pattern, subject)])
        return ast.If(test=guard, body=body, orelse=[])

    # -------------------------------------------------------- expressions

    def expr(self, node: Any, scope: Scope) -> Lowered:
        match node:
            case s.Int(value=value) | s.Float(value=value) | s.Bool(value=value):
                return [], const(value)
            case s.Char(value=value) | s.Str(value=value):
                return [], const(value)
            case s.Unit():
                return [], const(None)
            case s.Var(name=label):
                return [], self.value(scope, label)
            case s.Construct(name="::", args=[head, tail]):
                stmts, parts = self._many([head, tail], scope)
                return stmts, call(runtime("cons"), *parts)
            case s.Construct(name=label, args=args):
                stmts, parts = self._many(args, scope)
                return stmts, call(
                    runtime("Value"),
                    const(label),
                    ast.Tuple(elts=parts, ctx=ast.Load()),
                )
            case s.Tuple(items=items):
                stmts, parts = self._many(items, scope)
                return stmts, ast.Tuple(elts=parts, ctx=ast.Load())
            case s.ListLit(items=items):
                stmts, parts = self._many(items, scope)
                if not parts:
                    return stmts, runtime("NIL")
                made = ast.List(elts=parts, ctx=ast.Load())
                return stmts, call(runtime("from_python"), made)
            case s.ArrayLit(items=items):
                stmts, parts = self._many(items, scope)
                return stmts, ast.List(elts=parts, ctx=ast.Load())
            case s.Record(fields=fields, base=base):
                return self._record(fields, base, scope)
            case s.Apply(fn=fn, args=args):
                return self._apply(fn, args, scope)
            case s.BinOp(op=op, left=left, right=right):
                return self._binop(op, left, right, scope)
            case s.UnOp(op="!", value=value):
                stmts, found = self.expr(value, scope)
                return stmts, field_of(found, "contents")
            case s.UnOp(value=value):
                stmts, found = self.expr(value, scope)
                return stmts, ast.UnaryOp(op=ast.USub(), operand=found)
            case s.If(cond=cond, then=then, otherwise=otherwise):
                return self._if(cond, then, otherwise, scope)
            case s.Seq(items=items):
                out: list[ast.stmt] = []
                for entry in items[:-1]:
                    stmts, found = self.expr(entry, scope)
                    out += [*stmts, _expr_stmt(found)]
                stmts, found = self.expr(items[-1], scope)
                return [*out, *stmts], found
            case s.LetIn(recursive=recursive, bindings=entries, body=body):
                inner = scope.child()
                out = self.bind(recursive, entries, inner)
                stmts, found = self.expr(body, inner)
                return [*out, *stmts], found
            case s.Fun(params=params, body=body):
                return self.function(params, body, scope)
            case s.Function(cases=cases):
                return self._function_expr(cases, scope)
            case s.Match(scrutinee=scrutinee, cases=cases):
                stmts, found = self.expr(scrutinee, scope)
                more, value = self.cases(found, cases, scope, _match_failure())
                return [*stmts, *more], value
            case s.Try(body=body, cases=cases):
                return self._try(body, cases, scope)
            case s.While(cond=cond, body=body):
                return self._while(cond, body, scope), const(None)
            case s.For(var=var, start=start, stop=stop, down=down, body=body):
                made = self._for(var, start, stop, body, scope, down=down)
                return made, const(None)
            case s.GetField(value=value, label=label):
                stmts, found = self.expr(value, scope)
                return stmts, field_of(found, label)
            case s.SetField(value=value, label=label, rhs=rhs):
                stmts, parts = self._many([value, rhs], scope)
                target = ast.Subscript(
                    value=attribute(parts[0], "fields"),
                    slice=const(label),
                    ctx=ast.Store(),
                )
                made = ast.Assign(targets=[target], value=parts[1])
                return [*stmts, made], const(None)
            case s.ArrayGet(array=array, index=index):
                stmts, parts = self._many([array, index], scope)
                return stmts, call(runtime("at"), *parts)
            case s.ArraySet(array=array, index=index, rhs=rhs):
                stmts, parts = self._many([array, index, rhs], scope)
                return [*stmts, _expr_stmt(call(runtime("put"), *parts))], const(None)
            case s.StringGet(value=value, index=index):
                stmts, parts = self._many([value, index], scope)
                return stmts, call(runtime("at"), *parts)
            case s.Constraint(value=value):
                return self.expr(value, scope)
        raise TypeError(f"no rule for {type(node).__name__}")

    # ---------------------------------------------------------- the parts

    def _many(
        self, nodes: list[Any], scope: Scope
    ) -> tuple[list[ast.stmt], list[ast.expr]]:
        out: list[ast.stmt] = []
        found: list[ast.expr] = []
        for node in nodes:
            stmts, value = self.expr(node, scope)
            out += stmts
            found.append(value)
        return out, found

    def _record(self, fields: list[s.FieldBind], base: Any, scope: Scope) -> Lowered:
        out: list[ast.stmt] = []
        keys: list[ast.expr | None] = []
        values: list[ast.expr] = []
        if base is not None:
            stmts, found = self.expr(base, scope)
            out += stmts
            keys.append(None)
            values.append(attribute(found, "fields"))
        for entry in fields:
            stmts, found = self.expr(entry.value, scope)
            out += stmts
            keys.append(const(entry.label))
            values.append(found)
        return out, call(runtime("Record"), ast.Dict(keys=keys, values=values))

    def _apply(self, fn: Any, args: list[Any], scope: Scope) -> Lowered:
        out, values = self._many(args, scope)
        if isinstance(fn, s.Var):
            target = scope.lookup(fn.name)
            if target is None:
                # Every prelude value takes one argument at a time, so a
                # chain of calls is exact and needs no `apply`.
                found = self.value(scope, fn.name)
                for value in values:
                    found = call(found, value)
                return out, found
            if self.arity.get(target) == len(values):
                return out, call(name(target), *values)
        head, found = self.expr(fn, scope)
        return [*head, *out], call(runtime("apply"), found, *values)

    def _binop(self, op: str, left: Any, right: Any, scope: Scope) -> Lowered:
        if op in BOOL_OPS:
            out, parts = self._many([left, right], scope)
            return out, ast.BoolOp(op=BOOL_OPS[op](), values=parts)
        if op == ":=":
            out, parts = self._many([left, right], scope)
            target = ast.Subscript(
                value=attribute(parts[0], "fields"),
                slice=const("contents"),
                ctx=ast.Store(),
            )
            return [*out, ast.Assign(targets=[target], value=parts[1])], const(None)
        out, parts = self._many([left, right], scope)
        if op in DIRECT_BINOPS:
            return out, ast.BinOp(left=parts[0], op=DIRECT_BINOPS[op](), right=parts[1])
        if op == "=":
            return out, call(runtime("equal"), *parts)
        table = ast.Subscript(
            value=runtime("BINARY_OPS"), slice=const(op), ctx=ast.Load()
        )
        return out, call(table, *parts)

    def _if(self, cond: Any, then: Any, otherwise: Any, scope: Scope) -> Lowered:
        head, test = self.expr(cond, scope)
        then_stmts, then_value = self.expr(then, scope)
        else_stmts: list[ast.stmt] = []
        else_value: ast.expr = const(None)
        if otherwise is not None:
            else_stmts, else_value = self.expr(otherwise, scope)
        if not then_stmts and not else_stmts:
            made = ast.IfExp(test=test, body=then_value, orelse=else_value)
            return head, made
        result = self.fresh("r")
        branch = ast.If(
            test=test,
            body=[*then_stmts, store(result, then_value)],
            orelse=[*else_stmts, store(result, else_value)],
        )
        return [*head, branch], name(result)

    def _function_expr(self, cases: list[s.Case], scope: Scope) -> Lowered:
        inner = scope.child()
        holder = self.fresh("a")
        stmts, value = self.cases(name(holder), cases, inner, _match_failure())
        made = self.fresh("fn")
        body = [*stmts, ast.Return(value=value)]
        return [function_def(made, arguments([holder]), body)], name(made)

    def _try(self, body: Any, cases: list[s.Case], scope: Scope) -> Lowered:
        result = self.fresh("r")
        caught = self.fresh("e")
        handler = self.cases(
            attribute(name(caught), "value"),
            cases,
            scope,
            [ast.Raise(exc=None, cause=None)],
        )
        made = ast.Try(
            body=self.into(body, scope, result),
            handlers=[
                ast.ExceptHandler(
                    type=runtime("OCamlError"),
                    name=caught,
                    body=[*handler[0], store(result, handler[1])],
                )
            ],
            orelse=[],
            finalbody=[],
        )
        return [made], name(result)

    def _while(self, cond: Any, body: Any, scope: Scope) -> list[ast.stmt]:
        head, test = self.expr(cond, scope)
        stmts, value = self.expr(body, scope)
        inner = [*stmts, _expr_stmt(value)]
        if not head:
            return [ast.While(test=test, body=inner, orelse=[])]
        guard = ast.If(
            test=ast.UnaryOp(op=ast.Not(), operand=test),
            body=[ast.Break()],
            orelse=[],
        )
        return [ast.While(test=const(True), body=[*head, guard, *inner], orelse=[])]

    def _for(
        self, var: s.PVar, start: Any, stop: Any, body: Any, scope: Scope, *, down: bool
    ) -> list[ast.stmt]:
        head, parts = self._many([start, stop], scope)
        step = -1 if down else 1
        past: ast.operator = ast.Sub() if down else ast.Add()
        limit = ast.BinOp(left=parts[1], op=past, right=const(1))
        bounds = call(name("range"), parts[0], limit, const(step))
        inner = scope.child()
        label = self.define(inner, var.name)
        stmts, value = self.expr(body, inner)
        made = ast.For(
            target=ast.Name(id=label, ctx=ast.Store()),
            iter=bounds,
            body=[*stmts, _expr_stmt(value)],
            orelse=[],
        )
        return [*head, made]

    # ------------------------------------------------------------ binding

    def bind(
        self, recursive: bool, entries: list[s.Binding], scope: Scope
    ) -> list[ast.stmt]:
        if recursive:
            for entry in entries:
                for label, _ in bindings(expand(entry.pattern)[0], name("_")):
                    self.define(scope, label)
        out: list[ast.stmt] = []
        for entry in entries:
            out += self._one_binding(entry, scope, predefined=recursive)
        return out

    def _one_binding(
        self, entry: s.Binding, scope: Scope, *, predefined: bool
    ) -> list[ast.stmt]:
        pattern = entry.pattern
        if isinstance(pattern, s.PVar) and entry.params:
            return self._define_function(
                pattern.name, entry, scope, predefined=predefined
            )
        stmts, value = (
            self.function(entry.params, entry.value, scope)
            if entry.params
            else self.expr(entry.value, scope)
        )
        if isinstance(pattern, s.PVar):
            target = scope.lookup(pattern.name) if predefined else None
            return [*stmts, store(target or self.define(scope, pattern.name), value)]
        if _for_effect(entry.pattern):
            # `let () = e` and `let _ = e` bind nothing: the value is the
            # point, and a temporary plus a check would say less.
            return [*stmts, _expr_stmt(value)]
        holder = self.fresh("b")
        rest = self.destructure(entry.pattern, name(holder), scope)
        return [*stmts, store(holder, value), *rest]

    def _define_function(
        self, label: str, entry: s.Binding, scope: Scope, *, predefined: bool
    ) -> list[ast.stmt]:
        """`let f x y = e` as `def f(x, y)`, which is what arity buys.

        The name is chosen after the body is lowered when the binding is not
        recursive, so `let f = ... f ...` reads the *outer* `f` and the new
        one is freshened.
        """
        inner = scope.child()
        target = scope.lookup(label) if predefined else None
        if target is not None:
            self.arity[target] = len(entry.params)
        labels, prologue = self.parameters(entry.params, inner)
        stmts, value = self.expr(entry.value, inner)
        if target is None:
            target = self.define(scope, label)
            self.arity[target] = len(entry.params)
        body = [*prologue, *stmts, ast.Return(value=value)]
        return [function_def(target, arguments(labels), body)]


def _for_effect(pattern: Any) -> bool:
    """`()` and `_`, the two patterns a `let` uses to mean "run this"."""
    return isinstance(pattern, s.PWild) or (
        isinstance(pattern, s.PLit) and isinstance(pattern.value, s.Unit)
    )


def _all_of(parts: list[ast.expr]) -> ast.expr:
    return parts[0] if len(parts) == 1 else ast.BoolOp(op=ast.And(), values=parts)


def _match_failure() -> list[ast.stmt]:
    return [_expr_stmt(call(runtime("fail"), const("Match_failure")))]


# -------------------------------------------------------------- the module


def lower_item(low: Lowering, node: Any, scope: Scope) -> list[ast.stmt]:
    match node:
        case s.LetItem(recursive=recursive, bindings=entries):
            return low.bind(recursive, entries, scope)
        case s.TypeItem() | s.ExnItem():
            # A constructed value carries its own tag, so a declaration
            # emits nothing. `types.py` is what reads these.
            return []
        case s.ExprItem(value=value):
            stmts, found = low.expr(value, scope)
            return [*stmts, _expr_stmt(found)]
    raise TypeError(f"no rule for {type(node).__name__}")


def build(structure: s.Structure) -> ast.Module:
    """The Python module this structure compiles to."""
    # `all_names` reaches every identifier slot the grammar declares, in
    # every namespace, so a generated temporary cannot collide with one
    # the programme already uses.
    taken = {sanitize(found) or "" for found in all_names(structure, OCAML)}
    low = Lowering(used={RUNTIME, *keyword.kwlist}, reserved=taken)
    scope = Scope()
    body: list[ast.stmt] = []
    for entry in structure.items:
        body += lower_item(low, entry, scope)
    made = ast.Module(body=[*_preamble(low), *body], type_ignores=[])
    # astero's emitter reads a node's span to attach a source map, and
    # `ast.unparse` wants positions for a `def` header. Nothing here carries
    # one, so they are filled in before rendering.
    return ast.fix_missing_locations(made)


def _preamble(low: Lowering) -> list[ast.stmt]:
    """The runtime import, and one binding per prelude name actually used."""
    out: list[ast.stmt] = [
        ast.ImportFrom(
            module="ocaml.back",
            names=[ast.alias(name="runtime", asname=RUNTIME)],
            level=0,
        )
    ]
    for key in sorted(low.prelude):
        label = sanitize(key)
        if label is None:
            continue
        out.append(
            store(
                label,
                ast.Subscript(value=runtime("ENV"), slice=const(key), ctx=ast.Load()),
            )
        )
    return out


def compile_structure(structure: s.Structure) -> str:
    """Python source, rendered by astero's own emitter."""
    return emit_module(build(structure))


def compile_source(source: str) -> str:
    return compile_structure(parse(source))
