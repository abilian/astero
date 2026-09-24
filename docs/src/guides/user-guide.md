# User guide

One section per module: its purpose, its API, and when to use it.

## `grammar`: the declaration and its queries

A `Grammar` is a set of productions. Each production has named fields. Each field carries a **shape** (`ONE`, `OPT`, `SEQ`), a **sort** (what the slot holds) and a **role** (what the position does with it). Roles are listed in [Roles](../reference/roles.md).

### Declaring one

Three entry points, depending on what you already have:

```python
astero.python.build(module=my_ast)               # an AST of ast-like classes
from_dataclasses(name, classes, roles=…)         # annotated dataclasses
GrammarBuilder()                                 # field by field
```

`build` is for an AST that subclasses or mirrors Python's: roles come from astero's declaration of Python, and only the productions your module actually defines appear.

`from_dataclasses` (a module-level function in `astero.grammar`) reads names, sorts and shapes off the type annotations, so the only thing you author is the roles: one entry per production. `tests/fixtures/postpile_ir/grammar.py` is a worked example over a twelve-instruction SSA IR.

`GrammarBuilder` is the manual path, for an IR that is neither.

`Grammar.subset(names)` restricts an existing grammar to the productions you list, keeping the abstract sorts. That is how you declare a sublanguage: see the [tutorial](../tutorial.md#1-declare-the-language).

### Static queries: which *fields*

Four of them span every node of a production and return `{production: (field names,)}`:

```python
PY.positions(Kind.DEF, VARS)  # fields with a given role
PY.operands(VARS)  # fields that read a name
PY.definitions(VARS)  # fields that introduce one
PY.ident_slots(VARS)  # fields holding a bare identifier string
```

`Kind` is the role enum, in `astero.grammar`: `CHILD`, `ATTR`, `DEF`, `USE`, `DEFUSE`, `DEL`, `DECLARE`. `operands` and `definitions` are the two common cases of `positions` given a name.

The rest answer different shapes:

```python
PY.children("FunctionDef")  # tuple[Field, ...], the fields to descend into
PY.concrete("stmt")  # frozenset[str], productions of a sort
PY.with_trait("scope")  # frozenset[str], productions carrying a trait
PY.constructor("Assign")  # type, the class that builds this production
PY.check()  # list[str] of problems; [] if the grammar is sound
```

A **trait** is a free-form label, and which exist is up to the grammar: `PY` declares only `scope`, while `tests/fixtures/postpile_ir/grammar.py` declares `pure`, `terminator`, `load`, `store`, `effects` and `block`.

### Instance queries: which *values*

These take one node and return the contents of its slots:

```python
grammar.reads(node, ns)  # values in every slot of this node that reads a name
grammar.binds(node, ns)  # ... that introduces one
```

### Choosing between them

Use a static query to build a table once: "which productions must my renamer visit?" Use an instance query when you are holding a node: "what does *this* statement bind?"

The difference matters when a field's role depends on a sibling field. In one SSA IR, `AssignValue.target` is a definition when the instruction's `declare` flag is set and a use when it is not. A static table has to report the field under *both* roles, because both are possible. Only an instance query can apply the condition and give one answer.

If you find yourself writing a walk that reads a static table and then re-checks the node, you want the instance query instead.

## `rewriting`: rules over trees

```python
Pass(name, rules, strategy=…, eliminates=(…), grammar=…, stop_at=(…))
rules(block)                   # one string, one rule per line
@rewrite("pattern")            # a rule that is a function
```

`rules` takes **one** block of text and splits it into rules, so several rules are several lines of one string:

```python
rules("""
    _x + 0 => _x
    _x * 1 => _x
""")
```

Extra positional arguments are `Rule` objects; only the first argument is text. Passing a second pattern *string* is not rejected; it reaches the `Pass` unparsed and fails there.

A `Pass` is callable: `new_tree = MY_PASS(tree)`.

- **A rule is `pattern => result`.** Identifiers beginning with `_` are pattern variables.
- **A rule can be a function** instead, decorated with `@rewrite("pattern")`, when the result needs computing. It receives a `Match`, whose `.node` is the matched node, `.binds` maps each `_name` to its capture, `.env` holds whatever you passed to the pass, and `.new(cls, **fields)` builds a replacement node with the derived fields filled in.
- **Declining.** A function rule that returns `None` declines, so the next rule is tried. This is how you write "handle this shape only when some condition holds" without a guard language.
- **A rule may return a list**, which is spliced into the enclosing statement list. That is how one statement becomes three.
- **`stop_at=(ast.FunctionDef, …)`** makes the pass skip the named productions whole: neither entered nor offered to the rules. A rewrite that is local to one scope needs this, because `yield from` inside a nested function belongs to *that* generator. The one exception is the tree you call the pass on, which is offered before the traversal starts.
- **`strategy=`** is `Strategy.INNERMOST` (the default, bottom-up), `Strategy.TOPDOWN`, or `Strategy.OUTERMOST`.
- **`eliminates=(ast.AugAssign, …)`** is checked after the pass runs and raises if any remain.
- **`ctx` is recomputed for you** from the grammar's roles, so a rule never sets `Load` or `Store`.

The last point is the reason to use this over `ast.NodeTransformer`: a transformer that moves a node between a reading and a writing position must fix the context by hand, and getting it wrong produces a tree that unparses to plausible but wrong code.

## `scopes`: the scope tree and what each block binds

```python
scope_tree(tree, grammar, scopes, namespace, *, extra=…, mangle=…) -> Block
binds_in_scope(node, grammar, ns, scopes, *, stop=()) -> set[str]
names_bound_by(node, grammar, ns) -> set[str]
bound_names(value, sort=None) -> Iterator[str]
```

Three functions answer the question at three sizes: `scope_tree` for a whole module, `binds_in_scope` for one node and everything under it, `names_bound_by` for one node alone.

`scope_tree` returns a `Block` with `kind`, `name`, `bound`, `declared_elsewhere`, `children`, and `owns()`, which is `bound` minus `declared_elsewhere`. **Use `owns()`, not `bound`**: a block containing `global x` has `x` in `bound` and does not bind it.

It models Python's real rules, including `global`/`nonlocal` redirection, PEP 695 type-parameter scopes, PEP 709 comprehension inlining, and, from 3.14, PEP 649 annotation blocks (pass `siblings=astero.python.annotation_blocks(tree)`). Class-body private name mangling, where `__x` inside `class C` becomes `_C__x`, is opt-in: pass `mangle=astero.python.mangle`.

`names_bound_by` answers for a node's own fields, so a `With` reports nothing: the binding lives on the `withitem`, as an import's lives on the `alias` and an `except`'s on the `ExceptHandler`.

`binds_in_scope` does that walk. It reaches through those carriers and stops at a scope boundary, so `def f(a, b): x = 1` contributes `f` to the scope around it and a comprehension target never leaks:

```python
binds_in_scope(stmt, PY, VARS, BINDING_SCOPES)  # the subtree
binds_in_scope(stmt, PY, VARS, BINDING_SCOPES, stop=PY.concrete("stmt"))
```

The walk does not enter the productions named in `stop`, except for the node you asked about. A flow analysis visiting one statement at a time passes the statement productions, so an `if` reports what its test binds and says nothing about its branches.

**Two scope tables**, answering different questions.

| table | question it answers |
| --- | --- |
| `SCOPES` | what does CPython's `symtable` call a block? |
| `BINDING_SCOPES` | what does a name bind *over*? |

They agreed until Python 3.12, when PEP 709 stopped comprehensions opening a `symtable` block while leaving their iteration variable local to the comprehension. Pass `SCOPES` when comparing against `symtable`, `BINDING_SCOPES` when deciding whether a name is visible somewhere.

## `hygiene`: moving code without breaking names

```python
substitute(node, mapping, grammar, ns, *, scopes=…, fresh=…)
rename(node, mapping, grammar, ns)
free_names(node, grammar, ns, *, scopes=…) -> set[str]
bound_here(node, grammar, ns) -> set[str]
Fresh(prefix="_t")             # a supply of unused names
Fresh.avoiding(node, grammar)  # ... that avoids everything in a tree
```

`substitute` replaces variables with expressions. It does three things a naive walk does not:

1. **Replaces uses only.** A `Name` in a binding position is a different thing from a `Name` that reads; substituting into the first produces something that is not a program. Roles tell them apart.
2. **Refuses.** It raises `CaptureError` when the target rebinds a name you are substituting.
3. **Avoids capture**, given `fresh=`. If the expression you are inserting has a free name that some binder inside the target would capture, `substitute` renames that binder first.

`rename` is the simpler operation: change variables' names throughout, in every declared slot including the ones you would forget.

`free_names` without `scopes` treats the tree as one scope, so the first `t` of `t + sum(t for t in xs)` does not count as free. Pass `scopes=BINDING_SCOPES` when the answer decides whether moving code captures a name, as `substitute` does.

Use these when inlining a function, instantiating a macro or template, or specialising a body, anywhere an expression written in one scope is moved into another.

## `coverage`: gating a dispatch table against the language

```python
Coverage(handled, expected, accounted=…)
dispatch(grammar, registries, *, bases=(…), accounted=…) -> Coverage
handlers(registries) -> frozenset[str]      # from singledispatch registries
match_arms(*functions) -> frozenset[str]    # from `case Cls()` patterns in source
visitors(*classes) -> frozenset[str]        # from `visit_X` method names
```

A `Coverage` has `.missing`, `.absent`, `.redundant` and `.explain()`. Assert `not cover.missing` in a test.

Three readers cover the three ways a consumer enumerates a language. `handlers` reads `singledispatch` registries. `match_arms` parses the dispatcher's own source with `ast` and collects its `case` patterns, which is the only way to inspect a `match` statement, since it leaves no registry behind. `visitors` reads the `visit_<Production>` method names of an `ast.NodeVisitor`.

`visitors` reads each class's own methods along the MRO, and `dir()` is the wrong tool for it. `ast.NodeVisitor` defined `visit_Constant` through Python 3.13 and CPython dropped it in 3.14, so `dir()` reports a subclass as handling `Constant` on one interpreter and not the next, whether or not anyone wrote the method.

`accounted={"reason": {"Prod", …}}` records productions you choose not to handle, with the reason as the key. If a listed production stops existing, or gains a handler, `absent` and `redundant` report it, so the exemptions cannot go stale.

## `emit_rules`: a code generator as a table

```python
e = Emitter(grammar, levels=LEVELS, typer=get_type, fallback=…)
e.projection("sym", lambda op: SYMBOL[type(op)])
e.rule("BinOp", "{left} + {right}", All((OpIs((ast.Add,)), Both(NUMERIC))))
e.to_text(node)     # str
e.to_lines(node)    # list[str], split where a template said to break
```

**Template syntax.**

| written | meaning |
| --- | --- |
| `{field}` | emit that field, bracketed if the precedence table requires it |
| `{field?}` | the same, but emit nothing if the field is absent |
| `{field:name}` | run the projection called `name` over the value |
| `{field:, }` | join a list field with the given separator |
| `{&label}` | a label unique to this node, generated for you |
| `{{` `}}` | a literal brace |

A field holding a list joins with `", "` unless you give a separator, so `f({args})` emits `f(a, b, 1)`. A projection applied to a list maps over its elements.

**Guards**, which decide which of several rules for a production applies: `Is`, `Both`, `OpIs`, `Const` and `Has`, combined with `All`, `Either` and `Not`. Rules are tried in order and the first whose guard holds wins, so an unguarded rule goes last and acts as the default.

The vocabulary is closed on purpose. A guard that could call arbitrary host code would let a rule table become a program, which defeats the point of a table.

**Bracketing.** With `levels`, brackets are derived: each production or operator gets a `Level(power, assoc)`. A child is bracketed when its power is lower than its position requires. A production absent from the table imposes no bracketing on its children, which is why statement rules work. With `levels=None` there is no bracketing at all. Put the operator last in the template and you get post-order output, which is what a stack machine and WebAssembly's text format want.

**`fallback=`** takes a callable used for any production with no rule; it returns finished text for that node, already bracketed. It is how you convert an existing back end one production at a time, since everything unconverted still goes through your old generator. Without a fallback, a production with no matching rule raises `EmitError`.

**Where it stops.** Guards ask about a node's *type* and *shape*. Guards about an operand's provenance, such as whether it is provably a small constant or whether this operation can overflow, are a cost model and stay as code you write.

## `emit`: documents and derived brackets

`emit_rules` is built on this layer, which you can also use directly.

```python
text("x"), concat(a, b), line(), nest(doc, indent=4)   # build a document
a + b                                                  # concatenate two
render(doc, indent=0) -> str
spans(doc)                                             # (start, end, span)
Level(power, assoc), Assoc.LEFT | RIGHT | NONE, ATOM, FREE
needs_parens(inner, outer, on_right=…) -> bool
PRECEDENCE, BINOP_LEVELS, BOOLOP_LEVELS, UNARY_LEVELS   # Python's own table
```

`ATOM` is the tightest binding power and `FREE` the loosest. A production your table omits imposes `FREE` on its children, which is why a statement rule does not bracket what it holds.

A document is a tree, so indentation is the renderer's job and a source map falls out of `spans`.

`astero.python.emit` is a complete Python emitter built on this layer, exposing `emit(node)` and `emit_module(node)`. It is what the round-trip test exercises: parse the standard library, emit it, reparse, compare.

## `tables`: the tables no grammar derives

```python
Family.parse(name, matrix, normalize=None) -> Family
family.lookup(op, *types)      # the symbol for this operation on these types
family.holes()                 # cells deliberately left empty
family.check()                 # problems in the declaration
```

For an operation-by-type matrix: which runtime symbol implements a given operation on a given pair of types. `matrix` is the table as text, and `normalize` states once that (say) a `Bool` is looked up as an `Int64`. A cell written as a hole stays a hole; it never becomes a missing key at run time.

This is the one module that derives nothing from a grammar. It exists for the tables no grammar determines.

## `generate`: programs that exercise every declared position

```python
snippets() -> Mapping[str, str]
combinations(count, seed=0) -> Iterator[str]
missing_coverage(grammar, scopes, ns) -> set[str]
```

`missing_coverage` turns "have my tests exercised every role in the grammar?" into a set you can assert is empty.
