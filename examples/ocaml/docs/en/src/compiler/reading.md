# 1. Reading the text

This part answers two questions, in order. Which words did you write? What shape do they make?

## Words: the lexer

`let x = 42` is four pieces:

| piece | what it is |
| --- | --- |
| `let` | a keyword |
| `x` | a lowercase identifier |
| `=` | a symbol |
| `42` | an integer |

Those are **tokens**. Producing them is the first thing a compiler does. `src/ocaml/front/lexer.py` is 152 lines of code, mostly one regular expression with a named group per kind of token.

The payoff is that nothing afterwards ever thinks about characters. Spaces, newlines and comments disappear here. The grammar in the next section never has to mention them.

Two of OCaml's rules need real code. They are the reason the lexer is a file of its own.

**Comments nest.** `(* a (* b *) c *)` is one comment. The first `*)` does not end it. No regular expression can say so, which is why a small function counts the pairs.

**`'a'` is a character and `'a` is a type variable.** They start identically, so the order the patterns are tried in *is* the rule:

```python
    | (?P<char>  ' (?: {escape} | [^\\'] ) ' )
    | (?P<tyvar> ' [a-z_][A-Za-z0-9_']* )
```

The character pattern comes first, because a character literal always has a closing quote and a type variable never does. Swap those two lines and `'a'` becomes a type variable followed by a stray quote.

A great deal of a compiler is decisions like this one, where the rule is an ordering.

## Shape: the parser

Given the tokens, what is the structure? This is the part with a reputation. It deserves less of one than it has.

The engine is `front/peg.py`, 125 lines. A parser is a function that takes a position in the token list and returns either a result and a new position, or `None` meaning "that did not match". Everything is built from four of them:

```python
def seq(*parsers): ...      # a, then b, then c
def alt(*parsers): ...      # try a; if it fails, try b
def many(parser): ...       # as many as there are
def opt(parser): ...        # one, or none
```

Those four are the engine. You could write them yourself in an afternoon. The grammar is then a description of the language written with those pieces:

```python title="src/ocaml/front/parser.py"
if_expr = act(
    seq(lit("if"), seq_expr, lit("then"), expr, opt(seq(lit("else"), expr))),
    lambda v: s.If(v[1], v[3], v[4][1] if v[4] else None),
)
```

Read it as: match `if`, then an expression, then `then`, then an expression, then optionally `else` and another. Then build an `If` node out of the second, fourth and fifth things matched.

`src/ocaml/front/parser.py` is 391 lines of that, one rule per form the language has.

### Why this style suits OCaml

This is called a **PEG**, for *parsing expression grammar*. It has two properties. `alt` tries its alternatives **in order** and takes the first that works. `many` is **greedy** and takes as much as it can.

Those two happen to be exactly what OCaml needs, because the language is full of forms that run as far right as they can:

```ocaml
let x = 1 in a; b            (* the let's body is `a; b`, not just `a` *)
match n with 0 -> a; b       (* the arm's body is `a; b` *)
if a then if b then c else d (* the `else` goes with the inner `if` *)
fun x -> a; b                (* the function's body is `a; b` *)
```

Greedy repetition gets all four right by not stopping early. Older parser generators can also get them right, but only once somebody writes a table of precedences telling them how. Getting that table wrong is a classic source of bugs that never announce themselves.

### Precedence, from one table

`1 + 2 * 3` is 7, because `*` binds tighter than `+`. OCaml has ten such levels. Writing ten near-identical rules would work and would be ten chances to make a mistake, so the levels are data:

```python title="src/ocaml/front/parser.py"
LEVELS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("||",), "right"),
    (("&&",), "right"),
    (("=", "<>", "<", "<=", ">", ">="), "left"),
    (("@", "^"), "right"),
    (("::",), "right"),
    (("+", "-", "+.", "-."), "left"),
    (("*", "/", "*.", "/.", "mod", "land", "lor", "lxor"), "left"),
    (("**", "lsl", "lsr", "asr"), "right"),
)
```

Loosest first. The rules are generated from it. Add an operator to a row and the parser has it.

That table gets used a second time, which is the next section.

## Backwards: printing

`front/emit.py` turns a tree back into text. It has two uses. The second is the one that matters.

It shows you what the compiler thought you wrote. Type `1 + 2 * 3` into the playground and look at **Read back**; the brackets tell you how it grouped.

It is also how the parser is *checked*. Print a tree, read the text back, compare the trees:

```python
assert parse(unparse(parse(source))) == parse(source)
```

If the parser groups something the wrong way, this catches it. A hand-written test only catches the cases somebody thought of.

Brackets are the difficulty of printing. None of them is decided by hand. The rule fits in one sentence: a child needs brackets when it binds less tightly than the place it sits in. The table it needs is `LEVELS`, the same rows the parser already uses:

```python title="src/ocaml/front/emit.py"
OPERATOR_LEVEL: dict[str, Level] = {
    op: Level(BINARY_BASE + index, ASSOC[assoc])
    for index, (ops, assoc) in enumerate(LEVELS)
    for op in ops
}
```

The one declaration has two uses: the parser groups by it on the way in, and the printer brackets by it on the way out. They cannot disagree, because there is only one of them.

It found a real defect the first time it ran. Constructor arguments and list elements shared a helper, so `C (a, b)` printed as `C (a; b)`. Four programmes parsed fine, resolved fine, and ran fine; only printing and reading back disagreed.

---

Next: [working out what it means](meaning.md).
