"""The values a running programme is made of, and the library it can call.

Both back ends use this, which is the decision the whole back end rests on.
The interpreter walks the tree and calls these functions; the compiler
emits Python that calls the same ones. So the second back end cost an
emitter and nothing else: no second value representation, no second
`List.fold_left`.

How each OCaml value is represented in Python:

| OCaml | here |
| --- | --- |
| `int`, `float`, `bool`, `string` | the Python one |
| `char` | a one-character `str` |
| `unit` | `None` |
| a tuple | a Python tuple |
| `'a list` | `Value("::", (head, tail))` cells, ending at `Value("[]")` |
| `'a array` | a Python `list` |
| a record, and so `'a ref` too | `Record(fields)` |
| `Some x`, `Leaf`, an exception | `Value(tag, args)` |
| a function | a Python callable of one argument |

Lists are cons cells rather than Python lists because `::` has to be O(1)
and because sharing is visible: `x :: l` and `l` are the same tail. `ref`
gets no class of its own because in OCaml it is not primitive — it is a
record with one mutable field, and `!`, `:=`, `incr` and `decr` are
ordinary functions over it.

**A function value is a Python callable of one argument.** OCaml functions
are curried, so `add 1 2` is really `(add 1) 2`, and currying them here
makes partial application fall out with no arity bookkeeping. A compiler
*does* want arity, to emit `f(a, b)` rather than `f(a)(b)`, and it reads it
off `Binding.params` in the tree where the source put it.

Which is why every higher-order function below calls through `apply` rather
than `f(a)(b)`: the interpreter's closures take one argument at a time and
the compiler's `def`s take all of them, and a runtime shared by both may
not assume either.

Two tables are the interface. `ENV` is every value a programme may use
without defining it, and `middle/prelude.py` gives each of those names a
type. `BINARY_OPS` and `UNARY_OPS` are the operators, used twice: the
interpreter dispatches on them, and `ENV` exposes their curried forms,
which is what makes `List.fold_left ( + ) 0` work.
"""

from __future__ import annotations

import functools
import math
import operator
import random
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from ocaml.front.formats import Conversion, pieces

#: OCaml's `int` is 63-bit and wraps; this one does not. `lsr` is the one
#: operator that cannot ignore the difference, since a logical shift needs a
#: width. `specification.md`, *Differences from OCaml*, records it.
WORD = (1 << 63) - 1

#: OCaml runs a loop written as tail recursion in constant stack, and this
#: runtime cannot: each call costs several Python frames, so `explore (mask
#: + 1)` over 512 masks overran Python's default of 1000.
#: ponytail: a larger fixed limit, not tail calls; a trampoline in both back
#: ends is the fix when a corpus programme needs more.
DEPTH = 10_000
sys.setrecursionlimit(max(sys.getrecursionlimit(), DEPTH))


@dataclass(frozen=True)
class Value:
    """A constructed value: `Some 1`, `Leaf`, and the list cells.

    `::` and `[]` are constructors of `'a list` in OCaml and get no class of
    their own here either, so a cons cell is one of these and pattern
    matching over lists needs no case.
    """

    tag: str
    args: tuple[Any, ...] = ()


@dataclass
class Record:
    """A record, and therefore also a `ref`.

    `'a ref = { mutable contents : 'a }`, so `ref` is not primitive in OCaml
    and is not primitive here.

    ponytail: one class with a dict, not a generated class per declared type.
    Per-type classes with `__slots__` are the upgrade, when the compiler is
    measured.
    """

    fields: dict[str, Any]


@dataclass(eq=False)
class Stack:
    """A `'a Stack.t`: mutable, compared by identity, top at the end."""

    items: list[Any]


@dataclass(eq=False)
class Hashtbl:
    """A `('a, 'b) Hashtbl.t`, keyed by structure as OCaml's is.

    Each key holds a list of bindings, newest last, because `Hashtbl.add`
    shadows where `Hashtbl.replace` overwrites and `Hashtbl.remove` uncovers
    the binding underneath.
    """

    table: dict[Any, list[Any]]


class OCamlError(Exception):
    """A raised OCaml exception, carrying the constructed value."""

    def __init__(self, value: Value) -> None:
        super().__init__(value.tag)
        self.value = value


NIL = Value("[]")


def fail(tag: str, *args: Any) -> Any:
    raise OCamlError(Value(tag, args))


def cons(head: Any, tail: Any) -> Value:
    return Value("::", (head, tail))


