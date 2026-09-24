"""The shape of a programme, once it has been read.

A compiler does not work on text. It works on a **tree**: `1 + 2 * 3`
becomes a node meaning "add", whose left branch is `1` and whose right
branch is a node meaning "multiply". That tree is called an *abstract
syntax tree*, and this file lists every kind of node one can contain.

Each node is an ordinary Python dataclass, so `2 * 3` is literally
`BinOp("*", Int(2), Int(3))`. There are sixty-six kinds, one per form the
language has, and you can read the whole language by scrolling this file.

Nothing here imports astero. These are the classes a compiler for this
language would have anyway, and `middle/grammar.py` describes them
afterwards. That order matters: the description is *about* the tree, so the
tree has to be able to exist without it.

`Ident` is `str` under another name. That is what lets the description
separate a field holding a *name* from a field holding text that happens to
be a string, such as `BinOp.op`.

Two shapes are worth knowing before you read the list, because they are the
ones you would otherwise expect to find and would not:

* **`::` is a constructor, so it is `Construct`.** OCaml's "cons" is a
  constructor of `'a list` and nothing else, so `h :: t` and `Some x` are
  the same kind of node. `ListLit` still exists, because `[a; b]` is a
  different piece of text and the printer has to give it back.

* **A literal pattern holds a literal expression.** `PLit(value=Int(1))`,
  rather than six pattern classes mirroring the six expression ones. Only
  the parser builds a `PLit`, and only from a literal, so the invariant
  holds where the tree is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: A field holding a name. Distinct from `str` so the declaration can say
#: which strings are identifiers and which are data.
Ident = str


#: Where a node came from: offsets into the source, start and end. The
#: stepper needs them to say which sub-expression it is evaluating, and the
#: error messages could use them to point at a line.
Span = tuple[int, int]


@dataclass
class Node:
    """Root of the hierarchy, so `concrete()` can tell abstract from real.

    Every node carries where it came from, filled in by the parser. Three
    details, all of them so that adding it changed nothing else:

    * **`kw_only`** keeps it out of the positional arguments, so a subclass
      may still declare fields without defaults after it.
    * **`compare=False`** keeps it out of `__eq__`, so the print-and-reparse
      oracle still compares shapes rather than positions. Printing loses the
      original layout, which is the point of the test.
    * **`repr=False`** keeps a tree reading as the constructor call that
      builds it.

    A node the parser did not build, one a test writes by hand or a rewrite
    produces, has no span.
    """

    span: Span | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass
class Expr(Node):
    """An expression. Every OCaml construct is one."""


@dataclass
class Pattern(Node):
    """A pattern: what `let`, `fun`, `match` and `try` bind through."""


@dataclass
class TypeExpr(Node):
    """A type expression, as written in an annotation or a declaration."""


@dataclass
class TypeRhs(Node):
    """The right-hand side of a `type` declaration."""


@dataclass
class Item(Node):
    """A structure item: a top-level definition or expression."""


# ------------------------------------------------------------------ literals


@dataclass
class Int(Expr):
    value: int


@dataclass
class Float(Expr):
    value: float


@dataclass
class Char(Expr):
    value: str


@dataclass
class Str(Expr):
    value: str


@dataclass
class Bool(Expr):
    value: bool


@dataclass
class Unit(Expr):
    """`()`."""


# --------------------------------------------------------------- expressions


@dataclass
class Var(Expr):
    """`x`, or `List.map`: the module prefix is part of the name."""

    name: Ident


@dataclass
class Construct(Expr):
    """`Some x`, `None`, `h :: t`. `args` holds the components, flattened."""

    name: Ident
    args: list[Expr] = field(default_factory=list)


@dataclass
class Tuple(Expr):
    items: list[Expr] = field(default_factory=list)


@dataclass
class ListLit(Expr):
    items: list[Expr] = field(default_factory=list)


@dataclass
class ArrayLit(Expr):
    items: list[Expr] = field(default_factory=list)


@dataclass
class FieldBind(Node):
    """One `label = value` of a record expression."""

    label: Ident
    value: Expr


@dataclass
class Record(Expr):
    """`{ x = 1 }`, or `{ r with x = 1 }` when `base` is set."""

    fields: list[FieldBind] = field(default_factory=list)
    base: Expr | None = None


@dataclass
class Apply(Expr):
    """`f x y`. Kept n-ary, so the arity the source wrote survives."""

    fn: Expr
    args: list[Expr] = field(default_factory=list)


@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass
class UnOp(Expr):
    """`-e`, `-.e`, `!e`."""

    op: str
    value: Expr


@dataclass
class If(Expr):
    cond: Expr
    then: Expr
    otherwise: Expr | None = None


@dataclass
class Seq(Expr):
    """`e1; e2; e3`."""

    items: list[Expr] = field(default_factory=list)


@dataclass
class Binding(Node):
    """One `p params = value` of a `let`, with or without an `in`."""

    pattern: Pattern
    params: list[Pattern] = field(default_factory=list)
    annot: TypeExpr | None = None
    value: Expr | None = None


@dataclass
class LetIn(Expr):
    recursive: bool
    bindings: list[Binding]
    body: Expr


@dataclass
class Fun(Expr):
    params: list[Pattern]
    body: Expr


@dataclass
class Case(Node):
    """One `| p when g -> body` of a `match`, `try` or `function`."""

    pattern: Pattern
    guard: Expr | None = None
    body: Expr | None = None


@dataclass
class Function(Expr):
    """`function | p -> e`: a one-argument function that matches."""

    cases: list[Case] = field(default_factory=list)


@dataclass
class Match(Expr):
    scrutinee: Expr
    cases: list[Case] = field(default_factory=list)


@dataclass
class Try(Expr):
    body: Expr
    cases: list[Case] = field(default_factory=list)


@dataclass
class While(Expr):
    cond: Expr
    body: Expr


@dataclass
class For(Expr):
    """`for i = a to b do body done`.

    `var` holds a `PVar` rather than an `Ident` because the index binds
    *inside* the loop, and astero routes a field to the block a scope opens
    only when the field holds a node. `grammar.py` says so at more length.
    """

    var: PVar
    start: Expr
    stop: Expr
    down: bool
    body: Expr


@dataclass
class GetField(Expr):
    """`e.label`."""

    value: Expr
    label: Ident


@dataclass
class SetField(Expr):
    """`e.label <- rhs`."""

    value: Expr
    label: Ident
    rhs: Expr


@dataclass
class ArrayGet(Expr):
    """`a.(i)`."""

    array: Expr
    index: Expr


@dataclass
class ArraySet(Expr):
    """`a.(i) <- rhs`."""

    array: Expr
    index: Expr
    rhs: Expr


@dataclass
class StringGet(Expr):
    """`s.[i]`. There is no `StringSet`: OCaml strings are immutable."""

    value: Expr
    index: Expr


@dataclass
class Constraint(Expr):
    """`(e : t)`."""

    value: Expr
    annot: TypeExpr


# ------------------------------------------------------------------ patterns


@dataclass
class PWild(Pattern):
    """`_`."""


@dataclass
class PVar(Pattern):
    name: Ident


@dataclass
class PLit(Pattern):
    """A literal pattern. `value` is one of the literal expression classes."""

    value: Expr


@dataclass
class PTuple(Pattern):
    items: list[Pattern] = field(default_factory=list)


@dataclass
class PList(Pattern):
    items: list[Pattern] = field(default_factory=list)


@dataclass
class PArray(Pattern):
    items: list[Pattern] = field(default_factory=list)


@dataclass
class PConstruct(Pattern):
    """`Some x`, `[]`, `h :: t`."""

    name: Ident
    args: list[Pattern] = field(default_factory=list)


@dataclass
class PField(Node):
    """One `label = pattern` of a record pattern."""

    label: Ident
    pattern: Pattern


@dataclass
class PRecord(Pattern):
    fields: list[PField] = field(default_factory=list)


@dataclass
class POr(Pattern):
    alternatives: list[Pattern] = field(default_factory=list)


@dataclass
class PAlias(Pattern):
    """`p as x`."""

    pattern: Pattern
    name: Ident


@dataclass
class PConstraint(Pattern):
    """`(p : t)`."""

    pattern: Pattern
    annot: TypeExpr


# ------------------------------------------------------------- type expressions


@dataclass
class TVar(TypeExpr):
    """`'a`."""

    name: Ident


@dataclass
class TCon(TypeExpr):
    """`int`, `int list`, `(int, string) table`."""

    name: Ident
    args: list[TypeExpr] = field(default_factory=list)


@dataclass
class TFun(TypeExpr):
    arg: TypeExpr
    result: TypeExpr


@dataclass
class TTuple(TypeExpr):
    items: list[TypeExpr] = field(default_factory=list)


# ----------------------------------------------------------- type declarations


@dataclass
class Variant(Node):
    """One `| C of t1 * t2` of a sum type."""

    name: Ident
    args: list[TypeExpr] = field(default_factory=list)


@dataclass
class Variants(TypeRhs):
    variants: list[Variant] = field(default_factory=list)


@dataclass
class FieldDef(Node):
    name: Ident
    annot: TypeExpr
    is_mutable: bool = False


@dataclass
class RecordDef(TypeRhs):
    fields: list[FieldDef] = field(default_factory=list)


@dataclass
class AliasDef(TypeRhs):
    """`type t = int * int`."""

    annot: TypeExpr


@dataclass
class TypeDef(Node):
    name: Ident
    params: list[Ident] = field(default_factory=list)
    rhs: TypeRhs | None = None


# ----------------------------------------------------------- structure items


@dataclass
class LetItem(Item):
    """A top-level `let`, which binds for the rest of the structure."""

    recursive: bool
    bindings: list[Binding]


@dataclass
class TypeItem(Item):
    defs: list[TypeDef] = field(default_factory=list)


@dataclass
class ExnItem(Item):
    """`exception E of t`. `E` lands in the constructor namespace."""

    name: Ident
    args: list[TypeExpr] = field(default_factory=list)


@dataclass
class ExprItem(Item):
    value: Expr


@dataclass
class Structure(Node):
    items: list[Item] = field(default_factory=list)


#: Every class the grammar is read from. The abstract bases are included so
#: `concrete("Expr")` has something to answer with.
CLASSES = [
    Node,
    Expr,
    Pattern,
    TypeExpr,
    TypeRhs,
    Item,
    Int,
    Float,
    Char,
    Str,
    Bool,
    Unit,
    Var,
    Construct,
    Tuple,
    ListLit,
    ArrayLit,
    FieldBind,
    Record,
    Apply,
    BinOp,
    UnOp,
    If,
    Seq,
    Binding,
    LetIn,
    Fun,
    Case,
    Function,
    Match,
    Try,
    While,
    For,
    GetField,
    SetField,
    ArrayGet,
    ArraySet,
    StringGet,
    Constraint,
    PWild,
    PVar,
    PLit,
    PTuple,
    PList,
    PArray,
    PConstruct,
    PField,
    PRecord,
    POr,
    PAlias,
    PConstraint,
    TVar,
    TCon,
    TFun,
    TTuple,
    Variant,
    Variants,
    FieldDef,
    RecordDef,
    AliasDef,
    TypeDef,
    LetItem,
    TypeItem,
    ExnItem,
    ExprItem,
    Structure,
]
