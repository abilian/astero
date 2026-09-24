# caml-prépa

**A compiler for the OCaml you learn in preparatory class, that you can look inside.**

[Open the playground](play/){ .md-button .md-button--primary }
[Start here](getting-started.md){ .md-button }

---

## What is this?

It is a real compiler for the subset of OCaml taught in French preparatory classes (*CPGE*, the two-year courses leading to the engineering-school entrance exams): `let rec`, pattern matching, lists, arrays, records, sum types, references, loops, exceptions.

You can write a programme in your browser and run it. That part is unremarkable. Plenty of sites do that.

It also shows you its working. Type a programme and it will tell you, for the same code, at the same time:

- **what it prints**
- **what type it worked out** for every definition, without being told
- **which definition each name refers to**, laid out as a tree of scopes
- **what Python it would compile to**
- **how it read what you wrote**, printed back out

Most compilers are a black box: source goes in, a result comes out, and if you are lucky an error message. This one lets you watch.

## What is in it for me?

**If you are learning OCaml**, the two things that trip everybody up are types and scope. This shows you both directly, before any error message does.

You wrote a function and OCaml says it has some type you did not expect? Ask what type it inferred, and for which sub-expression. You are not sure which `x` the `x` on line 12 refers to? The scope tree says so:

```
the whole programme          sum
  let sum · line 1           l
    match case · line 3      —
    match case · line 4      rest, t
```

That says: the file defines `sum`, `l` exists inside it, and `rest` and `t` exist inside the second `match` arm and nowhere else.

**If you are curious how a compiler works**, this one is small enough to read: about 6,600 lines of Python, laid out in the three parts a compiler course names. A front end turns text into a tree. A middle end works out what the tree means. A back end runs it. [The second tutorial](compiler/index.md) walks through all three by following one small programme.

If you can read Python, you can read this compiler.

**If you just want to try OCaml** without installing anything, the playground needs no account and no install, and works offline once it has loaded. Nothing you type leaves your browser.

## What it is not

It is not OCaml. It is a *teaching* compiler for a *teaching* subset, which says so where it differs. `int` is unbounded here and 63-bit in the real thing. A `Printf` format has to be written where it is used. A very deep recursion will run out of stack where OCaml would not. The [reference card](language/reference.md) lists the lot.

It is not an editor. It will not complete your code, colour it, or underline your mistakes: it is a text box and six answers.

If you want the real thing for coursework, install OCaml. This is for seeing how it works.

## Where to go

- **[Getting started](getting-started.md)**
  Run the playground, install it locally, use it from the command line.

- **[A tour of the language](language/tour.md)**
  What you can write, from `let` to pattern matching, for someone who knows a little Python.

- **[Using the playground](language/playground.md)**
  What each of the six views is telling you, including the one that steps through a run.

- **[How the compiler works](compiler/index.md)**
  Three parts, one small programme, followed all the way through.

---

caml-prépa is a worked example built on [astero](https://astero.lab.abilian.com), a library for deriving a compiler's handling of names from a declaration. It is open source under Apache-2.0.
