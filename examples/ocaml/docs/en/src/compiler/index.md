# The shape of a compiler

You know what a compiler does: source in, something runnable out. This section is about *how*, using one you can read.

No prior knowledge of compilers is assumed. If you can read Python, you can read this.

## The problem

Here is the whole difficulty in one line:

```ocaml
let rec sum l = match l with [] -> 0 | t :: q -> t + sum q
```

To a computer, that is 62 characters. It is not a function yet, nor a `match`, nor anything called `t`: it is a sequence of bytes, of which `t` is byte 44. Everything a compiler does is the work of turning that into something with structure and meaning.

It happens in three stages. Every compiler you will meet has them, whatever it calls them.

<div class="grid cards" markdown>

- **[1. Reading the text](reading.md)**

    Bytes to words to a tree: the *shape* of the programme.

- **[2. Working out what it means](meaning.md)**

    Which definition does each name refer to? What type does everything have?

- **[3. Running it, twice](running.md)**

    Walk the tree and do what it says, or turn it into another language.

</div>

## Following one line

Take that line and watch it go through. You can do all of this yourself, in [the playground](../play/) or on the command line.

### It becomes a list of words

The first pass, the **lexer**, splits the text into the smallest pieces that mean something on their own, called **tokens**:

```
kw:let  kw:rec  lid:sum  lid:l  sym:=  kw:match  lid:l  kw:with
sym:[  sym:]  sym:->  int:0  sym:|  lid:t  sym:::  lid:q  sym:->  ...
```

`lid` means a lowercase identifier, `kw` a keyword, `sym` a symbol. Nothing after this point ever looks at a character again, which is why spaces and comments stop mattering here.

### It becomes a tree

The second pass, the **parser**, works out the shape. `t + sum rest` is not four tokens in a row: it is an addition, whose left side is `t` and whose right side is a call. That is a tree:

```
LetItem(recursive=True, bindings=[
  Binding(pattern=PVar('sum'), params=[PVar('l')], value=
    Match(scrutinee=Var('l'), cases=[
      Case(pattern=PList([]),                       body=Int(0)),
      Case(pattern=PConstruct('::', [PVar('t'), PVar('q')]),
           body=BinOp('+', Var('t'), Apply(Var('sum'), [Var('q')]))),
    ]))])
```

Every compiler works on a tree like that, called an **abstract syntax tree**. In this one the nodes are ordinary Python dataclasses, listed in `src/ocaml/syntax.py`: sixty-six kinds of them.

You can see the tree indirectly by asking the compiler to print it back:

```console
$ python -m ocaml --printed sum.ml
let rec sum l = match l with [] -> 0 | t :: rest -> t + sum rest;;
```

If a bracket appears there that you did not write, the tree is not the shape you thought.

### It gets a meaning

The tree is a shape. It still does not know that the `t` in the body is the one the pattern introduced, or that `sum` returns an `int`.

Names first:

```console
$ python -m ocaml --names sum.ml   # abridged: the first of five trees
── vals ──
module    top              {sum}
  binding                    {l}
    case                       {}
    case                       {q, t}
```

Then the types are worked out, from nothing but the way the values are used:

```console
$ python -m ocaml --types sum.ml
val sum : int list -> int
```

`int` is written nowhere. `0` and `+` were enough.

### It runs

It runs either by walking the tree and doing what each node says, or by being turned into Python:

```console
$ python -m ocaml --python sum.ml
from ocaml.back import runtime as _rt
def sum(l):
    _s1 = l
    _ok3 = False
    _m2 = None
    if not _ok3 and _s1.tag == '[]':
        _m2 = 0
        _ok3 = True
    if not _ok3 and _s1.tag == '::':
        t = _s1.args[0]
        rest = _s1.args[1]
        _m2 = t + sum(rest)
        _ok3 = True
    if not _ok3:
        _rt.fail('Match_failure')
    return _m2
```

The `match` has become a chain of tests. That is what pattern matching *is*, once you look underneath: ask what kind of value you have, and where it fits, pull out the pieces and name them.

## The layout

Each stage is a directory, so the code is arranged the way the ideas are:

```
src/ocaml/
  syntax.py     the tree, which all three parts talk about
  front/        text in, tree out
  middle/       what the tree means
  back/         two ways to run it
```

The compiler is about 6,600 lines of Python, comments included.

## Why two back ends

Most compilers have one. This has two, which share their idea of what a value *is*. Running a programme both ways and comparing the output therefore tests the compiler itself.

It is not a hypothetical benefit. It found two real defects. Neither of them crashed: both gave wrong answers that every other test agreed with. [The third page](running.md) has the story.

---

Start with [reading the text](reading.md).
