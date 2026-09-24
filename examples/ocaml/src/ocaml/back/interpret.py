"""The first back end: walk the tree and do what it says.

The simplest thing that can be called running a programme. `eval_expr` takes
a node and an environment and returns a value: for `BinOp("+", a, b)` it
evaluates `a`, evaluates `b`, and adds them. One `case` per kind of node,
and you can read the whole language's behaviour in one function.

It is also the reference semantics. `specification.md`, *Evaluation*, is what this
implements, and where the two disagree one of them is wrong.

Three things worth reading:

* **A function value is a Python callable of one argument**, because OCaml
  functions are curried. `Fun` with three parameters builds three nested
  closures, and partial application then needs no arity anywhere.

* **`let rec` fills a scope its closures already hold.** The child mapping
  is created first and populated after, so a closure built during the pass
  can see names the pass is still binding. That is the same fact the scope
  declaration in `middle/grammar.py` states, arrived at from the other
  side.

* **The environment is a `ChainMap`.** A new scope is a new child; nothing
  is copied, and shadowing is the mapping's own rule. Each top-level `let`
  opens one rather than writing into the current one, so a closure made
  earlier keeps reading the binding it captured — which is a defect this
  had until the compiled programme disagreed with it.

ponytail: recursion is Python's, so a tail-recursive loop over a very long
list overflows where OCaml would not. `specification.md`, *Differences from
OCaml*, records it, and the fix is rewriting self-recursive tail calls into
a loop.
"""

from __future__ import annotations

from collections import ChainMap
from collections.abc import Callable
from typing import Any

from ocaml import syntax as s
from ocaml.front.parser import parse

from . import runtime
from .runtime import BINARY_OPS, UNARY_OPS, OCamlError, Record, Value, fail

Env = ChainMap[str, Any]


def run(structure: s.Structure, env: Env | None = None) -> Env:
    """Evaluate every item in order. The scope after the last one is returned.

    Each `let` item opens a **new** scope rather than writing into the one
    it was given. A closure made earlier holds the mapping it was made in,
    so a later `let x = 2` shadows `x` for what follows and leaves the
    closure reading the `x` it captured. Updating in place gave the closure
    the new value instead, which OCaml does not, and the compiled programme
    is what disagreed: it got 1 where this got 2.
    """
    scope: Env = env if env is not None else ChainMap({}, dict(runtime.ENV))
    for item in structure.items:
        scope = run_item(item, scope)
    return scope


def run_source(source: str) -> Env:
    return run(parse(source))


def run_item(node: Any, env: Env) -> Env:
    """The scope after this item, which a `let` extends and nothing else does."""
    match node:
        case s.LetItem(recursive=recursive, bindings=bindings):
            return env.new_child(evaluate_bindings(recursive, bindings, env))
        case s.TypeItem() | s.ExnItem():
            # A declaration binds a name for the checker and the resolver.
            # Nothing is created: a constructed value carries its own tag.
            return env
        case s.ExprItem(value=value):
            eval_expr(value, env)
            return env
    raise TypeError(f"no rule for {type(node).__name__}")


# ------------------------------------------------------------------ binding


def evaluate_bindings(
    recursive: bool, bindings: list[s.Binding], env: Env
) -> dict[str, Any]:
    """The names one `let` introduces, with their values.

    `recursive` decides which environment the right-hand sides see, and that
    is the whole difference between the two forms.
    """
    scope: dict[str, Any] = {}
    inner = env.new_child(scope) if recursive else env
    for binding in bindings:
        value = evaluate_binding(binding, inner)
        bind(binding.pattern, value, scope)
    return scope


def evaluate_binding(binding: s.Binding, env: Env) -> Any:
    """`let f x y = e` is a function of two arguments; `let x = e` is `e`."""
    if binding.params:
        return closure(binding.params, binding.value, env)
    return eval_expr(binding.value, env)


