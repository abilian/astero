# The back ends: two of them, one runtime

There are two ways to run the tree. Walk it and do what each node says, or turn it into a Python programme that does the same thing. This compiler does both, over one runtime, so that each checks the other.

## One runtime, shared

Before either back end, there has to be an answer to *what is an OCaml value, in Python?* `back/runtime.py` gives it:

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

Two of those are decisions. Lists are cons cells because `::` has to cost nothing and because sharing is visible: `x :: l` and `l` are the same tail, and a programme that builds a list by consing in a loop is what a student writes. `ref` gets no class of its own: in OCaml it is a record with one mutable field, over which `!`, `:=`, `incr` and `decr` are ordinary functions. The commonest programme in the corpus therefore exercises the record machinery.

Both back ends use this file, which is what made the second one cheap: it cost an emitter and nothing else, because there is no second value representation and no second `List.fold_left`.

It also means that running a programme both ways and comparing the output is a test **of the compiler**. If they were two separate implementations, a disagreement would only tell you that two programmes differ.

## Walking the tree

`back/interpret.py` is the simplest thing that can be called running a programme. `eval_expr` takes a node and an environment and returns a value:

```python title="src/ocaml/back/interpret.py"
        case s.BinOp(op=op, left=left, right=right):
            return BINARY_OPS[op](eval_expr(left, env), eval_expr(right, env))
```

```python title="src/ocaml/back/interpret.py"
        case s.If(cond=cond, then=then, otherwise=otherwise):
            if eval_expr(cond, env):
                return eval_expr(then, env)
            return eval_expr(otherwise, env) if otherwise is not None else None
```

One `case` per kind of node, so you can read the whole language's behaviour in one function. It is also the reference semantics: the [specification](https://caml-prepa.lab.abilian.com/en/language/specification/#evaluation)'s *Evaluation* section is what it implements, and where the two disagree one of them is wrong.

**A function value is a Python callable of one argument**, because OCaml functions are curried: `add 1 2` is really `(add 1) 2`. `Fun` with three parameters builds three nested closures, and partial application then falls out with no arity bookkeeping anywhere.

**`let rec` fills a scope its closures already hold.** The child mapping is created first and populated after, so a closure built during the pass can see names the pass is still binding. That is the same fact the scope declaration states, arrived at from the other side.

## Emitting Python

`back/compile.py` turns the tree into Python source instead. You can read it, save it, and run it without this compiler:

```console
$ python -m ocaml --python corpus/fact.ml   # abridged
from ocaml.back import runtime as _rt
print_int = _rt.ENV['print_int']
...
def fact(n):
    return 1 if _rt.BINARY_OPS['<='](n, 1) else n * fact(n - 1)
```

Three things it decides that the interpreter never has to.

**Arity.** `let f x y = e` is known to take two parameters, because the tree kept them, so it becomes `def f(x, y)` and a saturated `f a b` becomes `f(a, b)` rather than `f(a)(b)`. Every other call goes through `runtime.apply`, which works out at run time how many arguments the callee wants.

**Pattern matching.** `match` has to become a chain of tests. `back/patterns.py` produces two things from a pattern: the conditions that must hold, and where each name it binds is found. An or-pattern is expanded into separate patterns first, so the tests are always simple paths into the value.

**Names.** OCaml identifiers may contain `'` and Python's may not, and a `let` shadows where a Python assignment rebinds. So every binder gets a fresh Python name:

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

The second `x` becomes `x_2`, so the closure keeps reading the `x` it captured. The names a generated temporary must avoid are seeded by `astero.python.hygiene.all_names` over the *OCaml* tree.

Where the output calls `_rt.BINARY_OPS['/']`, the two languages disagree: OCaml's integer division truncates towards zero where Python's floors, and `=` is structural equality. Where they agree, the operator is emitted directly, which is why the arithmetic above reads normally.

The Python is built as an `ast` tree and rendered by `astero.python.emit`, which makes OCaml that emitter's first source language other than Python.

## What comparing them found

The differential test is one line: run the programme both ways, and assert the output is the same. It found two defects, and neither crashed.

**The runtime assumed how a function value was spelled.** `List.fold_left` applied its function as `f(a)(b)`. The interpreter's curried closures accept that; the compiler's multi-argument `def`s do not. Every higher-order function now goes through `runtime.apply`, which asks the callee how many arguments it wants. A runtime shared by two back ends may not assume either convention, a lesson the single-back-end version could not have taught.

**A top-level `let` wrote into a scope a closure had already captured.**

```ocaml
let x = 1
let f = fun () -> x
let x = 2
let y = f ()
```

OCaml gives `y = 1`: the second `let` is a new binding that shadows the first. The interpreter gave 2, because it updated the scope in place. The compiled programme gave 1, because a fresh Python name made shadowing impossible to get wrong. They disagreed on the first run. The interpreter was wrong.

That is why the second back end exists. A teaching compiler needs only the interpreter, yet two implementations over one runtime check each other in a way neither can check itself.

---

Next, [the playground](playground.md) runs all of this in a browser.
