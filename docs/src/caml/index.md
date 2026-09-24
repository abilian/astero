# caml-prépa: a compiler you can look inside

`examples/ocaml/` is a complete compiler for the OCaml subset taught in French preparatory classes, built on astero. It reads a programme, works out what its names refer to and what type everything has, and then either runs it or turns it into Python.

Most compilers are opaque: source goes in, a result comes out. This one will show you its working.

```console
$ python -m ocaml corpus/fact.ml
120
120
120
```

That is the ordinary use. The interesting ones are the other four.

## Five views of one programme

Take a small programme, `sum.ml`:

```ocaml
let rec sum l =
  match l with
  | [] -> 0
  | t :: rest -> t + sum rest
```

**What type did it get?** The file carries no annotation and never says `int`. The compiler works it out from `0` and `+`:

```console
$ python -m ocaml --types sum.ml
val sum : int list -> int
```

**Which name refers to what?** No other OCaml playground has this view; this project exists to show it:

```console
$ python -m ocaml --names sum.ml   # abridged: the first of five trees
── vals ──
module    top              {sum}
  binding                    {l}
    case                       {}
    case                       {rest, t}
```

Read it as a nesting of scopes. The whole file binds `sum`. Inside it, the function's own block binds `l`. Inside *that*, the two `match` arms each have a block of their own: the first binds nothing, and the second binds `rest` and `t`. So `t` and `rest` exist only inside that arm, while `sum` is visible everywhere, which is what makes the recursive call work.

There are four more trees below that one, because OCaml keeps five kinds of name apart: values, constructors, record fields, type names and type variables. A record label `x` and a variable `x` are unrelated names; separate trees stop a rename of one from touching the other.

**What does it compile to?**

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

A `match` has become a chain of tests. Each one asks what kind of value it has, and where it fits, pulls the pieces out into the names the pattern gave them.

**And how did the compiler read what I wrote?**

```console
$ python -m ocaml --printed sum.ml
let rec sum l = match l with [] -> 0 | t :: rest -> t + sum rest;;
```

Printing the tree back out is how you check that the grouping is what you meant. If a bracket appears that you did not write, the parser read it differently from you.

## In a browser

All six views, side by side, with the sixty worked programmes in a dropdown:

```sh
make -C examples web-serve
```

Then <http://localhost:8000/>. The page runs the whole compiler itself, with nothing installed and nothing uploaded. It runs the compiled Python as well as the tree and tells you whether the two agreed. See [the playground](playground.md).

## How it is put together

The layout follows a compiler course, with one directory per part:

| | | |
| --- | --- | --- |
| [**front/**](front.md) | text in, tree out | `lexer` `peg` `parser` `emit` |
| [**middle/**](middle.md) | what the tree means | `grammar` `analyze` `unify` `prelude` `infer` |
| [**back/**](back.md) | two ways to run it | `runtime` `interpret` `compile` `patterns` `pyast` |

`syntax.py` sits above all three, because the tree is what they all talk about.

The compiler is about 3,500 lines of Python. The largest single file is 523 lines. The smallest part is the piece this whole repository is about:

```python
ROLES = {
    "PVar": {"name": defines(VALS)},
    "PAlias": {"name": defines(VALS)},
    "Var": {"name": uses(VALS)},
    "Variant": {"name": defines(CONS)},
    "ExnItem": {"name": defines(CONS)},
    ...
}
```

The Names view above is derived from sixteen lines like that plus five scope entries. [The middle end](middle.md) is where that happens.

## The language

The subset covers `let rec`, pattern matching, lists, arrays, records, sum types, references, loops and exceptions. It is chosen by one test: does a first- or second-year programme use it? Functors, objects, GADTs and labelled arguments fail that test. `Printf`, `Hashtbl` and `Stack` pass it, and are there.

[The specification](https://caml-prepa.lab.abilian.com/en/language/specification/), on the caml-prépa site, gives lexical structure, the full grammar, the precedence table, static and dynamic semantics, the standard library, and every place where it knowingly differs from real OCaml. The playground ships a [reference card](playground.md) whose tables are generated from the compiler itself.

## Is it correct?

Every stage is compared against something that is not itself:

| stage | checked against |
| --- | --- |
| parse | print the tree and read it back; the tree has to be the same |
| names | every corpus programme resolves; scope trees compared by shape |
| types | `ocamlc -i`, signature by signature |
| run | the real `ocaml`, output compared |
| compile | the interpreter, over the same runtime |

The last row is the one that keeps paying. Two back ends sharing one runtime means a disagreement is a defect in one of them; it found two. A runtime function assumed how a closure was spelled. A top-level `let` wrote into a scope a closure had already captured. Neither crashed. Nothing else in the suite would have noticed either.

### The corpus those rows run over

The corpus holds sixty programmes, each checked in beside the output it prints and the signature it infers. Ten cover the language and eight cover the syllabus one chapter at a time. Twenty-three are in `corpus/simonet/`, one per subject of the exercise series Vincent Simonet set at the Lycée Janson-de-Sailly between 1998 and 2003. Those twenty-three go well past the syllabus: LZW, red-black insertion, Knuth-Morris-Pratt and Boyer-Moore, Thompson's construction with the subset construction after it, Barnes-Hut over a quadtree. The last nineteen, in `corpus/grimaud/`, are copied under the GPL-3.0 from the solutions Aslı Grimaud and Gilles Grimaud publish with their textbook *Informatique MPI*: Kosaraju, Kruskal, maximum bipartite matching, determinisation of an automaton, knapsack six ways, and a calculator with a lexer built on an automaton. Each file names the repository, the commit and the path it came from, and lists what was changed; fourteen are unchanged.

Every concrete production of the grammar is reached by one of them; `test_the_corpus_reaches_every_production` fails otherwise, so a production nothing writes does not belong in the subset.

Writing the Simonet set added no production and produced no wrong answer. It found three constructs the compiler refuses and OCaml accepts: `C _` where `C` takes more than one argument, an unparenthesised `if` to the right of a binary operator, and `for _ = 1 to n`. The compiler rejects all three with an error, so none can give a wrong answer. They are now rows of the [specification](https://caml-prepa.lab.abilian.com/en/language/specification/#differences-from-ocaml)'s *Differences from OCaml*, each with the way out.

### What the real compiler says

When OCaml 5.5.0 is installed, `ocaml` prints for all sixty programmes exactly what both back ends print. `ocamlc -i` infers the same signature as this checker, line for line.

That last part took the Grimaud set. Installing OCaml had found a fourth divergence: `ocamlc -i` keeps a type abbreviation, and this checker expanded it, so two lines of `records.ml` printed `point` where OCaml printed `position`. The test carried those two lines as known exceptions. The textbook's programmes annotate with abbreviations throughout (`solution`, `word`, `cover`), and fourteen of the nineteen disagreed on some signature. The checker now keeps an abbreviation as a type of its own that unification opens only when it has to, which is what OCaml does. The exception table is gone. The same set brought typed `Printf` formats, `Hashtbl` and `Stack`, and fields shared by two record types, resolved by type.

The two rows needing a real OCaml skip where there is none.
