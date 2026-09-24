# Specification

This page defines the language this compiler accepts, which is called **caml-prépa** wherever it has to be told apart from OCaml. The [reference card](reference.md) is the short version for everyday use; this is the long one, for when you need to know exactly what a construct means or why the compiler refused it.

caml-prépa is OCaml as it is taught in French preparatory classes (MPSI/MP, MPI, PCSI and the computer-science option): the subset a student writes on a whiteboard. It is chosen by one test: does a first- or second-year programme use it? That admits `let rec`, pattern matching, lists, arrays, records, sum types, references, loops and exceptions, with `Printf`, `Hashtbl` and `Stack` from the standard library.

Real OCaml is the reference. Where this page and OCaml disagree, [Differences from OCaml](#differences-from-ocaml) lists the case, with the reason and the way out.

## What is left out

These are not in the subset, nor planned: modules and functors (`module`, `sig`, `struct`, `open`, `include`, `let open`, `.mli` files); objects and classes; polymorphic variants (`` `Tag ``); GADTs and existentials; labelled and optional arguments (`~x`, `?x`); first-class and recursive modules; `lazy`; extensible variants; attributes and extension nodes (`[@...]`, `[%...]`); user-defined operators; `when` on `let`; `Format`, `Seq` and `Bytes`; `external`; `nonrec`; `function` with more than one parameter.

These are reasonable to add, in this order:

1. Range patterns, `'a' .. 'z'`.
2. `open`, restricted to the standard-library modules listed [below](#the-standard-library).
3. Physical equality, `==` and `!=`.

## Lexical structure

The text is first cut into tokens, which the grammar then works on. Two of OCaml's lexical rules need code a grammar would make unreadable: comments nest, and `'a'` is a character where `'a` is a type variable.

### Whitespace and comments

Space, tab, carriage return and newline separate tokens and are otherwise ignored.

Comments are `(*` ... `*)`. They **nest**: `(* a (* b *) c *)` is one comment. A string literal inside a comment is not scanned, where OCaml scans it; see [Differences from OCaml](#differences-from-ocaml).

### Literals

| token | form |
| --- | --- |
| `INT` | `[0-9][0-9_]*`, `0x[0-9A-Fa-f_]+`, `0o[0-7_]+`, `0b[01_]+` |
| `FLOAT` | `[0-9][0-9_]*` followed by `.` and/or an exponent `[eE][+-]?[0-9]+`: `1.`, `1.5`, `1e10`, `1.5e-3` |
| `CHAR` | `'c'`, `'\n'`, `'\t'`, `'\r'`, `'\b'`, `'\\'`, `'\''`, `'\"'`, `'\065'` (decimal), `'\x41'` (hex) |
| `STRING` | `"..."` with the same escapes, plus a `\` at the end of a line to continue it |

`1.` and `1.0` are floats and `1` is an int. There is no implicit conversion, so `1 + 1.0` is a type error, as in OCaml.

### Identifiers

| token | form | what it names |
| --- | --- | --- |
| `LID` | `[a-z_][A-Za-z0-9_']*` | values, type names, record labels |
| `UID` | `[A-Z][A-Za-z0-9_']*` | constructors, exceptions, standard-library modules |
| `TYVAR` | `'` followed by `[a-z][A-Za-z0-9_']*` | type variables |

`_` alone is the wildcard, a token of its own.

The lexer tries `CHAR` before `TYVAR`. A character literal always has a closing quote and a type variable never does, so one ordered choice settles it. `'ab'` is a lexical error.

### Keywords

```
and  as  begin  do  done  downto  else  end  exception  false  for  fun  function
if  in  let  match  mod  mutable  of  rec  then  to  true  try  type  when
while  with
land  lor  lxor  lsl  lsr  asr
```

Every name of [the standard library](#the-standard-library), `not` and `raise` included, is an ordinary name bound before the programme starts, as in OCaml.

### Symbols

```
->  <-  :=  ::  ;;  ;  ,  :  |  ||  &&  =  <>  <  <=  >  >=
+  -  *  /  +.  -.  *.  /.  **  ^  @  !  _
(  )  [  ]  [|  |]  {  }  .  .(  .[
```

The lexer takes the longest run of symbol characters it can without crossing whitespace, so `a < -1` is three tokens and `a <-1` is two.

## Type expressions

The grammars on this page are written as PEG rules: `/` is an ordered choice, `?` optional, `*` any number, `+` at least one.

```peg
type        <- tuple_type ("->" type)?           # right associative
tuple_type  <- app_type ("*" app_type)*
app_type    <- atom_type type_name*              # int list, int list array
atom_type   <- TYVAR
             / "(" type ("," type)* ")"
             / type_name
type_name   <- UID "." LID / LID                 # Hashtbl.t, list
```

A type constructor applied after its argument binds tightest, then `*`, then `->`: `int -> int list * bool` is `int -> ((int list) * bool)`.

A bracketed list of two or more types is only valid as the argument of a type constructor, as in `(int, string) Hashtbl.t`. The grammar accepts `(int, string)` standing alone and the type checker rejects it.

Type declarations:

```peg
typedef     <- type_params? LID "=" type_rhs
type_params <- TYVAR / "(" TYVAR ("," TYVAR)+ ")"
type_rhs    <- variants / record_type / type
variants    <- "|"? variant ("|" variant)*
variant     <- UID ("of" tuple_type)?
record_type <- "{" field_decl (";" field_decl)* ";"? "}"
field_decl  <- "mutable"? LID ":" type
```

A constructor takes no argument or one: `of int * string` declares one argument that is a pair, as in OCaml. A declaration whose right-hand side is a type, `type word = char list`, is an **abbreviation**: `word` and `char list` are the same type. The compiler prints the name you wrote.

## Patterns

```peg
pattern      <- or_pat ("as" LID)*
or_pat       <- tuple_pat ("|" tuple_pat)*
tuple_pat    <- cons_pat ("," cons_pat)*
cons_pat     <- app_pat ("::" cons_pat)?         # right associative
app_pat      <- UID atom_pat? / atom_pat
atom_pat     <- "_"
              / LID
              / pat_literal
              / "(" pattern (":" type)? ")"
              / "(" ")"
              / "[" (pattern (";" pattern)* ";"?)? "]"
              / "[|" (pattern (";" pattern)* ";"?)? "|]"
              / "{" field_pat (";" field_pat)* ";"? "}"
field_pat    <- LID ("=" pattern)?
pat_literal  <- INT / FLOAT / CHAR / STRING / "true" / "false"
              / "-" INT / "-" FLOAT
```

`as` binds loosest, then `|`, then `,`, then `::`, then a constructor applied to its argument. A record pattern may name some of the fields only. `{ x }` is short for `{ x = x }`.

Every alternative of an or-pattern must bind the same names at the same types. The type checker holds that; the grammar does not.

## Expressions

### Precedence

Tightest first. The table is OCaml's, restricted to the operators the subset has.

| level | forms | associativity |
| --- | --- | --- |
| 1 | `!e` | prefix |
| 2 | `e.l`, `e.(i)`, `e.[i]` | postfix, left |
| 3 | `f x`, `C x` | left |
| 4 | `-e`, `-.e` | prefix |
| 5 | `**` `lsl` `lsr` `asr` | right |
| 6 | `*` `/` `*.` `/.` `mod` `land` `lor` `lxor` | left |
| 7 | `+` `-` `+.` `-.` | left |
| 8 | `::` | right |
| 9 | `@` `^` | right |
| 10 | `=` `<>` `<` `<=` `>` `>=` | left |
| 11 | `&&` | right |
| 12 | `\|\|` | right |
| 13 | `,` | n-ary |
| 14 | `:=` `<-` | right |
| 15 | `if` `while` `for` | prefix, extends right |
| 16 | `;` | right |
| 17 | `let ... in`, `fun`, `function`, `match`, `try` | extends right |

Two consequences catch students out:

* `-x ** 2` is `(-x) ** 2`: prefix minus binds tighter than `**`.
* `1 + 2 :: l @ m` is `((1 + 2) :: l) @ m`: `::` binds tighter than `@` and looser than `+`.

Levels 5 to 12 are one table in the compiler, `LEVELS` in `front/parser.py`. The parser builds its rules from it and the printer decides its brackets from it, so the two cannot disagree.

### Grammar

```peg
seq_expr   <- expr (";" expr)* ";"?
expr       <- let_expr / fun_expr / function_expr / match_expr / try_expr
            / if_expr / while_expr / for_expr / assign_expr

let_expr      <- "let" "rec"? binding ("and" binding)* "in" seq_expr
fun_expr      <- "fun" atom_pat+ "->" seq_expr
function_expr <- "function" cases
match_expr    <- "match" seq_expr "with" cases
try_expr      <- "try" seq_expr "with" cases
if_expr       <- "if" seq_expr "then" expr ("else" expr)?
while_expr    <- "while" seq_expr "do" seq_expr "done"
for_expr      <- "for" LID "=" seq_expr ("to" / "downto") seq_expr
                 "do" seq_expr "done"

cases      <- "|"? case ("|" case)*
case       <- pattern ("when" seq_expr)? "->" seq_expr
binding    <- pattern atom_pat* (":" type)? "=" seq_expr

assign_expr <- tuple_expr ((":=" / "<-") assign_expr)?
tuple_expr  <- or_expr ("," or_expr)*
or_expr     <- and_expr ("||" and_expr)*
and_expr    <- cmp_expr ("&&" cmp_expr)*
cmp_expr    <- concat_expr (cmp_op concat_expr)*
concat_expr <- cons_expr (("@" / "^") concat_expr)?
cons_expr   <- add_expr ("::" cons_expr)?
add_expr    <- mul_expr (add_op mul_expr)*
mul_expr    <- pow_expr (mul_op pow_expr)*
pow_expr    <- neg_expr (pow_op pow_expr)?
neg_expr    <- ("-" / "-.") neg_expr / apply_expr
apply_expr  <- access_expr access_expr*
access_expr <- prefix_expr postfix*
postfix     <- "." LID / ".(" seq_expr ")" / ".[" seq_expr "]"
prefix_expr <- "!" prefix_expr / atom_expr

atom_expr  <- INT / FLOAT / CHAR / STRING / "true" / "false"
            / "(" ")"
            / UID "." LID                         # List.map
            / UID                                 # a constructor
            / LID
            / "(" seq_expr (":" type)? ")"
            / "begin" seq_expr "end"
            / "[" (expr (";" expr)* ";"?)? "]"
            / "[|" (expr (";" expr)* ";"?)? "|]"
            / "{" record_expr "}"
record_expr <- seq_expr "with" field_bind (";" field_bind)* ";"?
             / field_bind (";" field_bind)* ";"?
field_bind  <- LID ("=" expr)?
```

The bodies of `let ... in`, `fun`, a `match` case, `while` and `for` are `seq_expr`, so `match n with 0 -> f (); g () | _ -> ()` puts both calls in the first case. The branches of `if` are `expr`, so `if c then a; b` is `(if c then a); b`, and `if a then if b then c else d` gives the `else` to the inner `if`. All three are OCaml's readings. They come out of the grammar with no precedence declaration: a PEG repetition takes as much as it can, while its choices are tried in order.

### The tree

The parser builds plain Python dataclasses, defined in `src/ocaml/syntax.py`:

```
Expr    = Int | Float | Char | Str | Bool | Unit
        | Var(name)                              # x, List.map
        | Construct(name, args)                  # Some x, None
        | Tuple(items) | ListLit(items) | ArrayLit(items)
        | Record(fields, base)                   # { r with x = 1 }
        | Apply(fn, args)                        # f x y
        | BinOp(op, left, right) | UnOp(op, value)
        | If(cond, then, otherwise)
        | Seq(items)
        | LetIn(recursive, bindings, body)
        | Fun(params, body) | Function(cases)
        | Match(scrutinee, cases) | Try(body, cases)
        | While(cond, body) | For(var, start, stop, down, body)
        | GetField(value, label) | SetField(value, label, rhs)
        | ArrayGet(array, index) | ArraySet(array, index, rhs)
        | StringGet(value, index)
        | Constraint(value, annot)

Pattern = PWild | PVar(name) | PLit(value) | PTuple(items) | PList(items)
        | PArray(items) | PConstruct(name, args) | PRecord(fields)
        | POr(alternatives) | PAlias(pattern, name) | PConstraint(pattern, annot)

TypeExpr = TVar(name) | TCon(name, args) | TFun(arg, result) | TTuple(items)

Item    = LetItem(recursive, bindings) | TypeItem(defs) | ExnItem(name, args)
        | ExprItem(value)
```

`Apply` takes all its arguments at once. A `Binding` keeps its parameters: `let f x y = e` is not rewritten to `let f = fun x y -> e`. Both keep the number of arguments the source wrote, which is what lets the Python back end turn `f a b` into a direct call `f(a, b)`.

## Programmes

```peg
structure   <- ";;"? (item ";;"?)* EOF
item        <- "let" "rec"? binding ("and" binding)*
             / "type" typedef ("and" typedef)*
             / "exception" UID ("of" tuple_type)?
             / seq_expr
```

`;;` is optional everywhere and changes nothing. A top-level `let` without `in` defines its names for the rest of the programme.

## Names

Which definition a name refers to is worked out from a short declaration in `middle/grammar.py`, with nothing about it written out by hand: [Working out what it means](../compiler/meaning.md) shows how.

### Five kinds of name

The compiler keeps apart the same five kinds of name as OCaml:

| namespace | introduced by | used by |
| --- | --- | --- |
| `vals` | a variable in a pattern | a variable |
| `cons` | a variant constructor, an `exception` | `Some x`, `h :: t`, a constructor pattern |
| `fields` | a record field declaration | `r.x`, `r.x <- v`, `{ x = 1 }`, `{ x }` |
| `types` | a `type` declaration | a type name |
| `tyvars` | a declaration's parameters, and `'a` in an annotation | `'a` |

A record field `x` and a variable `x` are unrelated, so renaming one never touches the other.

Constructors and exceptions share a namespace because OCaml shares it: `exception E` declares a constructor of type `exn`, which hides a variant constructor `E` declared earlier.

### Where a name is visible

Every variable in a pattern is bound, however deep: in `match l with h :: t -> ...`, both `h` and `t`. Each of these constructs opens a scope, with the parts listed inside it:

| construct | inside its scope |
| --- | --- |
| `fun p1 p2 -> e` | the parameters and the body |
| a `match` or `try` case | the pattern, the guard and the body |
| `let f p1 p2 = e` | the parameters and the right-hand side |
| `for i = a to b do e done` | the loop variable and the body |
| `let ... in b` | the bindings and the body |

`let x = e` without parameters opens no scope of its own: it binds nothing over `e`. The names a top-level `let` defines are visible in everything after it.

In a type annotation on a value, `(l : 'a list)`, a type variable introduces itself, as in OCaml. In a type or exception declaration, `type t = 'a list` is an error: every type variable must be one of the declaration's parameters.

### Where the model is approximate

**`let` sees its own name.** In OCaml, `let x = x + 1 in ...` reads the *outer* `x`; only `let rec` makes the name visible in its own right-hand side. The compiler's scope model treats the two alike, so its Names view shows the inner `x` in scope on the right-hand side of a plain `let`. The type checker and both back ends handle it correctly; only the scope trees are approximate. The declaration says which parts of a construct are inside its scope. A binding's pattern and its right-hand side are one part of `let ... in`, so they are inside together or outside together.

**Type variables are programme-wide in the scope trees.** A declaration's parameters are not placed in a scope of their own. The type checker enforces the rule above; the Names view does not show it.

### What is checked

* Every name refers to a definition in an enclosing scope, or it is reported unbound.
* A constructor is applied to as many arguments as it was declared with.
* Every alternative of an or-pattern binds the same names.
* A record pattern or record expression names declared fields only.

## Typing

The type system is Hindley–Milner, with the parts of OCaml's that a preparatory-class course relies on:

* **Inference.** No annotation is needed anywhere. Types are worked out by unification, with an occurs check, so `let rec f x = f` is rejected as a cyclic type.
* **Let-polymorphism.** A definition made with `let`, at the top level or inside, is generalized: `let id x = x` has type `'a -> 'a` and can be used at `int` in one place and `string` in another.
* **The value restriction.** `let r = ref []` must not be generalized, or the same cell could be filled with an `int` and read as a `string`. Only a syntactic value is generalized: a literal, a variable, a function, a constructor applied to values, a tuple or list of values. A variable left ungeneralized prints as `'_weak1`, as OCaml prints it.
* **Recursion.** Inside its own `let rec`, a function is monomorphic; it is generalized afterwards. A group joined by `and` is generalized together.
* **The types.** `int`, `float`, `char`, `string`, `bool`, `unit` and `exn`; `list`, `array`, `ref` and `option`; `Stack.t` and `Hashtbl.t`; your own variants, records and abbreviations, with their parameters; functions and tuples.
* **Records and variants are nominal.** A field name or a constructor determines the type. When two record types share a field name, the type already known where the field is used decides, as in `(p : processor).id`; otherwise the latest declaration that has every field the expression names.
* **Abbreviations keep their names.** After `type solution = float array`, a function annotated to return a `solution` has that type in its signature, where `float array` would be the same type spelled differently. An annotation gives the type it names, on a parameter, on a result or in `(e : t)`.
* **Formats.** `Printf.printf` has OCaml's type, `('a, out_channel, unit) format -> 'a`. A string literal passed to it is read as a format: `Printf.printf "%d: %s\n"` expects an `int` and then a `string`. The directives are `%d %i %u %x %X %o %s %c %f %F %e %E %g %G %b %B`, with flags, a width and a precision, plus `%%` and `%!`.

Subtyping, row polymorphism and module types are absent.

`match` exhaustiveness is not checked. In OCaml it is a warning.

## Evaluation

The values are integers, floats, characters, strings, booleans, `()`, tuples, lists, arrays, records, constructed values, functions and exceptions.

* **Mutation.** Lists, tuples, strings and fields not declared `mutable` cannot be changed. Arrays, `mutable` fields and `ref` cells can.
* **`ref` is a record.** `'a ref` is `{ mutable contents : 'a }`, over which `!`, `:=`, `incr` and `decr` are ordinary functions.
* **Equality.** `=` is structural and goes all the way down. Comparing two functions raises `Invalid_argument`. `<`, `<=`, `>` and `>=` work on `int`, `float`, `char` and `string` only.
* **Order.** The arguments of an application are evaluated left to right. OCaml leaves the order unspecified; its compiler goes right to left.
* **Exceptions.** `raise e` unwinds to the nearest enclosing `try ... with` that has a matching case. `Not_found`, `Failure of string`, `Invalid_argument of string`, `Division_by_zero`, `End_of_file`, `Exit` and `Assert_failure` are predefined. An uncaught exception ends the programme with a message and a non-zero exit status.
* **Pattern matching.** Cases are tried in order. The first whose pattern matches and whose guard holds is taken. A `match` with no matching case raises `Match_failure`.
* **Recursion.** OCaml runs a call in tail position without using stack. Here every call uses some, so a loop written as recursion can run out: see [Differences from OCaml](#differences-from-ocaml).

The interpreter, `back/interpret.py`, is the reference for this section: where the two disagree, one of them is wrong. How values are represented in Python is in [Running it, twice](../compiler/running.md).

## The standard library

Bound before the programme starts, unqualified:

```
not  ref  !  :=  incr  decr  ignore  fst  snd  compare  min  max  abs  succ  pred
raise  failwith  invalid_arg  assert
print_int  print_float  print_char  print_string  print_newline  print_endline
read_int  read_float  read_line
string_of_int  int_of_string  string_of_float  float_of_string
string_of_bool  bool_of_string  float_of_int  int_of_float
char_of_int  int_of_char  truncate
sqrt  exp  log  sin  cos  tan  atan  floor  ceil  abs_float
infinity  neg_infinity  max_int  min_int
```

Qualified:

* `List`: `length hd tl nth rev append concat map rev_map iter mapi iteri fold_left fold_right filter exists find filter_map for_all mem assoc split combine sort init`
* `Array`: `length make init make_matrix get set copy sub append of_list to_list iter iteri map fold_left sort blit fill`
* `String`: `length get sub concat make init index contains uppercase_ascii lowercase_ascii split_on_char compare`
* `Char`: `code chr escaped lowercase_ascii uppercase_ascii`
* `Printf`: `printf sprintf`
* `Stack`: `create push pop top is_empty length`
* `Hashtbl`: `create add replace remove find find_opt mem length`, with keys compared by structure, as OCaml compares them
* `Random`: `int self_init init`
* `Float`: `pi exp cos sin tan`
* `Sys`: `argv`, which holds the programme's name and nothing after it

There is no module system: `List.map` is one name with a dot in it, as `Hashtbl.t` is one type name. The [reference card](reference.md) gives every one of these with its type, read off the compiler when the page is built.

## Differences from OCaml

Each one is a decision, with the reason and the way out.

| difference | why | the way out |
| --- | --- | --- |
| `int` is unbounded, where OCaml's has 63 bits and wraps | masking every operation costs a call per operator in the Python back end, and no preparatory-class programme relies on wrapping | mask at the arithmetic operators |
| arguments are evaluated left to right, where `ocamlc` goes right to left | left to right is free in Python, and OCaml leaves the order unspecified, so no correct programme can tell | evaluate arguments into temporaries, in the chosen order |
| a string literal inside a comment is not scanned | nested comments are what matters, and `(* "*)" *)` is not something a student writes | scan strings in the comment lexer |
| a tail call uses stack | Python has no tail-call elimination; the recursion limit is raised to 10,000 Python frames, a few per OCaml call | turn self-recursive tail calls into loops, and use a trampoline for mutual recursion if a programme needs one |
| `<` and friends work on `int`, `float`, `char` and `string` only | ordering closures and cyclic values is runtime machinery the subset does not need | implement OCaml's structural ordering |
| `==` and `!=` are absent | physical equality on immediate values depends on the implementation; courses do not use it | add both, with a stated answer for immediates |
| `match` exhaustiveness is not checked | a warning in OCaml, and a decision procedure here | implement the usefulness algorithm |
| `C _` does not match a constructor that takes several arguments | the checker counts argument patterns; a lone `_` is one | let a single `_` stand for all the arguments |
| `if` may not appear unbracketed to the right of a binary operator | the operator levels end at a primary expression, and `if` is not one | let the loosest level accept `if`, `match`, `fun` and `try` on its right |
| the variable of a `for` loop may not be `_` | the parser reads an identifier there | read a pattern, and allow `_` |
| `assert` is a function of type `bool -> unit`, so `assert false` is not of every type | OCaml's `assert` is a keyword with a typing rule of its own; the corpus uses it only on conditions | make `assert` a keyword, and give `assert false` a fresh type |
| a format must be written where it is used | a string literal is read as a format only as the argument of a function expecting one; bound by `let` first, it is a `string`, and OCaml accepts that | read a literal as a format wherever the expected type says so |
| `Random` draws other numbers than OCaml's, seeded or not | it is Python's generator | implement OCaml's LXM generator |

## How it is checked

Every stage is compared against something that is not itself:

| stage | checked against |
| --- | --- |
| reading | the tree printed and read back, which must give the same tree |
| names | every corpus programme resolves, and scope trees are compared by shape |
| types | `ocamlc -i`, signature by signature |
| running | the real `ocaml`, output compared |
| compiling | the interpreter, over the same runtime |

The corpus is sixty programmes, each checked in beside what it prints and the signature it infers. Every construct of the grammar appears in at least one of them. A test fails otherwise: a construct no programme writes does not belong in the subset. With OCaml 5.5.0 installed, `ocaml` prints for every one of them what both back ends print, and `ocamlc -i` infers the same signatures, line for line. [Getting started](../getting-started.md) describes the corpus.
