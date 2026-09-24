# Building a compiler with astero

This tutorial walks through `examples/tinypy/`, a complete working compiler for a small subset of Python. It is under 400 lines and uses astero and the standard library only.

**TinyPy** supports integers, variables, `if`, `while`, arithmetic, comparison and `print`. It compiles to two back ends, chosen to be as different from each other as possible:

| | stack machine | C |
| --- | --- | --- |
| expressions | post-order, no brackets | infix, brackets from precedence |
| control flow | labels and jumps | nested braces |
| precedence table (`levels`) | `None` | required |

Sections 1 to 4 build the front end. **None of it moves** between the two back ends; sections 5 to 7 are where you can check that.

By the end you will have seen where astero does the work for you and, in the section on limits, where it stops and you write ordinary code.

Every code block below is copied from the example. `tests/a_unit/test_tutorial.py` fails if this page and `examples/tinypy/` disagree.

---

## 1. Declare the language

astero ships Python's grammar as `PY`. TinyPy is a subset of Python, so its grammar is `PY` restricted to the productions TinyPy admits. First the set:

```python
ADMITTED = frozenset({
    "Module", "FunctionDef", "arguments", "arg", "Return",
    "Assign", "AugAssign", "If", "While", "Expr", "Pass",
    "Name", "Constant", "BinOp", "Compare", "Call",
    "Add", "Sub", "Mult", "FloorDiv", "Mod",
    "Lt", "LtE", "Gt", "GtE", "Eq", "NotEq",
})
```

Then the grammar:

```python
TINYPY = PY.subset(ADMITTED, name="tinypy")
```

`TINYPY` is a full grammar. It knows the fields of every production listed, their shapes, their sorts, and which of them bind or read a variable: all inherited from `PY`. The abstract sorts (`stmt`, `expr`) come along too, so `TINYPY.concrete("stmt")` still works on the subset.

Productions that are not in `ADMITTED` are simply absent from `TINYPY`. `TINYPY.constructor("ListComp")` raises `KeyError`, and so does a rewrite rule that names one, so a pass cannot build what the language does not admit. Plain host code calling `ast.ListComp(...)` is of course unaffected. The checker in the next section catches that input.

## 2. Refuse anything outside the subset

Because the admitted set is data, the checker is one comprehension over it:

```python
def check(tree: ast.AST) -> list[str]:
    """Refuse what TinyPy does not admit, naming the production."""
    return [
        f"line {n.lineno}: {type(n).__name__} is not TinyPy"
        for n in ast.walk(tree)
        if isinstance(n, (ast.stmt, ast.expr)) and type(n).__name__ not in ADMITTED
    ]
```

`check(ast.parse("def f(): return [x for x in y]"))` reports `line 1: ListComp is not TinyPy`.

The checker and the grammar read the same `ADMITTED`, so they cannot disagree about which productions the language admits. Add a production to the set and the checker starts accepting it in the same commit.

## 3. Desugar `+=`

TinyPy accepts `x += 1`, but neither back end needs to know about it, so a rewrite pass turns it into `x = x + 1`:

```python
DESUGAR = Pass(
    "desugar",
    rules("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))"),
    eliminates=(ast.AugAssign,),
    grammar=TINYPY,
)
```

`_t`, `_o` and `_v` are pattern variables capturing the target, the operator and the value. `DESUGAR(tree)` applies the rule bottom-up over the whole tree and returns a new one.

**The rule does not mention `ctx`.** In Python's AST an assignment target carries `ctx=Store()` and a read carries `ctx=Load()`. This rule places `_t` in two positions at once: as the target of the `Assign`, where it must be `Store`, and as the left operand of the `BinOp`, where it must be `Load`. astero looks up the roles of `Assign.targets` and `BinOp.left` in the grammar and sets each context accordingly, so one rule covers `x += 5`, `b[1] += 5` and `obj.f += 5` with no special cases.

