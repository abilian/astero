# The middle end: names and types

The front end knows the programme is well formed. It does not know that the `x` on line 9 is the one bound on line 3, or that adding it to a string is a mistake. The middle end works out both, by two very different methods.

**Names** are derived from a declaration, and take about fifty lines.
**Types** are written out by hand, and take a thousand.

## Names, from a declaration

Every compiler asks the same handful of questions about names. Which positions introduce one? Which refer to one? Which open a new scope, and over what? Those questions have one answer per language, and astero's idea is that if you write the answer down once, the passes follow from it. Write it out inside each pass and they drift apart until one of them renames a record field it should not have touched.

So `middle/grammar.py` gives each field of each kind of node a **role**:

```python
ROLES = {
    # A pattern is what introduces a value name.
    "PVar": {"name": defines(VALS)},
    "PAlias": {"name": defines(VALS)},
    "Var": {"name": uses(VALS)},
    # Constructors, shared by variants and exceptions.
    "Variant": {"name": defines(CONS)},
    "ExnItem": {"name": defines(CONS)},
    "Construct": {"name": uses(CONS)},
    "PConstruct": {"name": uses(CONS)},
    # Record labels.
    "FieldDef": {"name": defines(FIELDS)},
    "GetField": {"label": uses(FIELDS)},
    ...
}
```

and lists which productions open a scope, and which of their fields are evaluated inside it:

```python title="src/ocaml/middle/grammar.py"
SCOPES: dict[str, tuple[Scope, ...]] = {
    "Fun": (Scope("fun", inside=("params", "body")),),
    "Case": (Scope("case", inside=("pattern", "guard", "body")),),
    # `let x = e` binds nothing over `e`, so it opens nothing. `let f x = e`
    # binds `x` over it, so it does.
    "Binding": (Scope("binding", inside=("params", "value"), when=Present("params")),),
    "For": (Scope("for", inside=("var", "body")),),
    # One layer, and not two conditioned on `recursive`. Residual 1 above is
    # why: the difference between `let` and `let rec` is not in which fields
    # of `LetIn` are inner.
    "LetIn": (Scope("let", inside=("bindings", "body")),),
}
```

The declaration is sixteen roles and five scope layers. The field names, sorts and shapes are not written here at all: `from_dataclasses` reads them off the annotations in `syntax.py`.

### What it buys

`middle/analyze.py` is about fifty lines, and none of them mentions `PVar`, `Variant` or `FieldDef`, or lists which fields hold a binding. All of that is asked for:

```python
OCAML.definitions(ns)      # which fields declare a name in this namespace
OCAML.reads(node, ns)      # which of this node's fields read one
binds_in_scope(child, ...) # what this subtree contributes to the scope around it
```

Out of that comes the whole Names view, the unbound-name check, and capture-avoiding renaming. A compiler that wrote those lists out by hand would have four copies to keep in step.

A scope layer names the fields evaluated *inside* the scope its production opens, so the resolver walks with two environments and picks per field. That one rule puts a `match` arm's pattern inside the arm and a `for` loop's index inside the loop. It also puts a function's parameters inside the function while its name stays outside.

### Five namespaces

The declaration keeps apart the same five kinds of name as OCaml:

