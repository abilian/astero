"""Watching a programme run, one step at a time.

Running a programme tells you the answer. It does not tell you how the
answer happened, which is the part a student is stuck on. This records every
evaluation the interpreter performs, so the playground can walk through them
forwards and backwards, showing at each point which piece of source is being
evaluated, what every name in scope holds, and what has been printed so far.

**Why recording rather than pausing.** A debugger that pauses a running
programme can only go forwards: to see the previous step you must start
again. Recording first turns stepping into reading a list, so going back is
subtraction and costs nothing to implement. It works here because these
programmes are small and finish in milliseconds. `LIMIT` is what keeps a
programme that does not finish from filling the browser's memory.

**How it hooks in.** `interpret.eval_expr` is the one place every expression
goes through, and it calls `interpret.watching` when that is set. An
ordinary run pays one `is None` test per node for this, and nothing else.

Three things are recorded that a plain stack trace would not give you:

* **The store, apart from the environment.** `x` and `y` can be two names
  for one `ref` cell, and assigning through either changes what both see.
  Showing the cells separately, with the names that point at them, is what
  makes aliasing visible instead of surprising.
* **The scope, derived rather than guessed.** Which block a node sits in
  comes from `SCOPES` in `middle/grammar.py`, the same declaration the Names
  view is built from, so the stepper and that view cannot disagree.
* **The output so far**, as a length rather than a copy, so scrubbing back
  through a thousand steps does not hold a thousand copies of the output.
"""

from __future__ import annotations

import contextlib
import io
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from astero.scopes import evaluated_outside
from ocaml import syntax as s
from ocaml.back import interpret, runtime
from ocaml.back.compile import compile_source
from ocaml.front.parser import parse
from ocaml.middle import analyze
from ocaml.middle.grammar import SCOPES

#: How many steps to keep. A programme that loops forever still returns a
#: trace, marked `truncated`, rather than hanging the page. Five thousand is
#: about a second of recording and comfortably more than a student reads.
LIMIT = 5000

#: How deep to render a value before giving up. Guards against a `ref` that
#: points at itself, which is a thing a student writes on purpose.
DEPTH = 6


@dataclass
class Step:
    """One evaluation, recorded on the way in and again on the way out."""

    #: `enter` before the sub-expression is evaluated, `value` after.
    kind: str
    #: Where in the source, for the editor to mark.
    span: tuple[int, int] | None
    #: How deep in sub-expressions. `call` is the one stepping uses.
    depth: int
    #: How many function calls are on the stack. Step over, in and out are
    #: defined against this rather than `depth`, because every operand of an
    #: expression is deeper and none of them is a call.
    call: int
    #: The function whose body this is, innermost last.
    stack: tuple[str, ...]
    #: The names in scope and what they hold, nearest scope first.
    env: tuple[tuple[str, str], ...]
    #: The mutable cells, and which names reach them.
    store: tuple[tuple[str, str], ...]
    #: The scope this node sits in, from the same declaration as the Names
    #: view: `top ▸ binding ▸ case`.
    scope: str
    #: What the sub-expression evaluated to. `enter` steps do not know yet.
    value: str | None = None
    #: How much had been printed when this step happened.
    printed: int = 0


@dataclass
class Trace:
    """Everything a stepping session needs, recorded up front."""

    steps: list[Step] = field(default_factory=list)
    #: Everything the programme printed, in full. A step shows the prefix of
    #: it that existed at the time.
    output: str = ""
    #: Whether `LIMIT` cut the recording short.
    truncated: bool = False
    #: What stopped it, if anything did. A programme that raises still has a
    #: trace, and the last step is where it went wrong.
    error: str | None = None


# ----------------------------------------------------------------- values


def show(value: Any, depth: int = 0) -> str:
    """An OCaml value, written the way OCaml writes it.

    Not a debugging `repr`: `[3; 1; 4]` rather than a chain of cons cells,
    and `{ contents = 0 }` for a `ref`, because that is what a `ref` is.

    The one thing it cannot do is tell a `char` from a one-letter `string`,
    since the runtime represents both as a Python string. It prints the
    string form; `compiler/running.md` in the docs is where that representation is
    argued.
    """
    if depth > DEPTH:
        return "…"
    match value:
        case bool():
            return "true" if value else "false"
        case float():
            return runtime.show_float(value)
        case int():
            return str(value)
        case str():
            return f'"{value}"'
        case None:
            return "()"
        case list():
            return _joined("[|", value, "|]", depth)
        case tuple():
            return "(" + ", ".join(show(item, depth + 1) for item in value) + ")"
        case runtime.Record() | runtime.Value():
            return _built(value, depth)
    # What is left is a function, or a `Stack.t` or a `Hashtbl.t`, which
    # the OCaml toplevel prints as an abstract type.
    return "<fun>" if callable(value) else "<abstr>"