def to_python(value: Any) -> list[Any]:
    """An OCaml list as a Python list."""
    out = []
    while value.tag == "::":
        out.append(value.args[0])
        value = value.args[1]
    return out


def from_python(items: list[Any]) -> Value:
    out = NIL
    for item in reversed(items):
        out = cons(item, out)
    return out


def curry(arity: int) -> Callable[[Callable[..., Any]], Any]:
    """A Python function of `arity` arguments, as an OCaml function value."""

    def wrap(fn: Callable[..., Any]) -> Any:
        def collect(got: tuple[Any, ...]) -> Any:
            def step(x: Any) -> Any:
                args = (*got, x)
                return fn(*args) if len(args) == arity else collect(args)

            return step

        return collect(())

    return wrap


# ---------------------------------------------------------------- comparison


def equal(left: Any, right: Any) -> bool:
    """Structural equality, which is what `=` means.

    Comparing two functions raises, as OCaml's does: a closure has no
    structure, and Python's `==` on two callables would quietly answer.
    """
    if callable(left) or callable(right):
        fail("Invalid_argument", "compare: functional value")
    match left, right:
        case Value(tag=a, args=xs), Value(tag=b, args=ys):
            return a == b and len(xs) == len(ys) and all(map(equal, xs, ys))
        case Record(fields=xs), Record(fields=ys):
            if xs.keys() != ys.keys():
                return False
            return all(equal(v, ys[k]) for k, v in xs.items())
        case (list() | tuple()) as xs, (list() | tuple()) as ys:
            return len(xs) == len(ys) and all(map(equal, xs, ys))
    return bool(left == right)


def ordered(value: Any) -> Any:
    """A value `<` may be applied to.

    The subset restricts ordering to the scalars. OCaml orders any two values
    of the same type, which needs a structural traversal and a rule for
    cyclic values; `specification.md`, *Differences from OCaml*, records the choice.
    """
    if isinstance(value, (int, float, str)):
        return value
    return fail("Invalid_argument", "compare: unsupported")


def compare(left: Any, right: Any) -> int:
    a, b = ordered(left), ordered(right)
    return (a > b) - (a < b)


# ---------------------------------------------------------------- arithmetic


def divide(a: int, b: int) -> int:
    """OCaml truncates towards zero; Python floors. `(-7) / 2` is -3, not -4."""
    if b == 0:
        fail("Division_by_zero")
    quotient = abs(a) // abs(b)
    return quotient if (a >= 0) == (b >= 0) else -quotient


def modulo(a: int, b: int) -> int:
    """The remainder takes the sign of the dividend, as OCaml's does."""
    if b == 0:
        fail("Division_by_zero")
    return a - divide(a, b) * b


def float_divide(a: float, b: float) -> float:
    """`1.0 /. 0.0` is `infinity` in OCaml; Python raises.

    The zero tests are truth tests rather than comparisons, which is exact
    for a float and says what is meant: this asks whether the divisor is
    zero, not whether two computed floats happen to agree.
    """
    if b:
        return a / b
    if a and not math.isnan(a):
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return math.nan


def append(left: Value, right: Value) -> Value:
    return from_python(to_python(left) + to_python(right))


#: Every binary operator, once. The interpreter dispatches on this table and
#: `ENV` exposes the curried forms, so `( + )` and `a + b` cannot disagree.
def logical_shift(a: int, b: int) -> int:
    """`lsr` needs a width, and OCaml's is 63 bits. See `WORD`."""
    return (a & WORD) >> b


def assign(cell: Record, value: Any) -> None:
    cell.fields["contents"] = value


#: Every binary operator, once. `+`, `+.` and `^` are all `operator.add`,
#: which is the difference between the two languages in one line: OCaml
#: spells the operand type and Python dispatches on it.
BINARY_OPS: dict[str, Callable[[Any, Any], Any]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": divide,
    "mod": modulo,
    "+.": operator.add,
    "-.": operator.sub,
    "*.": operator.mul,
    "/.": float_divide,
    "**": operator.pow,
    "land": operator.and_,
    "lor": operator.or_,
    "lxor": operator.xor,
    "lsl": operator.lshift,
    "lsr": logical_shift,
    "asr": operator.rshift,
    "^": operator.add,
    "@": append,
    "=": equal,
    "<>": lambda a, b: not equal(a, b),
    "<": lambda a, b: compare(a, b) < 0,
    "<=": lambda a, b: compare(a, b) <= 0,
    ">": lambda a, b: compare(a, b) > 0,
    ">=": lambda a, b: compare(a, b) >= 0,
    "&&": lambda a, b: a and b,
    "||": lambda a, b: a or b,
    ":=": assign,
}

