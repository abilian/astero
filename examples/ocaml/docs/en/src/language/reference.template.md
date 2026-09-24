# Reference card

Everything the subset has, on one page.

!!! note "Three of these tables are generated"
    The operators, the keywords and the standard library are read off the
    compiler itself when this page is built, so they cannot fall behind it.
    The prose around them is written by hand.

## Definitions

```ocaml
let x = 42
let f x y = x + y                     (* two parameters *)
let rec fact n =                      (* rec, for a recursive call *)
  if n <= 1 then 1 else n * fact (n - 1)
let rec even n = ... and odd n = ...  (* mutual recursion *)
let () = print_int (fact 5)           (* run something *)
let a, b = 1, 2                       (* a pattern binds *)
let g x = let y = x * 2 in y + 1      (* local, with `in` *)
```

## Types

```ocaml
int  float  char  string  bool  unit  exn
'a list        'a array       'a option      'a ref
int * string                          (* a pair *)
int -> int -> int                     (* a function of two arguments *)

type colour = Red | Green | Blue
type 'a tree = Empty | Node of 'a tree * 'a * 'a tree
type point = { x : float; mutable y : float }
type number = int                     (* an alias *)
exception Empty
exception Too_big of int
```

A constructor takes one argument, and `of int * string` makes that argument a pair. `mutable` is what lets a field be assigned with `<-`.

## Expressions

```ocaml
if c then a else b                    (* both branches, same type *)
match e with | p -> a | q when g -> b
function | p -> a | q -> b            (* a function that matches *)
fun x y -> e                          (* anonymous *)
try e with Empty -> a | Failure m -> b
while c do e done
for i = 0 to n - 1 do e done          (* `downto` counts back *)
a; b                                  (* a is evaluated for its effect *)
begin a; b end                        (* the same, bracketed *)
[ 1; 2; 3 ]      1 :: rest       l1 @ l2
[| 1; 2; 3 |]    t.(i)           t.(i) <- v
s.[i]            "bon" ^ "jour"
{ x = 1.0; y = 2.0 }    p.x      p.y <- 3.0    { p with x = 0.0 }
let r = ref 0 in r := !r + 1; incr r
```

## Patterns

```ocaml
_                    x                    42        'a'       "s"
(a, b)               a :: rest            []        [ a; b ]  [| a; b |]
Node (l, v, r)      Some x               None
{ x = a; y = b }     p as whole            0 | 1 | 2
```

Every alternative of a `|` pattern has to bind the same names, and a case may carry a guard: `| n when n < 0 -> ...`.

## Operators

Tightest first. Application binds tighter than any of them, and prefix `-`, `-.` and `!` tighter still.

<!--OPERATORS-->

The `.` forms are for floats: `1 + 2` and `1.0 +. 2.0`, and never the two mixed. `=` is structural equality, `<>` its negation, and `:=` writes through a `ref`. Any of them can be used as a value by bracketing it, as in `List.fold_left ( + ) 0`.

## Keywords

<!--KEYWORDS-->

## The standard library

Everything a programme may use without defining it, with the type it has. There is no `open`: a module name is a prefix.

<!--STDLIB-->

## Deliberate differences from OCaml

| | here | real OCaml |
| --- | --- | --- |
| `int` | unbounded | 63-bit, and it wraps |
| argument order | left to right | unspecified |
| `<` and friends | `int`, `float`, `char`, `string` | any type |
| tail calls | use stack | use none |
| `==` and `!=` | absent | physical equality |
| exhaustiveness of `match` | not checked | a warning |
| a string inside a comment | not scanned | scanned |
| `assert false` | of type `unit` | of any type |
| `Random` | Python's generator | OCaml's, so other numbers |

Each of those is a decision with a way out, which [the specification](specification.md#differences-from-ocaml) gives.

## Not in the subset

Modules, functors, objects, classes, GADTs, polymorphic variants, labelled and optional arguments, first-class modules, `lazy`, and user-defined operators.

`Printf`, `Hashtbl` and `Stack` are here, for the functions listed above. A `Printf` format is typed from its directives, `%d`, `%s`, `%f`, `%.2f`, `%c`, `%b` and their widths, as OCaml types it, and it has to be the literal string passed to `printf`: bound by `let` first, it is only a string.