def _joined(open_: str, items: Any, close: str, depth: int) -> str:
    """`[|1; 2|]` and `[1; 2]`, which differ only in their brackets."""
    return open_ + "; ".join(show(item, depth + 1) for item in items) + close


def _built(value: Any, depth: int) -> str:
    """A record or a constructed value, which is where the shapes are.

    A list is a chain of `::` cells rather than a class of its own, so it
    comes back out as a list here rather than as the cells it is made of.
    """
    if isinstance(value, runtime.Record):
        pairs = value.fields.items()
        inside = "; ".join(f"{k} = {show(v, depth + 1)}" for k, v in pairs)
        return "{ " + inside + " }"
    if value.tag in {"[]", "::"}:
        return _joined("[", _items(value), "]", depth)
    if not value.args:
        return value.tag
    inside = ", ".join(show(arg, depth + 1) for arg in value.args)
    return f"{value.tag} ({inside})" if len(value.args) > 1 else f"{value.tag} {inside}"


def _items(cell: Any) -> list[Any]:
    """A cons chain as a Python list, stopping if it is circular."""
    out: list[Any] = []
    seen: set[int] = set()
    while isinstance(cell, runtime.Value) and cell.tag == "::" and id(cell) not in seen:
        seen.add(id(cell))
        out.append(cell.args[0])
        cell = cell.args[1]
    return out


# ------------------------------------------------------------------ scopes


def scope_paths(tree: s.Structure) -> dict[int, str]:
    """Every node's enclosing scope, as a readable path.

    The routing is `analyze._resolve`'s, and for the same reason: a scope
    layer names the fields evaluated *inside* the scope its production
    opens, so a `match` arm's pattern is in the arm and a `let`'s value is
    not in the `let`. Nothing here lists a node kind; `SCOPES` does.
    """
    found: dict[int, str] = {}
    # what a scope evaluates outside itself, with the path it is evaluated at
    around: dict[int, tuple[str, ...]] = {}

    def walk(node: Any, path: tuple[str, ...]) -> None:
        path = around.pop(id(node), path)
        found[id(node)] = " ▸ ".join(path)
        layers = [
            layer
            for layer in SCOPES.get(type(node).__name__, ())
            if layer.applies(node)
        ]
        for layer in layers:
            for _, _, child in evaluated_outside(node, layer, SCOPES):
                around[id(child)] = path
        inside = analyze.opened_fields(node)
        deeper = (*path, *(layer.kind for layer in layers)) if layers else path
        for name, child in analyze.fields_of(node):
            walk(child, deeper if name in inside else path)

    walk(tree, ("top",))
    return found


# ------------------------------------------------------------------ the run


def _levels(env: Any) -> list[Any]:
    """The scopes a programme made, innermost first, without the prelude.

    The prelude is the outermost map and holds 131 names nobody wants to
    scroll past. It is found by what it contains rather than by its
    position, because an environment is sometimes one plain mapping and
    dropping the last of those would drop the only one there is.
    """
    levels = list(getattr(env, "maps", [env]))
    if levels and levels[-1].keys() >= runtime.ENV.keys():
        levels = levels[:-1]
    return levels