UNARY_OPS: dict[str, Callable[[Any], Any]] = {
    "-": operator.neg,
    "-.": operator.neg,
    "!": lambda cell: cell.fields["contents"],
}


# ----------------------------------------------------------------- printing


def at(sequence: Any, index: int) -> Any:
    """`a.(i)` and `s.[i]`, bounds-checked.

    Python would take a negative index from the other end and OCaml raises,
    so neither back end may use `[]` directly.
    """
    if not 0 <= index < len(sequence):
        fail("Invalid_argument", "index out of bounds")
    return sequence[index]


def put(array: list[Any], index: int, value: Any) -> None:
    """`a.(i) <- v`, bounds-checked."""
    if not 0 <= index < len(array):
        fail("Invalid_argument", "index out of bounds")
    array[index] = value


def arity(fn: Any) -> int:
    """How many arguments this function value takes at once.

    The compiler emits an OCaml function of `n` parameters as a Python
    function of `n`, and the prelude's are curried to one. `apply` needs to
    know which it has.
    """
    if isinstance(fn, functools.partial):
        return arity(fn.func) - len(fn.args)
    code = getattr(fn, "__code__", None)
    return code.co_argcount if code is not None else 1


def apply(fn: Any, *args: Any) -> Any:
    """Application that does not care how the callee was spelled.

    A saturated call the compiler recognises is emitted as `f(a, b)`; this
    is what the other calls go through, and it is where partial and excess
    application are handled.

    **Every higher-order function below calls through here**, and not
    `f(a)(b)`. The interpreter's closures take one argument at a time and
    the compiler's `def`s take all of them, so a runtime shared by both may
    not assume either. `List.fold_left` written the direct way ran under the
    interpreter and failed under the compiler on the first corpus programme
    that folded a two-parameter function.
    """
    index = 0
    while index < len(args):
        want = arity(fn)
        taken = args[index : index + want]
        index += len(taken)
        if len(taken) < want:
            return functools.partial(fn, *taken)
        fn = fn(*taken)
    return fn


def show_float(value: float) -> str:
    """`string_of_float`, which prints `3.` rather than `3.0`."""
    if math.isinf(value):
        return "infinity" if value > 0 else "neg_infinity"
    if math.isnan(value):
        return "nan"
    text = f"{value:.12g}"
    return text if any(c in text for c in ".e") else f"{text}."


def write(text: str) -> None:
    sys.stdout.write(text)


# ------------------------------------------------------------- the modules


def _iter(fn: Any, items: Any) -> None:
    for item in items:
        fn(item)


def _iteri(fn: Any, items: Any) -> None:
    for index, item in enumerate(items):
        apply(fn, index, item)


def _nth(items: Value, index: int) -> Any:
    if index < 0:
        fail("Invalid_argument", "List.nth")
    cells = to_python(items)
    return cells[index] if index < len(cells) else fail("Failure", "nth")


def _assoc(key: Any, items: Value) -> Any:
    for pair in to_python(items):
        if equal(pair[0], key):
            return pair[1]
    return fail("Not_found")


def _sorted(compare_with: Any, items: list[Any]) -> list[Any]:
    ordering = functools.cmp_to_key(lambda a, b: apply(compare_with, a, b))
    return sorted(items, key=ordering)


def _array_sort(compare_with: Any, array: list[Any]) -> None:
    array[:] = _sorted(compare_with, array)


def _array_blit(src: list[Any], i: int, dst: list[Any], j: int, n: int) -> None:
    dst[j : j + n] = src[i : i + n]


def _array_fill(array: list[Any], at: int, count: int, value: Any) -> None:
    array[at : at + count] = [value] * count


def _bump(cell: Record, step: int) -> None:
    cell.fields["contents"] += step


def _sub_string(text: str, start: int, length: int) -> str:
    if start < 0 or length < 0 or start + length > len(text):
        fail("Invalid_argument", "String.sub")
    return text[start : start + length]


def _index(text: str, char: str) -> int:
    at = text.find(char)
    return at if at >= 0 else fail("Not_found")


def _line() -> str:
    """One line of input without its newline, or `End_of_file` after the last."""
    line = sys.stdin.readline()
    return line.removesuffix("\n") if line else fail("End_of_file")


