# 2. Working out what it means

After the front end, the compiler knows the programme is well formed. It does not know that the `t` on line 4 is the one the pattern introduced two characters earlier, or that adding it to a string would be a mistake.

Two questions. They are the reason type errors and scope errors are the two kinds of error you actually meet.

## Which definition does each name refer to?

Consider:

```ocaml
let x = 1
let f = fun () -> x
let x = 2
let y = f ()
```

What is `y`? In OCaml it is **1**. The third line does not change `x`. It makes a *new* `x` that hides the old one, while `f` still holds the one it captured. Getting that wrong is easy. This compiler did get it wrong, which [the next page](running.md) comes back to.

Answering it means knowing, for every point in the programme, which names are visible. That structure is called the **scope tree**. You can look at it:

```console
$ python -m ocaml --names sum.ml   # abridged: the first of five trees
── vals ──
module    top              {sum}
  binding                    {l}
    case                       {}
    case                       {q, t}
```

The whole file binds `sum`. The function binds `l` inside itself. The second `match` arm binds `q` and `t`, and they exist nowhere else.

### How it is worked out

`src/ocaml/middle/analyze.py`, which produces all of that, is **52 lines**. It never mentions a single kind of node: it names neither `PVar` nor `Case`, and lists none of the fields that introduce names.

It asks instead. The answers come from a separate 43-line file, `middle/grammar.py`, which describes the tree:

```python
ROLES = {
    # A pattern is what introduces a value name.
    "PVar": {"name": defines(VALS)},
    "PAlias": {"name": defines(VALS)},
    "Var": {"name": uses(VALS)},
    # Constructors, shared by variants and exceptions.
    "Variant": {"name": defines(CONS)},
    "ExnItem": {"name": defines(CONS)},
    ...
}
```

Each field of each kind of node gets a **role**: this one introduces a name, that one refers to one, this other one is just a subtree. A second table says which nodes open a new scope, and over which of their parts:

```python
SCOPES: dict[str, tuple[Scope, ...]] = {
    "Fun": (Scope("fun", inside=("params", "body")),),
    "Case": (Scope("case", inside=("pattern", "guard", "body")),),
    ...
}
```

Read the `Case` line as: a `match` arm opens a scope with its pattern, its guard and its body all *inside* it. That single line is why `q` and `t` show up in an arm's block and nowhere else.

From those two tables come the scope tree, the check for undefined names, and safe renaming. A compiler that wrote those lists out inside each pass would have three or four copies to keep in step. The classic bug is that one of them is missing a case: a renamer that handles function parameters, forgets `match` arms, and renames the wrong thing without saying so.

The library that implements that idea is [astero](https://astero.lab.abilian.com). This compiler is its worked example.

### Five kinds of name

The description keeps apart the same five sorts of name as OCaml:

| namespace | introduced by | used by |
| --- | --- | --- |
| `vals` | a pattern variable | a variable |
| `cons` | a variant, an exception | `Some x`, `h :: t` |
| `fields` | a record field | `r.x`, `{ x = 1 }` |
| `types` | a `type` declaration | an annotation |
| `tyvars` | a type's parameters | `'a` |

That is not tidiness. In OCaml a record label `x` and a variable `x` are completely unrelated, so a pass that renames the variable must leave `r.x` alone. With one namespace it would not, while nothing complained.

## What type does everything have?

You never write a type in OCaml, yet everything has one. Working it out is called **type inference**. The method is simpler than it sounds.

Start by saying "I do not know", which gives you an *unknown*. Then every time the programme uses a value, insist that its type fits how it was used, and see what the unknowns are forced to be.

For `sum`:

- `sum` takes an argument `l`, so it is `?1 -> ?2` for two unknowns.
- `match l with [] -> ...` means `l` is a list of something: `?1 = ?3 list`.
- One arm gives `0`, so `?2 = int`.
- The other gives `t + sum rest`, and `+` is integer addition, so `t` is an `int`. Since `t` came out of the pattern `t :: rest`, so `?3 = int`.

Put those together and `sum : int list -> int`. That is what the compiler prints, having done exactly that reasoning.

Making two types fit is called **unification**, the heart of `middle/unify.py`. Sometimes two types cannot fit. Those failures are your error messages:

```console
types: TypingError: this has type bool but int was expected
```

One failure looks strange the first time. `let rec f x = f` would need `f` to have a type that contains itself, forever. The **occurs check** catches it; without it the compiler would loop forever on this programme.

### Two subtleties that catch everyone

**`let id x = x` gets `'a -> 'a`** and can then be used at `int` here and `string` there. That is called *let-polymorphism*. You get a reusable function without writing anything more.

**`let r = ref []` does not.** Try it in the playground:

```ocaml
let r = ref []
```

You get `'_weak1 list ref`, not `'a list ref`. If it were `'a`, you could put an `int` in the cell in one place and read a `string` out of it in another, while the type system said nothing. Refusing to generalize here is the **value restriction**. Real OCaml does the same. The `'_weak1` in your error message is not a mistake; it is the compiler saying "one specific type, and I do not know which yet".

### Where the derivation stops

The names half of this section is derived from a 43-line description. The types half is about nine hundred lines of hand-written code that nothing derives.

That is the boundary of the idea. A declaration can say where names are introduced and where scopes open. It cannot say what unification is. `middle/infer.py`, `unify.py` and `prelude.py` are the largest part of this compiler for that reason.

## Checking it against the real thing

An inference engine that agrees with itself proves nothing. So where a real OCaml is installed, the tests run `ocamlc -i`, which prints the types the real compiler infers, and compare line by line:

```console
$ python -m ocaml --types corpus/tree.ml
val insert : 'a -> 'a tree -> 'a tree
val height : 'a tree -> int
val min_elt : 'a tree -> 'a
val to_list : 'a tree -> 'a list
val summarise : int list -> stats
```

Every one of those has to match what `ocamlc -i` says about the same file.

---

Next: [running it, twice](running.md).