def _locals(env: Any) -> tuple[tuple[str, str], ...]:
    """The names a programme bound, nearest scope first.

    Functions go last. A programme of twenty definitions has twenty names
    holding `<fun>`, and none of them is what you are stepping through; the
    two or three that hold data are.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for level in _levels(env):
        for name, value in level.items():
            if name not in seen:
                seen.add(name)
                out.append((name, show(value)))
    return tuple(sorted(out, key=lambda pair: pair[1] == "<fun>"))


def _store(env: Any) -> tuple[tuple[str, str], ...]:
    """Every mutable cell the programme can reach, and what is in it.

    A `ref` and an array are the two things whose contents can change under
    a name that did not change, so they are worth showing apart from the
    environment. Two names for one cell appear once, labelled with both.
    """
    cells: dict[int, tuple[list[str], Any]] = {}

    def visit(name: str, value: Any, depth: int) -> None:
        if depth > DEPTH:
            return
        if isinstance(value, runtime.Record | list):
            here = cells.setdefault(id(value), ([], value))
            if name and name not in here[0]:
                here[0].append(name)
            held = value.fields.values() if isinstance(value, runtime.Record) else value
            for item in held:
                visit("", item, depth + 1)
        elif isinstance(value, runtime.Value):
            for item in value.args:
                visit("", item, depth + 1)

    for level in _levels(env):
        for name, value in level.items():
            visit(name, value, 0)
    return tuple(
        (", ".join(names) or f"#{n}", show(value))
        for n, (names, value) in enumerate(cells.values(), start=1)
    )


def record(source: str, limit: int = LIMIT) -> Trace:
    """Run the programme, keeping every step.

    The interpreter is the back end that gets watched, because it is the one
    whose steps are the language's own. The compiled Python takes different
    steps to reach the same answer, which is what `compiled_output` below is
    for.
    """
    trace = Trace()
    tree = parse(source)
    scopes = scope_paths(tree)
    sink = io.StringIO()
    stack: list[str] = ["top"]
    depth = 0

    def snapshot(node: Any, env: Any, kind: str, value: str | None) -> None:
        trace.steps.append(
            Step(
                kind=kind,
                span=node.span,
                depth=depth,
                call=len(stack),
                stack=tuple(stack),
                env=_locals(env),
                store=_store(env),
                scope=scopes.get(id(node), ""),
                value=value,
                printed=sink.tell(),
            )
        )

    def watch(node: Any, env: Any, evaluate: Any) -> Any:
        nonlocal depth
        if len(trace.steps) >= limit:
            trace.truncated = True
            return evaluate(node, env)
        snapshot(node, env, "enter", None)
        called = isinstance(node, s.Apply)
        if called:
            stack.append(_called(node, source))
        depth += 1
        try:
            value = evaluate(node, env)
        finally:
            depth -= 1
            if called:
                stack.pop()
        snapshot(node, env, "value", show(value))
        return value

    interpret.watching = watch
    try:
        with contextlib.redirect_stdout(sink):
            interpret.run(tree)
    except Exception as bad:
        trace.error = f"{type(bad).__name__}: {bad}"
    finally:
        interpret.watching = None
    trace.output = sink.getvalue()
    return trace


# ------------------------------------------------------- the other back end


@dataclass
class PyStep:
    """One line of the emitted Python, as it ran."""

    line: int
    #: The line of emitted source, for the Python pane to mark.
    text: str
    #: The Python frame's own names. A compiled binding is `x_2`, not `x`,
    #: which is the renaming `back/compile.py` does and worth seeing.
    names: tuple[tuple[str, str], ...]
    printed: int


def record_compiled(source: str, limit: int = LIMIT) -> tuple[list[PyStep], str]:
    """The same programme, stepped through the Python the compiler emitted.

    The two back ends do not take the same steps and there is no honest way
    to pretend they do: one walks a tree and the other runs a `def`. What
    they share is `runtime.py`, so they print the same characters at the
    same points, and that is what the playground lines them up on. A step on
    one side is matched to the step on the other that had printed as much.

    Approximate between prints, exact at them, and the place where it stops
    being approximate is the place that matters: the first character where
    the two disagree is a defect in one of them.
    """
    steps: list[PyStep] = []
    emitted = compile_source(source)
    lines = emitted.splitlines()
    code = compile(emitted, FILE, "exec")
    sink = io.StringIO()

    def tracer(frame: Any, event: str, _arg: Any) -> Any:
        if event == "line" and frame.f_code.co_filename == FILE:
            if len(steps) >= limit:
                sys.settrace(None)
                return None
            steps.append(
                PyStep(
                    line=frame.f_lineno,
                    text=_line(lines, frame.f_lineno),
                    names=tuple(
                        (name, show(value))
                        for name, value in frame.f_locals.items()
                        if not _plumbing(name, value)
                    ),
                    printed=sink.tell(),
                )
            )
        return tracer

    scope: dict[str, Any] = {"__name__": "__main__"}
    sys.settrace(tracer)
    # A programme that raises still produced steps, and those are where it
    # went wrong. The interpreter's side keeps the message; this side is
    # only asked how far the output got.
    with contextlib.suppress(Exception):
        try:
            with contextlib.redirect_stdout(sink):
                exec(code, scope)
        finally:
            sys.settrace(None)
    return steps, sink.getvalue()


#: The filename the emitted module is compiled under, so the tracer can tell
#: its frames from every other frame Python runs.
FILE = "<caml-prépa>"


def _line(lines: list[str], number: int) -> str:
    """One line of the emitted source, or nothing past the end of it."""
    return lines[number - 1] if 1 <= number <= len(lines) else ""


def _plumbing(name: str, value: Any) -> bool:
    """Whether a Python name is the emitter's rather than the programme's.

    The emitted module opens by importing the runtime and unpacking every
    prelude name out of it, so a module-level frame holds 131 names nobody
    wrote. Compared by identity rather than by name, so a programme that
    binds `ref` to something of its own still shows.
    """
    return (
        name.startswith("__")
        or isinstance(value, ModuleType)
        or runtime.ENV.get(name) is value
    )


def _called(node: s.Apply, source: str) -> str:
    """What an application calls, for the stack. The text, where there is
    any: a call is `f x`, and `f` is the part worth naming."""
    fn = node.fn
    if fn.span is not None:
        return source[fn.span[0] : fn.span[1]]
    return getattr(fn, "name", "<fun>")