def _escaped(char: str) -> str:
    """`Char.escaped`: OCaml's escapes, and `\\ddd` for the rest."""
    special = {
        "\\": "\\\\",
        "'": "\\'",
        "\n": "\\n",
        "\t": "\\t",
        "\r": "\\r",
        "\b": "\\b",
    }
    if char in special:
        return special[char]
    return char if " " <= char <= "~" else f"\\{ord(char):03d}"


def _find_first(predicate: Any, items: Value) -> Any:
    for item in to_python(items):
        if predicate(item):
            return item
    return fail("Not_found")


def _filter_map(fn: Any, items: Value) -> Value:
    found = (fn(x) for x in to_python(items))
    return from_python([option.args[0] for option in found if option.tag == "Some"])


LIST_MODULE: dict[str, Any] = {
    "length": lambda items: len(to_python(items)),
    "hd": lambda items: items.args[0] if items.tag == "::" else fail("Failure", "hd"),
    "tl": lambda items: items.args[1] if items.tag == "::" else fail("Failure", "tl"),
    "nth": curry(2)(_nth),
    "rev": lambda items: from_python(list(reversed(to_python(items)))),
    "append": curry(2)(append),
    "concat": lambda ls: from_python([
        x for sub in to_python(ls) for x in to_python(sub)
    ]),
    "map": curry(2)(lambda f, items: from_python([f(x) for x in to_python(items)])),
    "rev_map": curry(2)(
        lambda f, items: from_python([f(x) for x in reversed(to_python(items))])
    ),
    "mapi": curry(2)(
        lambda f, items: from_python([
            apply(f, i, x) for i, x in enumerate(to_python(items))
        ])
    ),
    "iter": curry(2)(lambda f, items: _iter(f, to_python(items))),
    "iteri": curry(2)(lambda f, items: _iteri(f, to_python(items))),
    "fold_left": curry(3)(
        lambda f, acc, items: functools.reduce(
            lambda a, x: apply(f, a, x), to_python(items), acc
        )
    ),
    "fold_right": curry(3)(
        lambda f, items, acc: functools.reduce(
            lambda a, x: apply(f, x, a), reversed(to_python(items)), acc
        )
    ),
    "filter": curry(2)(
        lambda p, items: from_python([x for x in to_python(items) if p(x)])
    ),
    "exists": curry(2)(lambda p, items: any(p(x) for x in to_python(items))),
    "find": curry(2)(_find_first),
    "filter_map": curry(2)(_filter_map),
    "for_all": curry(2)(lambda p, items: all(p(x) for x in to_python(items))),
    "mem": curry(2)(lambda x, items: any(equal(x, y) for y in to_python(items))),
    "assoc": curry(2)(_assoc),
    "split": lambda items: (
        tuple(from_python(list(side)) for side in zip(*to_python(items), strict=True))
        if to_python(items)
        else (NIL, NIL)
    ),
    "combine": curry(2)(
        lambda a, b: from_python(list(zip(to_python(a), to_python(b), strict=True)))
    ),
    "sort": curry(2)(lambda c, items: from_python(_sorted(c, to_python(items)))),
    "init": curry(2)(lambda n, f: from_python([f(i) for i in range(n)])),
}

ARRAY_MODULE: dict[str, Any] = {
    "length": len,
    "make": curry(2)(lambda n, x: [x] * n),
    "init": curry(2)(lambda n, f: [f(i) for i in range(n)]),
    "make_matrix": curry(3)(lambda r, c, x: [[x] * c for _ in range(r)]),
    "get": curry(2)(
        lambda a, i: (
            a[i] if 0 <= i < len(a) else fail("Invalid_argument", "index out of bounds")
        )
    ),
    "set": curry(3)(put),
    "copy": list,
    "sub": curry(3)(lambda a, start, length: a[start : start + length]),
    "append": curry(2)(operator.add),
    "of_list": to_python,
    "to_list": from_python,
    "iter": curry(2)(_iter),
    "iteri": curry(2)(_iteri),
    "map": curry(2)(lambda f, a: [f(x) for x in a]),
    "fold_left": curry(3)(
        lambda f, acc, a: functools.reduce(lambda x, y: apply(f, x, y), a, acc)
    ),
    "sort": curry(2)(_array_sort),
    "blit": curry(5)(_array_blit),
    "fill": curry(4)(_array_fill),
}

