"""The grammar: what a programme is allowed to look like.

`specification.md`, from *Type expressions* to *Programmes*, is this file in
prose, rule for rule. Each rule says what one piece of the language is made
of, using the combinators from `peg.py`, and reads close to the notation a
textbook would use:

    seq_expr   <- expr (";" expr)*
    expr       <- let_expr / fun_expr / ... / assign_expr
    if_expr    <- "if" seq_expr "then" expr ("else" expr)?

astero does not parse, so this is the part you write yourself for your own
language. It is here because a tutorial that started from a tree would
leave that boundary vague.

Three places are worth reading, because they are where the ordered-choice
style does work that an older parser generator needs a precedence table
for:

* **`LEVELS`** is the operator table of `specification.md`, *Precedence*, and `_level`
  builds the cascade from it. Writing the ten near-identical rules out
  would be the alternative.
* **`expr` puts the right-extending forms first.** `let ... in`, `fun`,
  `match` and `try` take a `seq_expr` body, so they run to the end of what
  follows. That is OCaml's rule, and it is what greedy repetition does by
  default.
* **`if_expr` takes `expr` branches and a `seq_expr` condition**, which is
  why `if c then a; b` means `(if c then a); b` while
  `match x with A -> a; b` puts both in the arm.
"""

from __future__ import annotations

import operator
from typing import Any

from ocaml import syntax as s

from .lexer import tokenize
from .peg import (
    Rule,
    act,
    alt,
    guard,
    kind,
    lit,
    many,
    many1,
    not_,
    one_of,
    opt,
    run,
    sep1,
    seq,
)

# Rules referred to before they are defined, which in a grammar is most of
# them. `Rule` also memoizes, which is what keeps the cascade linear.
type_ = Rule("type")
pattern = Rule("pattern")
atom_pat = Rule("atom_pat")
cons_pat = Rule("cons_pat")
expr = Rule("expr")
seq_expr = Rule("seq_expr")
assign_expr = Rule("assign_expr")
neg_expr = Rule("neg_expr")
prefix_expr = Rule("prefix_expr")
atom_expr = Rule("atom_expr")

#: What a pair of brackets held. `seq` keeps every part it matched, and a
#: bracketed rule wants the one in the middle.
_inner = operator.itemgetter(1)
_first = operator.itemgetter(0)

#: The binary operators of section 5, loosest first. `_level` builds one
#: rule per row, and `::` is folded into a `Construct` because in OCaml it
#: is a constructor rather than an operator.
LEVELS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("||",), "right"),
    (("&&",), "right"),
    (("=", "<>", "<", "<=", ">", ">="), "left"),
    (("@", "^"), "right"),
    (("::",), "right"),
    (("+", "-", "+.", "-."), "left"),
    (("*", "/", "*.", "/.", "mod", "land", "lor", "lxor"), "left"),
    (("**", "lsl", "lsr", "asr"), "right"),
)


#: Every operator that can be written as a value, `( + )`. Derived from
#: `LEVELS` rather than listed again, so a new row cannot be forgotten here.
#:
#: `::` is the exception, and not an oversight: it is a constructor rather
#: than an operator, so `1 :: l` builds a `Construct` and there is no
#: function for `( :: )` to name. OCaml says the same. A test comparing this
#: against the runtime's operator table is what found it.
OPERATOR_NAMES: tuple[str, ...] = (
    *(op for ops, _ in LEVELS for op in ops if op != "::"),
    ":=",
    "!",
)


def _pairs(rest: list[Any]) -> list[tuple[str, Any]]:
    """`many(seq(op, operand))` yields two-element lists; name them."""
    return [(item[0], item[1]) for item in rest]


def _binop(op: str, left: s.Expr, right: s.Expr) -> s.Expr:
    return s.Construct("::", [left, right]) if op == "::" else s.BinOp(op, left, right)


