# 3. Running it, twice

The tree has a shape and a meaning. Now something has to happen.

There are two ways. This compiler does both.

## First: what is a value?

Before either, one question has to be answered. When the programme has a list, what *is* that, in Python?

`src/ocaml/back/runtime.py` decides:

| OCaml | in Python |
| --- | --- |
| `int`, `float`, `bool`, `string` | the Python one |
| `char` | a one-character `str` |
| `unit` | `None` |
| a tuple | a Python tuple |
| `'a list` | linked cells: `Value("::", (head, tail))`, ending at `Value("[]")` |
| `'a array` | a Python `list` |
| a record, and so `'a ref` too | `Record(fields)` |
| `Some x`, `Feuille`, an exception | `Value(tag, args)` |
| a function | a Python callable of one argument |

Three of those need defending.

**Lists are linked cells.** In OCaml, `x :: l` costs nothing and shares `l`: the new list *is* `x` pointing at the old one. A Python list would have to copy, which would be the wrong cost and, worse, the wrong behaviour when two lists share a tail.

**`ref` gets no special treatment.** In OCaml `ref` is not built in: it is a record with one mutable field, and `!`, `:=`, `incr` and `decr` are ordinary functions over it. So it is a `Record` here too, which means the commonest programme anybody writes.

**A function takes one argument.** OCaml functions are curried, meaning `add 3 4` is really `(add 3) 4`, and `add 3` on its own is a perfectly good function that adds 3. Representing every function as taking one argument at a time makes that fall out with no bookkeeping.

## Way one: walk the tree

`back/interpret.py` is the simplest thing that can be called running a programme. A function takes a node and an environment and gives back a value:

```python title="src/ocaml/back/interpret.py"
        case s.BinOp(op=op, left=left, right=right):
            return BINARY_OPS[op](eval_expr(left, env), eval_expr(right, env))
```

Evaluate the left, evaluate the right, apply the operator. And:

```python title="src/ocaml/back/interpret.py"
        case s.If(cond=cond, then=then, otherwise=otherwise):
            if eval_expr(cond, env):
                return eval_expr(then, env)
            return eval_expr(otherwise, env) if otherwise is not None else None
```

One case per kind of node, so the whole language's behaviour is one function you can read top to bottom. The file is 209 lines of code.

If you have ever wondered what "an interpreter" really is, that is it. There is no trick.

## Way two: turn it into Python

`back/compile.py` produces a Python programme that does the same thing:

```console
$ python -m ocaml --python corpus/fact.ml   # abridged
from ocaml.back import runtime as _rt
print_int = _rt.ENV['print_int']
...
def fact(n):
    return 1 if _rt.BINARY_OPS['<='](n, 1) else n * fact(n - 1)
```

You can save that, run it with `python`, and never involve this compiler again.

Three things it has to decide that the interpreter never does.

**How many arguments.** The interpreter can take them one at a time and not care. A compiler wants `def f(x, y)` and a direct call `f(a, b)`, because `f(a)(b)` is slower and reads worse. It knows the number because the tree kept it, from the moment the parser saw `let f x y = ...`.

**How to test a pattern.** `match` has to become ordinary control flow. The earlier example showed the shape: ask what kind of value it is, and where it fits, pull out the pieces and give them the pattern's names.

**What to call things.** OCaml identifiers may contain `'`; Python's may not. Worse, a `let` in OCaml shadows the earlier name, where a Python assignment overwrites it. The first example on the [previous page](meaning.md) turned on that difference. So every binding gets a fresh Python name:

```console
$ python -m ocaml --python shadow.ml
from ocaml.back import runtime as _rt
x = 1
def _fn2(_p1):
    if not _p1 == None:
        _rt.fail('Match_failure')
    return x
f = _fn2
x_2 = 2
y = _rt.apply(f, None)
```

The second binding took the fresh name `x_2`, so the closure keeps reading the `x` it captured. That is what OCaml means.

Where you see `_rt.BINARY_OPS['/']` in place of a plain `/`, the two languages genuinely disagree: OCaml's integer division truncates towards zero and Python's rounds down, so `(-7) / 2` is `-3` in one and `-4` in the other. Where they agree, the operator comes out directly.

## Why two, and what it caught

Both back ends use the same `runtime.py`. That is the point of the arrangement. Because they share their idea of what a value is, running a programme both ways and comparing the output tests **the compiler**. If they were two separate implementations, a difference would only tell you that two programmes differ.

The playground does this on every run. The status line says *both back ends agree*. If it ever does not, one of them has a bug.

It has found two. Neither of them crashed. A crash gets noticed; an answer that is merely wrong does not.

### The runtime assumed how a function was written

`List.fold_left` called its argument as `f(a)(b)`, one argument at a time, the way the interpreter's functions work. The compiler's functions take both at once, so the moment a corpus programme folded a two-argument function, it broke.

The fix is a small function, `apply`, that asks the callee how many arguments it wants. The lesson generalises: a runtime shared by two back ends may not assume either one's conventions, and with a single back end there is nothing to teach you that.

### A closure saw a binding it should not have

Here is the example from the previous page:

```ocaml
let x = 1
let f = fun () -> x
let x = 2
let y = f ()
```

OCaml gives `y = 1`. The interpreter gave **2**, because it updated the scope in place, so `f` saw the change. A new binding should have made a new scope.

The compiled version gave 1, because a fresh Python name made shadowing impossible to get wrong. They disagreed on the very first run of the comparison. The interpreter was the one that was wrong.

Every other test in the suite had agreed with the interpreter, because every other test compared it against itself.

## What this buys you

If you take one idea away from this section, take that one. Two implementations of the same thing, sharing whatever they can and checking each other, beat one implementation and a hundred tests you wrote yourself. You can only test what you thought of. The second implementation disagrees about the things you did not.

---

That is the compiler, end to end. If you want to read it, `src/ocaml/` is about 6,600 lines and the [getting started](../getting-started.md) page has it cloned in three commands.