STRING_MODULE: dict[str, Any] = {
    "length": len,
    "get": curry(2)(
        lambda s, i: (
            s[i] if 0 <= i < len(s) else fail("Invalid_argument", "index out of bounds")
        )
    ),
    "sub": curry(3)(_sub_string),
    "concat": curry(2)(lambda sep, items: sep.join(to_python(items))),
    "make": curry(2)(lambda n, c: c * n),
    "init": curry(2)(lambda n, f: "".join(f(i) for i in range(n))),
    "index": curry(2)(_index),
    # `operator.contains(seq, item)` is `item in seq`, which is the order
    # `String.contains s c` takes its arguments in.
    "contains": curry(2)(operator.contains),
    "uppercase_ascii": str.upper,
    "lowercase_ascii": str.lower,
    "split_on_char": curry(2)(lambda c, s: from_python(s.split(c))),
    "compare": curry(2)(compare),
}

CHAR_MODULE: dict[str, Any] = {
    "code": ord,
    "chr": chr,
    "escaped": _escaped,
    "lowercase_ascii": str.lower,
    "uppercase_ascii": str.upper,
}

FLOAT_MODULE: dict[str, Any] = {
    "pi": math.pi,
    "exp": math.exp,
    "cos": math.cos,
    "sin": math.sin,
    "tan": math.tan,
}

#: `Sys.argv.(0)` is the programme's name, and no arguments follow it: the
#: corpus runs every programme bare, as `ocaml file.ml` would.
SYS_MODULE: dict[str, Any] = {"argv": ["caml-prépa"]}


def _frozen(value: Any) -> Any:
    """A hashable stand-in for `value` that is equal where OCaml's `=` is."""
    match value:
        case Value(tag=tag, args=args):
            return (tag, tuple(_frozen(a) for a in args))
        case Record(fields=fields):
            return tuple((k, _frozen(v)) for k, v in fields.items())
        case list() | tuple():
            return tuple(_frozen(item) for item in value)
    return value


def _bindings(table: Hashtbl, key: Any) -> list[Any]:
    return table.table.setdefault(_frozen(key), [])


def _find(table: Hashtbl, key: Any) -> Any:
    found = table.table.get(_frozen(key))
    return found[-1] if found else fail("Not_found")


def _replace(table: Hashtbl, key: Any, value: Any) -> None:
    bindings = _bindings(table, key)
    if bindings:
        bindings[-1] = value
    else:
        bindings.append(value)


def _remove(table: Hashtbl, key: Any) -> None:
    bindings = table.table.get(_frozen(key))
    if bindings:
        bindings.pop()


def _pop(stack: Stack) -> Any:
    return stack.items.pop() if stack.items else fail("Stack.Empty")


def _render(piece: str | Conversion, arguments: Iterator[Any]) -> str:
    if isinstance(piece, str):
        return piece
    value = next(arguments)
    spec = f"%{piece.flags}{piece.width}"
    match piece.letter:
        case "F":
            return show_float(value)
        case "b" | "B":
            return (spec + "s") % ("true" if value else "false")
        case "c":
            return (spec + "s") % value
        case "u" | "i":
            return (spec + "d") % value
    precision = "" if piece.precision is None else f".{piece.precision}"
    return (spec + precision + piece.letter) % value


def _formatted(fmt: str, then: Callable[[str], Any]) -> Any:
    """`Printf.printf fmt`: a function of as many arguments as `fmt` takes.

    With none, it prints at once, which is why `Printf.printf "\\n"` needs
    no `()` after it.
    """
    parts = pieces(fmt)
    wanted = len([p for p in parts if not isinstance(p, str)])

    def render(*arguments: Any) -> Any:
        given = iter(arguments)
        return then("".join(_render(piece, given) for piece in parts))

    return curry(wanted)(render) if wanted else render()


#: Python's generator, not OCaml's, so a seeded run draws other numbers than
#: `ocaml` would. Only a programme whose output does not depend on the draws
#: belongs in the corpus: `quickselect.ml` picks a random pivot and prints
#: the same element whichever it picks.
def _seed(value: int) -> None:
    """`Random.init`. `random.seed` itself takes a second, optional argument,
    and `arity` would count it."""
    random.seed(value)


RANDOM_MODULE: dict[str, Any] = {
    "int": lambda bound: (
        random.randrange(bound) if bound > 0 else fail("Invalid_argument", "Random.int")
    ),
    "self_init": lambda _unit: random.seed(),
    "init": _seed,
}

PRINTF_MODULE: dict[str, Any] = {
    "printf": lambda fmt: _formatted(fmt, write),
    "sprintf": lambda fmt: _formatted(fmt, str),
}