def _level(sub: Any, ops: tuple[str, ...], assoc: str) -> Any:
    """One row of `LEVELS`: `sub (op sub)*`, folded the row's way."""

    def build(value: list[Any]) -> s.Expr:
        head, rest = value[0], _pairs(value[1])
        if not rest:
            return head
        if assoc == "left":
            for op, right in rest:
                head = _binop(op, head, right)
            return head
        operands = [head, *(right for _, right in rest)]
        out = operands[-1]
        for op, left in zip(
            reversed([op for op, _ in rest]), reversed(operands[:-1]), strict=True
        ):
            out = _binop(op, left, out)
        return out

    return act(seq(sub, many(seq(one_of(ops), sub))), build)


def _nary(value: list[Any], make: Any) -> Any:
    """`head (sep item)*`: the head alone, or `make` over all of them."""
    head, rest = value[0], value[1]
    return head if not rest else make([head, *(item[1] for item in rest)])


# ------------------------------------------------------------------- types

# `Hashtbl.t` is one name with a dot in it, as `List.map` is below.
type_name = alt(
    act(seq(kind("uid"), lit("."), kind("lid")), lambda v: f"{v[0]}.{v[2]}"),
    kind("lid"),
)

atom_type = alt(
    act(kind("tyvar"), s.TVar),
    act(seq(lit("("), type_, lit(")")), _inner),
    act(type_name, lambda name: s.TCon(name, [])),
)


def _postfix_type(args: list[s.TypeExpr], names: list[str]) -> s.TypeExpr:
    """`int list array`: each name wraps what came before it."""
    for name in names:
        args = [s.TCon(name, args)]
    return args[0]


# A parenthesised list of two or more types is only a type constructor's
# argument, so the alternative that needs one comes first.
app_type = alt(
    act(
        seq(lit("("), sep1(type_, ","), lit(")"), many1(type_name)),
        lambda v: _postfix_type(v[1], v[3]),
    ),
    act(seq(atom_type, many(type_name)), lambda v: _postfix_type([v[0]], v[1])),
)

#: The components of `t1 * t2`, unfolded. A variant declares them as its
#: arguments, and `(int * string)` stays one because the parentheses make it
#: an `atom_type`.
type_components = act(
    seq(app_type, many(seq(lit("*"), app_type))),
    lambda v: [v[0], *(item[1] for item in v[1])],
)

tuple_type = act(
    type_components,
    lambda items: items[0] if len(items) == 1 else s.TTuple(items),
)

type_.define(
    act(
        seq(tuple_type, opt(seq(lit("->"), type_))),
        lambda v: v[0] if v[1] is None else s.TFun(v[0], v[1][1]),
    )
)

# ---------------------------------------------------------------- patterns

pat_literal = alt(
    act(kind("int"), lambda n: s.PLit(s.Int(n))),
    act(kind("float"), lambda x: s.PLit(s.Float(x))),
    act(kind("char"), lambda c: s.PLit(s.Char(c))),
    act(kind("string"), lambda t: s.PLit(s.Str(t))),
    act(lit("true"), lambda _: s.PLit(s.Bool(True))),
    act(lit("false"), lambda _: s.PLit(s.Bool(False))),
    act(seq(lit("-"), kind("int")), lambda v: s.PLit(s.Int(-v[1]))),
    act(seq(one_of(("-", "-.")), kind("float")), lambda v: s.PLit(s.Float(-v[1]))),
)

field_pat = act(
    seq(kind("lid"), opt(seq(lit("="), pattern))),
    lambda v: s.PField(v[0], v[1][1] if v[1] else s.PVar(v[0])),
)