def closure(params: list[s.Pattern], body: Any, env: Env) -> Any:
    """One Python callable per parameter, which is what currying means."""
    head, rest = params[0], params[1:]

    def call(argument: Any) -> Any:
        scope: dict[str, Any] = {}
        bind(head, argument, scope)
        inner = env.new_child(scope)
        return closure(rest, body, inner) if rest else eval_expr(body, inner)

    return call


def bind(pattern: s.Pattern, value: Any, into: dict[str, Any]) -> None:
    """Bind through a pattern, or raise `Match_failure`."""
    if not match_pattern(pattern, value, into):
        fail("Match_failure")


def matcher(cases: list[s.Case], env: Env) -> Any:
    """`function | p -> e`: a one-argument function that matches."""
    return lambda argument: eval_cases(argument, cases, env)


def eval_cases(value: Any, cases: list[s.Case], env: Env) -> Any:
    for case in cases:
        scope: dict[str, Any] = {}
        if not match_pattern(case.pattern, value, scope):
            continue
        inner = env.new_child(scope)
        if case.guard is not None and not eval_expr(case.guard, inner):
            continue
        return eval_expr(case.body, inner)
    return fail("Match_failure")


# ----------------------------------------------------------------- patterns


def match_pattern(node: Any, value: Any, into: dict[str, Any]) -> bool:
    """Whether `value` matches, binding into `into` as it goes.

    A failed match may leave names behind; the caller drops the mapping, so
    nothing sees them. That is why `into` is a fresh dict per case.
    """
    match node:
        case s.PWild():
            return True
        case s.PVar(name=name):
            into[name] = value
            return True
        case s.PLit(value=literal):
            return runtime.equal(eval_expr(literal, ChainMap()), value)
        case s.PTuple(items=items):
            return _match_all(items, value, into)
        case s.PList(items=items):
            cells = _cells(value)
            return cells is not None and _match_all(items, cells, into)
        case s.PArray(items=items):
            return isinstance(value, list) and _match_all(items, value, into)
        case s.PConstruct(name=name, args=args):
            if not isinstance(value, Value) or value.tag != name:
                return False
            return _match_all(args, value.args, into)
        case s.PRecord(fields=fields):
            return isinstance(value, Record) and all(
                field.label in value.fields
                and match_pattern(field.pattern, value.fields[field.label], into)
                for field in fields
            )
        case s.POr(alternatives=alternatives):
            return any(match_pattern(alt, value, into) for alt in alternatives)
        case s.PAlias(pattern=pattern, name=name):
            into[name] = value
            return match_pattern(pattern, value, into)
        case s.PConstraint(pattern=pattern):
            return match_pattern(pattern, value, into)
    raise TypeError(f"no rule for {type(node).__name__}")


def _match_all(patterns: list[s.Pattern], values: Any, into: dict[str, Any]) -> bool:
    if len(patterns) != len(values):
        return False
    return all(match_pattern(p, v, into) for p, v in zip(patterns, values, strict=True))


def _cells(value: Any) -> list[Any] | None:
    """An OCaml list as a Python list, or None if it is not one."""
    out: list[Any] = []
    while isinstance(value, Value) and value.tag == "::":
        out.append(value.args[0])
        value = value.args[1]
    return out if isinstance(value, Value) and value.tag == "[]" else None


# -------------------------------------------------------------- expressions


#: Set to watch every evaluation, and left `None` for an ordinary run.
#: `back/stepper.py` is the only thing that sets it, and what it records is
#: what the playground steps through. The cost when nothing is watching is
#: one comparison per node.
watching: Callable[[Any, Env, Callable[[Any, Env], Any]], Any] | None = None


def eval_expr(node: Any, env: Env) -> Any:
    """One expression's value, and the seam the stepper watches through.

    Every sub-expression goes through here, including the recursive calls
    below, so a watcher set on the module sees the whole evaluation without
    anything else in this file knowing it exists.
    """
    if watching is None:
        return _eval_expr(node, env)
    return watching(node, env, _eval_expr)