**`eliminates=` is a postcondition.** After the pass runs, astero walks the result and raises if any `AugAssign` remains. A rewrite whose pattern matches nothing is otherwise hard to notice, because the tree is still valid, just untransformed.

## 4. Allocate a slot for each local

Both back ends need to know which names a function binds. `names_bound_by` answers that for one node, from the grammar's roles:

```python
def slots(fn: ast.FunctionDef) -> dict[str, int]:
    names = [a.arg for a in fn.args.args]
    # The body, not the whole node: a function binds its own name in the
    # scope that encloses it, so walking `fn` allocated a slot for `f` that
    # nothing ever loaded.
    for stmt in fn.body:
        for node in ast.walk(stmt):
            names += sorted(names_bound_by(node, TINYPY, VARS))
    return {n: i for i, n in enumerate(dict.fromkeys(names))}
```

`names_bound_by(node, grammar, ns)` returns the set of variable names that *this node* introduces: `{"x"}` for `x = 1`, `{"i"}` for `for i in xs`, the empty set for `x + 1`. It works for any production in the grammar, so the loop above never enumerates target shapes.

Written by hand, this function becomes a chain of `isinstance` checks covering `Name`, tuple and starred targets, `for` targets, `with ... as`, `except ... as`, the walrus operator and comprehension variables. Every case you forget is a local the compiler fails to allocate. Reading the positions out of the grammar makes the list complete by construction, so it stays complete when the language grows.

## 5. Back end one, expressions: a stack machine

An `Emitter` is a table of templates, one or more per production. A stack machine wants the operator *after* its operands, and since a template's holes are filled in the order they are written, putting the operator last produces post-order output:

```python
vm.rule("Name", "PUSH {id:slot}")
vm.rule("Constant", "CONST {value:lit}")
vm.rule("BinOp", "{left}\n{right}\n{op:binop}")
vm.rule("Compare", "{left}\n{comparators}\n{ops:cmp}")
```

`{left}` emits whatever node is in that field. `{id:slot}` is a **projection**: `slot` names a function registered with `vm.projection("slot", ...)`, which converts a value that is not a node (here a variable name) into text. A projection is the only place an emitter calls a function you wrote.

The emitter is built with `Emitter(TINYPY, levels=None)`. `levels` is the precedence table used to decide bracketing; a stack machine has no brackets, so it has no table.

## 6. Back end one, statements: labels and jumps

Control flow is a template as well, because the notation can name a label:

```python
    vm.rule(
        "While",
        "{&top}:\n{test}\nJZ {&done}\n{body:\n}\nJMP {&top}\n{&done}:",
    )
```

Two pieces of notation do the work.

`{&top}` is a **label hole**. It generates a label unique to this node, so writing `{&top}` twice in one template refers to the same label, while a second `while` in the same function gets a different one. Nested and sequential loops therefore interleave correctly without a counter of your own.

`{body:\n}` renders a field holding a *list* of nodes, joined with the text after the colon, here a newline. The break is recorded in the emitted document, which matters when you call `to_lines`: it splits where a template said to break. A newline inside a value never causes a split.

The `If` rule is one more line of the same shape. Between them they are the whole of TinyPy's control flow.

## 7. Back end two: C

Nothing in sections 1 to 4 changes. The second back end is a second `Emitter` over the same grammar. It needs a precedence table, because C has infix operators:

```python
C_LEVELS = {
    ast.Lt: Level(6, Assoc.NONE),
    ast.Gt: Level(6, Assoc.NONE),
```

A `Level` is a binding power and an associativity. The full table has eleven entries, one per operator TinyPy admits.

The expression rules are then plain infix:

```python
    c.rule("BinOp", "{left} {op:sym} {right}")
    c.rule("Compare", "{left} {ops:sym} {comparators}")
```

and control flow is written with braces:

```python
    c.rule("While", "while ({test}) {{\n{body:\n}\n}}")
    c.rule("If", "if ({test}) {{\n{body:\n}\n}} else {{\n{orelse:\n}\n}}")
```

Three things to notice.