atom_pat.define(
    alt(
        act(lit("_"), lambda _: s.PWild()),
        pat_literal,
        act(seq(lit("("), lit(")")), lambda _: s.PLit(s.Unit())),
        act(
            seq(lit("("), pattern, lit(":"), type_, lit(")")),
            lambda v: s.PConstraint(v[1], v[3]),
        ),
        act(seq(lit("("), pattern, lit(")")), _inner),
        act(seq(lit("["), lit("]")), lambda _: s.PList([])),
        act(
            seq(lit("["), sep1(pattern, ";"), opt(lit(";")), lit("]")),
            lambda v: s.PList(v[1]),
        ),
        act(seq(lit("[|"), lit("|]")), lambda _: s.PArray([])),
        act(
            seq(lit("[|"), sep1(pattern, ";"), opt(lit(";")), lit("|]")),
            lambda v: s.PArray(v[1]),
        ),
        act(
            seq(lit("{"), sep1(field_pat, ";"), opt(lit(";")), lit("}")),
            lambda v: s.PRecord(v[1]),
        ),
        act(kind("lid"), s.PVar),
    )
)


def _flatten_pat(argument: s.Pattern | None) -> list[s.Pattern]:
    """`C (a, b)` declares two components, as `C of t * t` does."""
    if argument is None:
        return []
    return list(argument.items) if isinstance(argument, s.PTuple) else [argument]


app_pat = alt(
    act(
        seq(kind("uid"), opt(atom_pat)),
        lambda v: s.PConstruct(v[0], _flatten_pat(v[1])),
    ),
    atom_pat,
)

cons_pat.define(
    act(
        seq(app_pat, opt(seq(lit("::"), cons_pat))),
        lambda v: v[0] if v[1] is None else s.PConstruct("::", [v[0], v[1][1]]),
    )
)

tuple_pat = act(
    seq(cons_pat, many(seq(lit(","), cons_pat))), lambda v: _nary(v, s.PTuple)
)
or_pat = act(seq(tuple_pat, many(seq(lit("|"), tuple_pat))), lambda v: _nary(v, s.POr))


def _alias(inner: s.Pattern, names: list[str]) -> s.Pattern:
    for name in names:
        inner = s.PAlias(inner, name)
    return inner


pattern.define(
    act(
        seq(or_pat, many(seq(lit("as"), kind("lid")))),
        lambda v: _alias(v[0], [item[1] for item in v[1]]),
    )
)

# ------------------------------------------------------------- expressions

field_bind = act(
    seq(kind("lid"), opt(seq(lit("="), expr))),
    lambda v: s.FieldBind(v[0], v[1][1] if v[1] else s.Var(v[0])),
)

record_body = alt(
    act(
        seq(seq_expr, lit("with"), sep1(field_bind, ";"), opt(lit(";"))),
        lambda v: s.Record(v[2], v[0]),
    ),
    act(seq(sep1(field_bind, ";"), opt(lit(";"))), lambda v: s.Record(v[0], None)),
)

atom_expr.define(
    alt(
        act(kind("int"), s.Int),
        act(kind("float"), s.Float),
        act(kind("char"), s.Char),
        act(kind("string"), s.Str),
        act(lit("true"), lambda _: s.Bool(True)),
        act(lit("false"), lambda _: s.Bool(False)),
        act(seq(lit("("), lit(")")), lambda _: s.Unit()),
        # `List.fold_left ( + ) 0`: an operator used as a value.
        act(seq(lit("("), one_of(OPERATOR_NAMES), lit(")")), lambda v: s.Var(v[1])),
        act(
            seq(lit("("), seq_expr, lit(":"), type_, lit(")")),
            lambda v: s.Constraint(v[1], v[3]),
        ),
        act(seq(lit("("), seq_expr, lit(")")), _inner),
        act(seq(lit("begin"), seq_expr, lit("end")), _inner),
        act(seq(lit("["), lit("]")), lambda _: s.ListLit([])),
        act(
            seq(lit("["), sep1(expr, ";"), opt(lit(";")), lit("]")),
            lambda v: s.ListLit(v[1]),
        ),
        act(seq(lit("[|"), lit("|]")), lambda _: s.ArrayLit([])),
        act(
            seq(lit("[|"), sep1(expr, ";"), opt(lit(";")), lit("|]")),
            lambda v: s.ArrayLit(v[1]),
        ),
        act(seq(lit("{"), record_body, lit("}")), _inner),
        # `List.map` is one name with a dot in it: the subset has no module
        # system, so there is nothing for a `modules` namespace to answer.
        act(seq(kind("uid"), lit("."), kind("lid")), lambda v: s.Var(f"{v[0]}.{v[2]}")),
        act(kind("uid"), lambda name: s.Construct(name, [])),
        act(kind("lid"), s.Var),
    )
)