def _eval_expr(node: Any, env: Env) -> Any:
    match node:
        case s.Int(value=value) | s.Float(value=value) | s.Bool(value=value):
            return value
        case s.Char(value=value) | s.Str(value=value):
            return value
        case s.Unit():
            return None
        case s.Var(name=name):
            return env[name]
        case s.Construct(name=name, args=args):
            return Value(name, tuple(eval_expr(a, env) for a in args))
        case s.Tuple(items=items):
            return tuple(eval_expr(i, env) for i in items)
        case s.ListLit(items=items):
            return runtime.from_python([eval_expr(i, env) for i in items])
        case s.ArrayLit(items=items):
            return [eval_expr(i, env) for i in items]
        case s.Record(fields=fields, base=base):
            made = dict(eval_expr(base, env).fields) if base else {}
            made.update({f.label: eval_expr(f.value, env) for f in fields})
            return Record(made)
        case s.Apply(fn=fn, args=args):
            found = eval_expr(fn, env)
            for argument in args:
                found = found(eval_expr(argument, env))
            return found
        case s.BinOp(op="&&", left=left, right=right):
            return eval_expr(left, env) and eval_expr(right, env)
        case s.BinOp(op="||", left=left, right=right):
            return eval_expr(left, env) or eval_expr(right, env)
        case s.BinOp(op=op, left=left, right=right):
            return BINARY_OPS[op](eval_expr(left, env), eval_expr(right, env))
        case s.UnOp(op=op, value=value):
            return UNARY_OPS[op](eval_expr(value, env))
        case s.If(cond=cond, then=then, otherwise=otherwise):
            if eval_expr(cond, env):
                return eval_expr(then, env)
            return eval_expr(otherwise, env) if otherwise is not None else None
        case s.Seq(items=items):
            found = None
            for item in items:
                found = eval_expr(item, env)
            return found
        case s.LetIn(recursive=recursive, bindings=bindings, body=body):
            scope = evaluate_bindings(recursive, bindings, env)
            return eval_expr(body, env.new_child(scope))
        case s.Fun(params=params, body=body):
            return closure(params, body, env)
        case s.Function(cases=cases):
            return matcher(cases, env)
        case s.Match(scrutinee=scrutinee, cases=cases):
            return eval_cases(eval_expr(scrutinee, env), cases, env)
        case s.Try(body=body, cases=cases):
            return _try(body, cases, env)
        case s.While(cond=cond, body=body):
            while eval_expr(cond, env):
                eval_expr(body, env)
            return None
        case s.For(var=var, start=start, stop=stop, down=down, body=body):
            _for(var, start, stop, down=down, body=body, env=env)
            return None
        case s.GetField(value=value, label=label):
            return eval_expr(value, env).fields[label]
        case s.SetField(value=value, label=label, rhs=rhs):
            eval_expr(value, env).fields[label] = eval_expr(rhs, env)
            return None
        case s.ArrayGet(array=array, index=index):
            return runtime.at(eval_expr(array, env), eval_expr(index, env))
        case s.ArraySet(array=array, index=index, rhs=rhs):
            found, index_at = eval_expr(array, env), eval_expr(index, env)
            runtime.put(found, index_at, eval_expr(rhs, env))
            return None
        case s.StringGet(value=value, index=index):
            return runtime.at(eval_expr(value, env), eval_expr(index, env))
        case s.Constraint(value=value):
            return eval_expr(value, env)
    raise TypeError(f"no rule for {type(node).__name__}")


def _try(body: Any, cases: list[s.Case], env: Env) -> Any:
    try:
        return eval_expr(body, env)
    except OCamlError as raised:
        for case in cases:
            scope: dict[str, Any] = {}
            if not match_pattern(case.pattern, raised.value, scope):
                continue
            inner = env.new_child(scope)
            if case.guard is not None and not eval_expr(case.guard, inner):
                continue
            return eval_expr(case.body, inner)
        raise


def _for(
    var: s.PVar, start: Any, stop: Any, *, down: bool, body: Any, env: Env
) -> None:
    first, last = eval_expr(start, env), eval_expr(stop, env)
    step = -1 if down else 1
    for index in range(first, last + step, step):
        eval_expr(body, env.new_child({var.name: index}))