**No rule mentions a parenthesis.** Brackets come from `C_LEVELS`. When the emitter fills `{left}`, it compares the binding power of the child against the binding power of the operator around it, and brackets only where it must. `(n * 3 + 7) // 2 - n % 4` emits as `(n * 3 + 7) / 2 - n % 4`: the one bracket that is needed, and no others.

**`{{` and `}}` are literal braces**, following `str.format`, so a C block can be written the way it reads.

**The two back ends share no code.** The stack machine's `While` names two labels; the C one names none. Neither emitter knows the other exists. Both are driven by the same front end.

Correctness is checked as a three-way comparison: CPython says what a TinyPy program means; both back ends must agree with it. `tests/a_unit/test_tutorial.py` runs four programs through CPython and the stack machine at five inputs each, and all three (adding C compiled with `cc`) at four.

## 8. Gate the emitter against the grammar

```python
def coverage() -> Coverage:
    """Every statement TinyPy admits has a rule. The gate, from the grammar."""
    return Coverage(handled=emitter({}).covered(), expected=STATEMENTS)
```

`Coverage` compares what you handle against what the language contains. Add a statement to `ADMITTED` and forget to write its rule: this test fails naming the production, before a user ever hits a `NotImplementedError`.

If your generator is a `match` statement, `coverage.match_arms(fn)` reads the `case ast.X()` patterns back out of the function's source, so the same gate applies.

## 9. Run it

```python
code = compile_source("def f(n):\n    t = 0\n    i = 0\n    while i < n:\n        t += i\n        i = i + 1\n    return t\n")
```

```
STORE 0
CONST 0
STORE 1
...
L1:
PUSH 2
PUSH 0
LT
JZ L2
```

`examples/tinypy/vm.py` executes that instruction list and `examples/tinypy/run_c.py` compiles the C with `cc` and runs the result, so every program can be checked against what CPython does with the same source.

---

## Where the code went

| the job | the code |
| --- | --- |
| **the front end, shared by both back ends** | **written once** |
| declaring the language | a `frozenset` and `PY.subset` |
| refusing what is outside it | one comprehension |
| desugaring `+=` | one rule, no mention of `ctx` |
| slot allocation | `names_bound_by`, no target shapes enumerated |
| stack machine, complete | 11 rules, 5 projections |
| C back end, complete | 11 rules, 4 projections, 1 precedence table of 11 entries |
| the coverage gate | 2 lines |

## Limits: what you write yourself

These are not missing features. Each is outside what a declaration over a grammar can express, and knowing them in advance saves you the experiment.

**Parsing.** astero starts from a tree. Bring your own front end, or use `ast.parse`.

**The runtime library.** Every target needs helper functions, and nothing about a grammar determines them.

**Lowering.** Turning a comprehension into a loop, `with` into try/finally, or `for` into the iterator protocol. A rewrite rule maps one shape onto another shape of fixed size; a lowering builds a list of statements whose length depends on the input, so there is no fixed shape for a template to describe. Write it as a function.

**Name resolution.** Deciding that `js.console` refers to the host's `console` is a policy question for your compiler. astero's guard vocabulary is closed. A guard meaning "ask this other subsystem" would open it.

**A cost model.** "Is this operand provably a small constant?" and "can this operation overflow?" choose a *representation*. In one WebAssembly back end this accounts for 47% of the expression emitter. No closed set of guards reaches it, because the answers are facts about a program.

**The semantic gap.** How large a back end is depends on how far your source language is from your target. Python's `%` is not JavaScript's, its `dict` is not a JavaScript object, its `bool` is an `int` subclass whose bitwise operators still produce `bool`. This is per-target work and it is usually most of a back end.

**Indentation in `emit_rules`.** The C above is brace-correct but not indented, because the rule notation has no way to reach the document layer's `Nest`. `astero.emit` supports indentation and astero's own Python emitter uses it; `emit_rules` templates do not yet. That is cosmetic for C and a correctness problem for a whitespace-significant target.