STACK_MODULE: dict[str, Any] = {
    "create": lambda _unit: Stack([]),
    "push": curry(2)(lambda x, stack: stack.items.append(x)),
    "pop": _pop,
    "top": lambda stack: stack.items[-1] if stack.items else fail("Stack.Empty"),
    "is_empty": lambda stack: not stack.items,
    "length": lambda stack: len(stack.items),
}

HASHTBL_MODULE: dict[str, Any] = {
    "create": lambda _size: Hashtbl({}),
    "add": curry(3)(lambda table, key, value: _bindings(table, key).append(value)),
    "replace": curry(3)(_replace),
    "remove": curry(2)(_remove),
    "find": curry(2)(_find),
    "find_opt": curry(2)(
        lambda table, key: (
            Value("Some", (found[-1],))
            if (found := table.table.get(_frozen(key)))
            else Value("None")
        )
    ),
    "mem": curry(2)(lambda table, key: bool(table.table.get(_frozen(key)))),
    "length": lambda table: sum(len(b) for b in table.table.values()),
}


def _int_of_string(text: str) -> int:
    try:
        return int(text.replace("_", ""), 0)
    except ValueError:
        return fail("Failure", "int_of_string")


def _float_of_string(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return fail("Failure", "float_of_string")


BUILTINS: dict[str, Any] = {
    "not": operator.not_,
    "ref": lambda x: Record({"contents": x}),
    "incr": lambda cell: _bump(cell, 1),
    "decr": lambda cell: _bump(cell, -1),
    # `ignore e` is how a prépa programme discards a value the surrounding
    # expression must not carry: `if p then ignore (depile s)`.
    "ignore": lambda _value: None,
    "fst": operator.itemgetter(0),
    "snd": operator.itemgetter(1),
    "compare": curry(2)(compare),
    "min": curry(2)(lambda a, b: a if compare(a, b) <= 0 else b),
    "max": curry(2)(lambda a, b: a if compare(a, b) >= 0 else b),
    "abs": abs,
    "succ": lambda n: n + 1,
    "pred": lambda n: n - 1,
    "raise": lambda value: (_ for _ in ()).throw(OCamlError(value)),
    "failwith": lambda text: fail("Failure", text),
    "invalid_arg": lambda text: fail("Invalid_argument", text),
    "print_int": lambda n: write(str(n)),
    "print_float": lambda x: write(show_float(x)),
    "print_char": write,
    "print_string": write,
    "print_endline": lambda s: write(s + "\n"),
    "print_newline": lambda _unit: write("\n"),
    "read_int": lambda _unit: _int_of_string(_line().strip()),
    "read_float": lambda _unit: _float_of_string(_line().strip()),
    "read_line": lambda _unit: _line(),
    "string_of_int": str,
    "int_of_string": _int_of_string,
    "string_of_float": show_float,
    "float_of_string": _float_of_string,
    "string_of_bool": lambda b: "true" if b else "false",
    "bool_of_string": lambda s: s == "true",
    "float_of_int": float,
    "int_of_float": int,
    "char_of_int": chr,
    "int_of_char": ord,
    "truncate": int,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "atan": math.atan,
    "floor": lambda x: float(math.floor(x)),
    "ceil": lambda x: float(math.ceil(x)),
    "abs_float": abs,
    "infinity": math.inf,
    "neg_infinity": -math.inf,
    "max_int": WORD,
    "min_int": -WORD - 1,
    # A keyword in OCaml, and a function here: `specification.md`, *Differences*.
    "assert": lambda holds: None if holds else fail("Assert_failure", ("", 0, 0)),
}

#: A value for every name `middle/prelude.py` gives a type. That module is
#: the source of what is in scope; this is the source of what it does, and
#: `test_every_prelude_value_has_a_type` holds the two in step.
ENV: dict[str, Any] = {
    **BUILTINS,
    **{op: curry(2)(fn) for op, fn in BINARY_OPS.items()},
    "!": UNARY_OPS["!"],
    **{
        f"{module}.{name}": value
        for module, entries in (
            ("List", LIST_MODULE),
            ("Array", ARRAY_MODULE),
            ("String", STRING_MODULE),
            ("Char", CHAR_MODULE),
            ("Float", FLOAT_MODULE),
            ("Sys", SYS_MODULE),
            ("Printf", PRINTF_MODULE),
            ("Random", RANDOM_MODULE),
            ("Stack", STACK_MODULE),
            ("Hashtbl", HASHTBL_MODULE),
        )
        for name, value in entries.items()
    },
}