prefix_expr.define(
    alt(
        act(seq(lit("!"), prefix_expr), lambda v: s.UnOp("!", v[1])),
        atom_expr,
    )
)

postfix = alt(
    act(seq(lit("."), kind("lid")), lambda v: ("field", v[1])),
    act(seq(lit(".("), seq_expr, lit(")")), lambda v: ("array", v[1])),
    act(seq(lit(".["), seq_expr, lit("]")), lambda v: ("string", v[1])),
)


def _access(value: list[Any]) -> s.Expr:
    out = value[0]
    for tag, argument in value[1]:
        match tag:
            case "field":
                out = s.GetField(out, argument)
            case "array":
                out = s.ArrayGet(out, argument)
            case _:
                out = s.StringGet(out, argument)
    return out


access_expr = act(seq(prefix_expr, many(postfix)), _access)


def _apply(value: list[Any]) -> s.Expr:
    """Juxtaposition. A constructor takes its one argument here."""
    head, args = value
    if not args:
        return head
    if isinstance(head, s.Construct) and not head.args:
        first, rest = args[0], args[1:]
        made = s.Construct(
            head.name, list(first.items) if isinstance(first, s.Tuple) else [first]
        )
        return made if not rest else s.Apply(made, rest)
    return s.Apply(head, args)


apply_expr = act(seq(access_expr, many(access_expr)), _apply)

neg_expr.define(
    alt(
        act(seq(one_of(("-", "-.")), neg_expr), lambda v: s.UnOp(v[0], v[1])),
        apply_expr,
    )
)

# The cascade of section 5, built from `LEVELS` tightest first.
_chain: Any = neg_expr
for _ops, _assoc in reversed(LEVELS):
    _chain = _level(_chain, _ops, _assoc)
or_expr = _chain

tuple_expr = act(
    seq(or_expr, many(seq(lit(","), or_expr))), lambda v: _nary(v, s.Tuple)
)


def _assign(value: list[Any]) -> s.Expr | None:
    """`:=` is an operator; `<-` needs a field or an element on its left."""
    left, tail = value
    if tail is None:
        return left
    op, right = tail
    if op == ":=":
        return s.BinOp(":=", left, right)
    match left:
        case s.GetField():
            return s.SetField(left.value, left.label, right)
        case s.ArrayGet():
            return s.ArraySet(left.array, left.index, right)
    return None


assign_expr.define(
    guard(seq(tuple_expr, opt(seq(one_of((":=", "<-")), assign_expr))), _assign)
)

case = act(
    seq(pattern, opt(seq(lit("when"), seq_expr)), lit("->"), seq_expr),
    lambda v: s.Case(v[0], v[1][1] if v[1] else None, v[3]),
)
cases = act(seq(opt(lit("|")), sep1(case, "|")), _inner)

binding = act(
    seq(pattern, many(atom_pat), opt(seq(lit(":"), type_)), lit("="), seq_expr),
    lambda v: s.Binding(v[0], v[1], v[2][1] if v[2] else None, v[4]),
)
bindings = act(
    seq(opt(lit("rec")), sep1(binding, "and")),
    lambda v: (v[0] is not None, v[1]),
)

