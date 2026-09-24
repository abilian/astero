# A tour of the language

Written for somebody who knows a little Python. Every example here runs in [the playground](../play/) as it stands.

OCaml is a *functional* language, which in practice means three things you will notice immediately. You give names to values; a name never changes afterwards. Functions are values like any other. The compiler works out the types, so you never write them.

## Naming things

```ocaml
let x = 42
let name = "Hypatia"
let pi = 3.14159
```

`let` introduces a name. It is not assignment: `x` is 42, and stays 42. If you write `let x = 43` afterwards you have made a *new* `x` that hides the old one. Anything that captured the first one still sees 42.

Functions are the same word:

```ocaml
let double n = 2 * n
let add a b = a + b
```

`double` takes one argument and `add` takes two. You call them without brackets or commas:

```ocaml
let quatre = double 2
let seven = add 3 4
```

Brackets are only for grouping, so `add 3 (double 2)` needs them and `add 3 4` does not. That trips everybody up once.

!!! tip "Try it"
    Put those in the playground and look at the **Types** tab. You never wrote `int` anywhere: the compiler found it.

## Types, without writing them

```console
$ python -m ocaml --types tour.ml
val double : int -> int
val add : int -> int -> int
```

Read `int -> int` as "takes an `int`, gives an `int`". `add` is `int -> int -> int`, which looks odd until you know that a two-argument function is really a function that takes one argument and gives back a function expecting the next. That is why `add 3` on its own is legal, and is a function that adds 3.

The compiler worked those out from `2 * n` and `a + b`, because `*` and `+` are integer operators. If you had written `2. *. n` it would have said `float -> float`.

**Floats have their own operators**. This is the single most common surprise in OCaml:

```ocaml
let area r = 3.14159 *. r *. r
```

`+.`, `-.`, `*.`, `/.` for floats; `+`, `-`, `*`, `/` for integers. Mixing them is a type error. `float_of_int` and `int_of_float` convert when you want it.

## Making decisions

```ocaml
let sign n = if n > 0 then "positive" else "negative"
```

`if` is an *expression*: it has a value, like Python's `a if c else b`. Both branches must have the same type, because the whole thing has one type.

For anything with more than two cases, **pattern matching** is the tool:

```ocaml
let describe n =
  match n with
  | 0 -> "zero"
  | 1 -> "one"
  | k when k < 0 -> "negative"
  | _ -> "large"
```

Each `|` is one case. `_` matches anything, and `when` adds a condition. Cases are tried top to bottom.

## Lists

A list is written with `;` between the elements, not `,`:

```ocaml
let primes = [ 2; 3; 5; 7; 11 ]
```

`,` builds a *tuple*, which is a different thing: `(1, "un")` is a pair of an `int` and a `string`.

Lists are built from two pieces: the empty list `[]`, and `::` which sticks one element on the front. So `[1; 2; 3]` really is `1 :: (2 :: (3 :: []))`, and that is why the standard way to work on a list is to match those two shapes:

```ocaml
let rec length l =
  match l with
  | [] -> 0
  | _ :: rest -> 1 + length rest
```

Note the `rec`: the function calls itself; OCaml wants you to say so.

That pattern, matching on `[]` and on `t :: rest`, is most of the first term. Here is summing:

```ocaml
let rec sum l =
  match l with
  | [] -> 0
  | t :: rest -> t + sum rest
```

!!! tip "Try it"
    Paste that into the playground and open **Names**. You will see that `t` and `rest` exist only inside the second arm. That is what a pattern does: it takes the value apart and names the pieces, for that arm only.

The library has the common ones already:

```ocaml
List.length [ 1; 2; 3 ]              (* 3 *)
List.map double [ 1; 2; 3 ]          (* [2; 4; 6] *)
List.filter (fun n -> n > 2) l       (* the elements above 2 *)
List.fold_left ( + ) 0 [ 1; 2; 3 ]   (* 6 *)
```

`fun n -> n > 2` is a function without a name. `( + )` is the addition operator used as a value, which is what the brackets are for.

## Your own types

Two kinds, and they cover almost everything.

A **sum type** lists the shapes a value can take:

```ocaml
type suit = Clubs | Diamonds | Hearts | Spades

type shape =
  | Circle of float
  | Rectangle of float * float
```

Each name starting with a capital is a *constructor*. `Circle 2.0` is a `shape`, and so is `Rectangle (3.0, 4.0)`. You take them apart by matching:

```ocaml
let area f =
  match f with
  | Circle r -> 3.14159 *. r *. r
  | Rectangle (w, h) -> w *. h
```

This is the thing OCaml is good at and Python is clumsy about. The compiler knows the list of shapes, so it can tell you when you have forgotten one.

A **record type** is a record, like a small named tuple:

```ocaml
type point = { x : float; y : float }

let origin = { x = 0.0; y = 0.0 }
let x_of p = p.x
```

Fields are read with `.`, as in Python. A field marked `mutable` can be changed:

```ocaml
type counter = { mutable value : int }

let increment c = c.value <- c.value + 1
```

`<-` is assignment, legal only on a `mutable` field. Everything else is immutable.

## Types that hold anything

```ocaml
type 'a tree =
  | Leaf
  | Node of 'a tree * 'a * 'a tree
```

`'a` is a *type variable*: a tree of anything. `int tree` is a tree of integers and `string tree` a tree of strings, from one piece of code.

The compiler puts those in for you. Write a function over trees that never looks at the values: it will tell you the function works for any tree:

```console
$ python -m ocaml --types tree.ml
val height : 'a tree -> int
```

That `'a` was not written anywhere. It was worked out.

## When you do need to change something

Most of the time you do not. When you do:

```ocaml
let counter = ref 0         (* a reference *)
let () = counter := 5       (* write *)
let n = !counter            (* read *)
```

`ref` makes a mutable cell, `:=` writes to it, and `!` reads it. Arrays are the other mutable thing:

```ocaml
let t = [| 1; 2; 3 |]
let first = t.(0)
let () = t.(0) <- 99
```

`[| ... |]` for arrays, `t.(i)` to index, and note that `[ ... ]` is a list and `[| ... |]` is an array; they are different types with different costs.

The two loops exist too:

```ocaml
let () =
  for i = 1 to 5 do
    print_int i
  done

let () =
  let n = ref 10 in
  while !n > 0 do
    n := !n - 1
  done
```

A loop's body has type `unit`, OCaml's "nothing to say" and the equivalent of Python's `None`. It is written `()`.

## Doing several things

```ocaml
let () =
  print_string "answer: ";
  print_int 42;
  print_newline ()
```

`;` puts expressions in sequence: do this, then that. The value is the last one's.

`let () = ...` at the top of a file is the idiom for "run this". It reads as a pattern match against `()`, which is exactly what it is.

## Exceptions

```ocaml
exception Empty

let first l =
  match l with
  | [] -> raise Empty
  | t :: _ -> t

let safe l = try first l with Empty -> 0
```

Declared with `exception`, thrown with `raise`, caught with `try ... with` followed by cases, exactly like a `match`.

## What is not here

There are no modules of your own, no objects and no functors. `Printf`, `Hashtbl` and `Stack` are there. The [reference card](reference.md) has the full list of what exists, including every standard-library function with its type.

## Next

- [Using the playground](playground.md), to get the most out of the six views.
- [How the compiler works](../compiler/index.md), if you now want to know how any of this is possible.
