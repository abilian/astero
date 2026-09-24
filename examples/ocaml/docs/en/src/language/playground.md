# Using the playground

[Open it](../play/), then come back here when something is puzzling.

The **Programme** list loads any of the sixty worked examples and runs it straight away. Edit the source and the views dim, because they describe the old version: press **Run**, or <kbd>Ctrl</kbd> or <kbd>⌘</kbd> + <kbd>Enter</kbd>, to bring them up to date. **Run** is greyed out while there is nothing new to run.

Everything happens in your browser. The page uploads nothing, stores nothing, and needs no OCaml on the far end: the compiler is written in Python, which runs in your tab.

## The six views

### Run

What the programme prints.

A programme with no `let () = ...` prints nothing, and that is fine: half the examples only define functions. If you want to see something, add a line:

```ocaml
let () = print_int (fact 5)
```

The status line, top right, says **both back ends agree** when it went well.

Your programme is executed *twice*. Once by walking the syntax tree, and once by compiling it to Python and running that. The two back ends are independent and share one runtime. The line reports whether they printed the same thing. This is the project's own correctness test, running on whatever you typed. It has caught real defects; see [running it, twice](../compiler/running.md).

### Types

This view shows the signature the compiler inferred, in the form the real `ocamlc -i` prints. Nothing in your source says what type anything is; all of it was worked out.

A type variable written `'_weak1` has **not** been generalized. That is not a bug. Try it:

```ocaml
let r = ref []
```

You get `'_weak1 list ref`, not `'a list ref`. If it were `'a`, the same cell could be filled with an `int` in one place and read back as a `string` in another, which would make the type system unsound. Refusing to generalize is called the *value restriction*; real OCaml does exactly the same.

### Names

This view draws the scope tree, one per namespace. It is the view no other OCaml playground has.

Each line is a part of the programme that opens a scope, with the line it starts on and the names it introduces there:

| label | what it is |
| --- | --- |
| the whole programme | the top level of the file |
| let `f` | the parameters of the function `f` |
| match case | one arm of a `match`, `function` or `try` |
| fun | the parameters of an anonymous function |
| let … in | the body of a `let ... in` |
| for loop `i` | a loop and its index |

Click a line to select it in the source.

Reading it answers the questions people actually get stuck on. Which `x` does this `x` refer to? Does this recursive call resolve? Does that parameter escape the function? The tree says so, without you having to reason it out.

There is one section per kind of name, because OCaml keeps five apart: values, constructors, record fields, type names and type variables. A record label `x` and a variable `x` are unrelated names in OCaml, so they are in different sections. Constructors and exceptions share one, because OCaml shares it. A section with nothing in it is left out.

Anything the compiler could not find is listed above the trees.

### Python

What the second back end emits. It is meant to be readable: `let f x y = ...` becomes `def f(x, y)` and a call with both arguments becomes a direct call.

Where you see `_rt.BINARY_OPS['/']` in place of a plain `/`, the two languages disagree. OCaml's integer division truncates towards zero and Python's rounds down, so `(-7) / 2` is `-3` in OCaml and `-4` in Python. `=` is structural equality, which is not Python's `==` either. Where they agree, the operator is emitted directly, which is why the arithmetic mostly reads normally.

Names get freshened, so a shadowing `let x = ...` comes out as `x_2`. That is what keeps an earlier closure reading the `x` it captured.

### Read back

Your source, printed back out of the tree the compiler built. It is how you check that it read what you meant: if a bracket appears that you did not type, the grouping was not what you thought.

Try `1 + 2 * 3` and then `1 + 2 :: l @ m`, and see where the brackets land.

### Step

The other five answer a question about the whole programme. This one takes the programme apart.

Opening it runs your code once with every evaluation recorded, and then you walk through that recording with the buttons or with <kbd>←</kbd> and <kbd>→</kbd>. Going **back** works because the run already happened: it reads the list from the other end.

Each step shows:

- **The sub-expression being evaluated**, marked in the source. Yellow on the way in, green on the way out, when it has produced a value.
- **The names in scope**, nearest scope first, with what each one holds. Functions are listed last, because the two names holding data are the ones you came for.
- **The mutable cells**, kept apart from the names. `let s = r` makes two names for one cell, and assigning through `r` changes what `s` reads. One row with both names on it is what that looks like.
- **The call stack and the scope**: `top ▸ sum ▸ sum`, and `top ▸ binding ▸ case`. The second is the block the **Names** view draws, read from the same declaration, so the two cannot disagree.
- **The emitted Python**, at the nearest point where it had printed as much. The two back ends take different steps, with no exact correspondence between them. They share the output, which therefore lines them up.
- **What has been printed so far.**

**↳** and **↰** step into and out of a *function call*, skipping the sub-expressions in between. That is what a debugger means by them: what you want when the recursive call is the thing you are chasing. **Run to cursor** jumps to the first step inside whatever you clicked in the source.

A long run stops recording after five thousand steps and says so. The programme still finishes; only the recording stops.

## Sharing

The address bar always names what is on the page. A worked example as it stands has a short link, such as `#example=fact`. Once you edit it, the address loses its `#` part until you press **Copy link**, which puts your whole programme into the URL after `#z=`, compressed, and copies it. Anybody opening that link sees your code.

Nothing is stored anywhere; the programme travels in the link itself, so a long programme still makes a long link, about a third of its length in characters.

## When something goes wrong

Problems appear in a red band above the views, prefixed by the stage that found them.

`syntax: 3:14: expected … found …`
:   The parser stopped at line 3, column 14, and lists everything that could have come next. Usually a missing `in`, a missing `->`, or a `,` where a `;` was wanted.

`names: 'foo' is not declared in vals`
:   A name nothing defines. Check the spelling, and check that the `let` defining it comes *earlier* in the file: order matters at the top level.

`types: TypingError: this has type … but … was expected`
:   Two types had to be the same and were not. The commonest cause by a distance is mixing `int` and `float`: OCaml has `+` and `+.` and they are different operators.

`interpreter: OCamlError: …`
:   The programme raised an exception nothing caught, exactly as the real `ocaml` would end.

A stage that fails does not stop the others. A programme that does not type still runs and still shows its scopes. That is often the fastest way to find out what went wrong: look at **Names** to see what the compiler thinks is in scope.

## What is not here

There is no editor. Nothing completes your code, colours it, or underlines your mistakes: it is a text box and six answers.

Modules of your own, objects and functors are missing. The [reference card](reference.md) lists what there is.

Long-running programmes freeze the tab, because everything runs on one thread. Reload the page to stop one.
