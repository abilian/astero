# The front end: text to tree

The front end answers three questions in order: which words the text contains, which structure they form, and, going back the other way, how a structure turns into words again.

## Words: the lexer

A compiler does not work on characters. The first thing it does is chop the text into the smallest pieces that mean something on their own, called **tokens**. `let x = 42` is four of them:

| token | kind |
| --- | --- |
| `let` | a keyword |
| `x` | a lowercase identifier |
| `=` | a symbol |
| `42` | an integer |

`front/lexer.py` does that with one regular expression, mostly: a named group per kind, tried in the order written. Everything after this point works on tokens, which is why the grammar never has to think about whitespace.

Two of OCaml's rules need real code, which is why the lexer is a file of its own.

**Comments nest.** `(* a (* b *) c *)` is one comment, which does not end at the first `*)`. No regular expression can say that, so `skip_comment` counts the pairs.

**`'a'` is a character and `'a` is a type variable.** They start the same way. The fix is one ordered choice: try the character pattern first, because a character literal always has a closing quote and a type variable never does.

```python
    | (?P<char>  ' (?: {escape} | [^\\'] ) ' )
    | (?P<tyvar> ' [a-z_][A-Za-z0-9_']* )
```

That ordering *is* the rule. Swap the two lines and `'a'` becomes a type variable followed by a stray quote.

## Structure: the parser

Given the tokens, what is the shape? `front/peg.py` is a small engine and `front/parser.py` is the grammar written on top of it.

The engine provides the pieces any grammar needs. A parser is a function from a position in the token list to either a result and a new position, or `None` for "did not match", and the combinators build bigger ones out of smaller:

```python
def seq(*parsers): ...      # a, then b, then c
def alt(*parsers): ...      # try a; if it fails, try b
def many(parser): ...       # as many as there are
def opt(parser): ...        # one, or none
```

This style is called **PEG**, for *parsing expression grammar*. Two of its properties matter here. `alt` tries its alternatives **in order** and takes the first that works. `many` is **greedy** and takes as much as it can.

Those two properties are why OCaml suits it. The language is full of forms that run as far to the right as they can:

```ocaml
let x = 1 in a; b            (* the let's body is `a; b`, not just `a` *)
match n with 0 -> a; b       (* the arm's body is `a; b` *)
if a then if b then c else d (* the else belongs to the inner if *)
fun x -> a; b                (* the function's body is `a; b` *)
```

Greedy repetition gets all four right by simply not stopping early. A parser generator in the older LR style resolves the same four conflicts, but only after somebody writes a table of precedences telling it how.

The grammar reads close to the notation a textbook uses:

```python
if_expr = act(
    seq(lit("if"), seq_expr, lit("then"), expr, opt(seq(lit("else"), expr))),
    lambda v: s.If(v[1], v[3], v[4][1] if v[4] else None),
)
```

`seq(...)` matches the pieces, and `act` says what to build out of them: an `If` node whose parts are the second, fourth and fifth things matched.

### One table, ten rules

OCaml has ten levels of binary operator. Writing ten near-identical rules would work and would be ten places to make a mistake, so the table is data and the rules are generated from it:

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

Loosest first. `_level` turns one row into one rule; the cascade is built by folding over the table. Add an operator to a row and the parser has it.

The table is used a second time, on the way out.

### Packrat

"Packrat" means the engine remembers. `Rule` caches what it found at each position, so a seventeen-level cascade costs one pass. The cache takes eight lines and keeps parsing linear in the length of the input.

## Back the other way: the printer

`front/emit.py` turns a tree into text. It has two uses; the second is why it exists.

It shows you what the compiler thought you wrote. If a bracket appears that you did not type, the parser grouped it differently from you.

It is also how the parser is checked. Print a tree, read the printed text back, compare the two trees:

```python
assert parse(unparse(parse(source))) == parse(source)
```

The check runs over all sixty corpus programmes, plus eighteen hand-written cases where dropping a bracket would change the meaning. A grammar rule that groups the wrong way passes every assertion somebody thought to write and fails this one.

Brackets are the difficulty of printing, and none of them is counted by hand. `astero.emit` supplies the rule (*a child needs brackets when it binds less tightly than the position it sits in*), and this file supplies the table. The table is `parser.LEVELS`, the same rows the parser cascades over:

```python title="src/ocaml/front/emit.py"
OPERATOR_LEVEL: dict[str, Level] = {
    op: Level(BINARY_BASE + index, ASSOC[assoc])
    for index, (ops, assoc) in enumerate(LEVELS)
    for op in ops
}
```

The one declaration has two consumers: the parser groups by it on the way in, and the printer brackets by it on the way out. A row added to `LEVELS` changes both, and they cannot disagree.

It caught a defect the first time it ran. Constructor arguments and list elements shared a helper, so `C (a, b)` printed as `C (a; b)`. Four programmes parsed, resolved and looked right; only the reparse disagreed.

## Why write the engine at all

Because the test suite runs on Python 3.11 through 3.15 with pytest and nothing else installed, and astero and both its sibling examples have no dependencies. `peg.py` is 125 lines of code, which is what that costs.

A note in the file says to take `lark` instead if it ever passes about two hundred, so the decision has a stated ceiling.

---

Next, in [the middle end](middle.md), the tree stops being a shape and starts having a meaning.