let_expr = act(
    seq(lit("let"), bindings, lit("in"), seq_expr),
    lambda v: s.LetIn(v[1][0], v[1][1], v[3]),
)
fun_expr = act(
    seq(lit("fun"), many1(atom_pat), lit("->"), seq_expr), lambda v: s.Fun(v[1], v[3])
)
function_expr = act(seq(lit("function"), cases), lambda v: s.Function(v[1]))
match_expr = act(
    seq(lit("match"), seq_expr, lit("with"), cases), lambda v: s.Match(v[1], v[3])
)
try_expr = act(
    seq(lit("try"), seq_expr, lit("with"), cases), lambda v: s.Try(v[1], v[3])
)
if_expr = act(
    seq(lit("if"), seq_expr, lit("then"), expr, opt(seq(lit("else"), expr))),
    lambda v: s.If(v[1], v[3], v[4][1] if v[4] else None),
)
while_expr = act(
    seq(lit("while"), seq_expr, lit("do"), seq_expr, lit("done")),
    lambda v: s.While(v[1], v[3]),
)
for_expr = act(
    seq(
        lit("for"),
        kind("lid"),
        lit("="),
        seq_expr,
        one_of(("to", "downto")),
        seq_expr,
        lit("do"),
        seq_expr,
        lit("done"),
    ),
    lambda v: s.For(s.PVar(v[1]), v[3], v[5], v[4] == "downto", v[7]),
)

expr.define(
    alt(
        let_expr,
        fun_expr,
        function_expr,
        match_expr,
        try_expr,
        if_expr,
        while_expr,
        for_expr,
        assign_expr,
    )
)

seq_expr.define(
    act(
        seq(expr, many(seq(lit(";"), expr)), opt(lit(";"))),
        lambda v: _nary(v, s.Seq),
    )
)

# ------------------------------------------------------------------- items

type_params = alt(
    act(kind("tyvar"), lambda name: [name]),
    act(seq(lit("("), sep1(kind("tyvar"), ","), lit(")")), _inner),
)
variant = act(
    seq(kind("uid"), opt(seq(lit("of"), type_components))),
    lambda v: s.Variant(v[0], v[1][1] if v[1] else []),
)
field_decl = act(
    seq(opt(lit("mutable")), kind("lid"), lit(":"), type_),
    lambda v: s.FieldDef(v[1], v[3], v[0] is not None),
)
type_rhs = alt(
    act(
        seq(lit("{"), sep1(field_decl, ";"), opt(lit(";")), lit("}")),
        lambda v: s.RecordDef(v[1]),
    ),
    act(seq(opt(lit("|")), sep1(variant, "|")), lambda v: s.Variants(v[1])),
    act(type_, s.AliasDef),
)
typedef = act(
    seq(opt(type_params, []), kind("lid"), lit("="), type_rhs),
    lambda v: s.TypeDef(v[1], v[0], v[3]),
)

# `not_(lit("in"))` is what separates a definition from an expression: a
# top-level `let x = 1` binds for the rest of the structure, and
# `let x = 1 in e` is one expression that happens to start the same way.
item = alt(
    act(seq(lit("type"), sep1(typedef, "and")), lambda v: s.TypeItem(v[1])),
    act(
        seq(lit("exception"), kind("uid"), opt(seq(lit("of"), type_components))),
        lambda v: s.ExnItem(v[1], v[2][1] if v[2] else []),
    ),
    act(
        seq(lit("let"), bindings, not_(lit("in"))),
        lambda v: s.LetItem(v[1][0], v[1][1]),
    ),
    act(seq_expr, s.ExprItem),
)

structure = act(
    seq(many(lit(";;")), many(act(seq(item, many(lit(";;"))), _first))),
    lambda v: s.Structure(v[1]),
)


def parse(source: str) -> s.Structure:
    """The structure `source` denotes, or `peg.ParseError`."""
    return run(structure, tokenize(source), source)


def parse_type(source: str) -> s.TypeExpr:
    """One type expression. `types.py` writes the prelude's types as OCaml
    and reads them back with this, rather than building them by hand."""
    return run(type_, tokenize(source), source)
