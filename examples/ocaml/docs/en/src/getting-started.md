# Getting started

Three ways to use it, in increasing order of effort.

## 1. In your browser

[Open the playground](../play/). There is nothing to install and no account to create.

Pick a programme from the dropdown, or type your own, and press <kbd>Ctrl</kbd> or <kbd>⌘</kbd> + <kbd>Enter</kbd>. The five tabs on the right show what it prints, the types it inferred, the scopes, the Python it compiles to, and your source printed back.

Everything runs inside the page. Your code is not uploaded anywhere, and after the first load it works offline. The **Copy link** button puts your programme in the URL, so you can send it to somebody.

## 2. On your own machine

You need [Python 3.11 or later](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/), which is one command to install:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then:

```sh
git clone https://github.com/abilian/astero
cd astero/examples/ocaml
uv run python -m ocaml corpus/fact.ml
```

That should print `120` three times: `corpus/fact.ml` computes a factorial three different ways.

`uv run` builds the environment the first time and reuses it afterwards. There is nothing else to set up, because the compiler is pure Python with no dependencies at all.

### The five views, from the command line

Each of the playground's tabs is a flag:

```sh
python -m ocaml programme.ml              # run it
python -m ocaml --types programme.ml      # the types it inferred
python -m ocaml --names programme.ml      # the scopes
python -m ocaml --python programme.ml     # the Python it emits
python -m ocaml --printed programme.ml    # your source, printed back
```

Try one on a programme you know:

```console
$ python -m ocaml --types corpus/tree.ml
val insert : 'a -> 'a tree -> 'a tree
val height : 'a tree -> int
val min_elt : 'a tree -> 'a
val to_list : 'a tree -> 'a list
val summarise : int list -> stats
```

Nothing in `corpus/tree.ml` says what type anything has. All of that was worked out.

### Your own playground

To run the browser playground from your own copy:

```sh
make -C .. web-serve
```

Then open <http://localhost:8000/>. That builds the bundle and starts a small web server; press <kbd>Ctrl</kbd>+<kbd>C</kbd> to stop it.

## 3. From Python

The compiler is an ordinary package, so you can call the parts directly:

```python
from ocaml.front.parser import parse
from ocaml.middle.infer import signature
from ocaml.back.interpret import run_source
from ocaml.back.compile import compile_source

source = "let rec fact n = if n <= 1 then 1 else n * fact (n - 1)"

signature(parse(source))     # ['val fact : int -> int']
compile_source(source)       # the Python it emits, as a string
run_source(source)           # runs it, and gives back the top-level scope
```

`ocaml.pipeline.analyse(source)` runs every stage at once and hands back what each produced. Both the command line and the playground are built on it, so anything you can see in either you can get at from Python.

## The example programmes

`corpus/` holds sixty programmes, and reading a few before writing your own will save you time. Eight of them are one per chapter of a typical course:

| | |
| --- | --- |
| `sorting.ml` | sorting: insertion, selection, merge, quicksort |
| `stacks.ml` | stacks and queues, the queue amortised over two stacks |
| `divide.ml` | divide and conquer: Euclid, fast exponentiation, binary search |
| `dynamic.ml` | dynamic programming: memoisation, maximum subarray, longest common subsequence |
| `assoc.ml` | dictionaries, as association lists |
| `polynomes.ml` | polynomials: Horner, sum, product, derivative |
| `combinatoire.ml` | Hanoi, subsets, permutations, Gray code |
| `graphes.ml` | graphs: depth-first and breadth-first traversal |

Each has a `.expected` file, which is exactly what it prints. Its `.signature` file holds the types it gets. Those are not decoration: they are what the test suite compares against on every change.

Another twenty-three sit in `corpus/simonet/`, one per subject in the exercise series [Vincent Simonet](https://www.normalesup.org/~simonet/teaching/caml-prepa/index.html) set at the Lycée Janson-de-Sailly between 1998 and 2003, first year and second. They go further than the eight above: LZW compression, red-black trees, Knuth-Morris-Pratt, Thompson's construction, Barnes-Hut. `corpus/simonet/README.md` is the index. The original statements are on his site, with their solutions.

The last nineteen, in `corpus/grimaud/`, are solutions from the textbook [*Informatique MPI*](https://www.informatiquempi.fr) by Aslı Grimaud and Gilles Grimaud, copied under the GPL-3.0: strongly connected components, Kruskal, bipartite matching, automata, knapsack six ways, a calculator. They are the authors' own code, written for OCaml, so they show what a programme looks like with `Printf` and type annotations throughout. `corpus/grimaud/README.md` says where each came from and what, if anything, was changed.

## Next

- [A tour of the language](language/tour.md), if you want to start writing.
- [Using the playground](language/playground.md), for what the six views are telling you.
- [How the compiler works](compiler/index.md), if you came for that.