| namespace | introduced by | used by |
| --- | --- | --- |
| `vals` | a pattern variable | a variable |
| `cons` | a variant, an exception | `Some x`, `h :: t` |
| `fields` | a record field declaration | `r.x`, `{ x = 1 }` |
| `types` | a `type` declaration | a type annotation |
| `tyvars` | a type's parameters | `'a` |

In OCaml a record label `x` and a variable `x` are unrelated, so a pass renaming the variable must not touch `r.x`. With one namespace it would, without complaint; with five it cannot.

`exception E` and `type t = E` both declare a constructor, and OCaml lets the later one shadow the earlier. Both are `def(cons)`, so shadowing needs no special case anywhere.

### Patterns bind at their leaves

In `match l with h :: t -> ...`, both `h` and `t` are new names, two levels down inside the pattern. The declaration handles that by putting the role on the **leaf** (`PVar.name` is `def(vals)`) and letting the scope entry say that the pattern field is evaluated inside the new scope. The binding then lands in the right block with no library change at all.

Python needs a walk that knows its own destructuring shapes for the same job. This language needs nothing, because the role sits on the leaf.

### Where it stops

Two things this declaration cannot say, both found by running it.

**`let` and `let rec` look the same to it.** In OCaml a plain `let p = e in b` evaluates `e` in the scope *around* the `let`, so `let x = x + 1 in ...` reads the outer `x` and `let f = fun n -> f n` is an error. Saying that needs a binding's pattern routed inside the new scope and its value routed outside. Both live in the same field of `LetIn`. `Scope.inside` names a field, so it can put both in or both out and nothing else. A condition does not reach it either: the fields that would have to differ belong to a grandchild.

The first draft of the specification proposed exactly that condition. Writing the resolver showed it changes only whether the names *also* leak outward, which is a second defect.

**A bare identifier on a scope-opening production always binds outside it.** That is what Python needs for `def f`, where the name belongs to the enclosing scope. OCaml's `for i = a to b do ... done` needs the opposite, so `For.var` holds a `PVar` node: a node can be routed into the scope, a plain string cannot.

Both are recorded in `examples/ocaml/README.md`, with the candidate fixes.

## Types, by hand

`middle/` has three files for inference, and astero contributes nothing to any of them. Its own plan marks type inference as the one front-end job it does not do; these files measure what that costs.

### unify.py: what a type is

The compiler is never told that `fact` takes an `int`. It works that out, by **unification**: start with an unknown; every time the programme uses a value, insist that its type matches how it was used. `n <= 1` says `n` is comparable to an `int`, so the unknown standing for `n` becomes `int`.

A type is one of two things. A `Var` is an unknown, which may later turn out to be something. A `Con` is a type constructor applied to arguments: `int` is `Con("int")`, `int list` is `Con("list", (int,))`, a function is `Con("->", (a, b))`, a tuple is `Con("*", ...)`. One shape for everything.

`unify(a, b)` makes two types equal or raises. It refuses a cycle, which is the **occurs check**: `let rec f x = f` would need a type containing itself. The check reports that as an error. A real defect here was found by the check *not* firing. The pattern of a recursive binding was being inferred twice, so the type the recursive call used and the type the definition got were never joined. `let rec f x = f` typed cleanly, and so did `let rec f n = if n = 0 then "" else f true`.

### prelude.py: what is already in scope

`prelude.py` lists every name a programme may use without defining it, with its type. The types are written as OCaml source and read back with this compiler's own type grammar, so the table can be checked against the manual:

```python title="src/ocaml/middle/prelude.py"
    "List.fold_left": "('a -> 'b -> 'a) -> 'a -> 'b list -> 'a",
```

It is a middle-end file because which names are in scope is settled before anything runs. `back/runtime.py` supplies a *value* for each of them; a test holds the two lists equal so neither can grow an entry the other lacks.

That test found a defect: `::` was in the parser's operator table, so `( :: )` parsed to a name no environment could ever supply. It is a constructor, as OCaml says too.

### infer.py: one rule per node

An `if` needs a `bool` condition and two branches that agree. An application `f x` needs `f` to be a function whose argument type matches `x`. A `match` needs every arm's pattern to fit the scrutinee and every arm's body to agree. Written out, that is most of the file.

Three pieces are less obvious.

**Let-polymorphism.** `let id x = x` gets `'a -> 'a`, so it can be used at `int` in one place and `string` in another. Generalizing at a `let` is what buys that.

**The value restriction.** `let r = ref []` must *not* be generalized, or the same cell could be filled with an `int` and read back as a `string`. Only a syntactic value is generalized, and a variable left ungeneralized prints as `'_weak1`, exactly as OCaml prints it.

**Nominal records and variants.** A field name determines which record type it belongs to, so the tables are looked up by label. Where two record types share a label, the type already known at that point decides, and otherwise the later declaration does, as in OCaml.

### The oracle

`ocamlc -i` prints the signature the real compiler infers for a file. Running it over the corpus and comparing, line by line, is the check:

```console
$ python -m ocaml --types corpus/tree.ml
val insert : 'a -> 'a tree -> 'a tree
val height : 'a tree -> int
val min_elt : 'a tree -> 'a
val to_list : 'a tree -> 'a list
val summarise : int list -> stats
```

Where no OCaml is installed those tests skip, which is why `.signature` files are checked in beside each programme as well. Where one is installed, `ocamlc -i` agrees with this checker on every line of every corpus programme. Getting there meant keeping type abbreviations: `type solution = float array` stays `solution` in a signature, as OCaml prints it, and unification looks inside only when it meets a type with another name.

## The numbers

| | lines of code |
| --- | --- |
| `grammar.py`, the declaration | 43 |
| `analyze.py`, everything derived from it | 52 |
| `unify.py` + `prelude.py` + `infer.py` | 908 |

Every other module in this compiler is shorter than the hand-written thing it replaces, because a declaration derives it. Inference has nothing to replace.

---

Next, in [the back ends](back.md), the tree finally does something.
