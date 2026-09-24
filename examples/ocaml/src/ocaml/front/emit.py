"""Turning a tree back into source text.

The parser reads text and builds a tree; this does the reverse. Two uses,
and the second is the interesting one.

It is how the playground shows you what the compiler *thought* you wrote:
if a bracket moves, the grouping was not what you expected.

And it is how the parser is checked. Print a tree, read the printed text
back, and compare the two trees. They have to match, over every programme
in the corpus. A grammar rule that groups the wrong way survives every
hand-written assertion and dies here.

Brackets are the whole difficulty of printing, and they are not counted by
hand. `astero.emit` supplies the rule — a child needs brackets when it
binds less tightly than the position it sits in — and this file supplies
the table. The table is not written here either: `OPERATOR_LEVEL` is built
from `parser.LEVELS`, the same rows the parser cascades over, so one
declaration groups on the way in and brackets on the way out.

ponytail: one line per item, no layout. `astero.emit` has `nest` and `line`
for when the output is meant to be read rather than reparsed.
"""

from __future__ import annotations

from typing import Any

from astero.emit import (
    ATOM,
    FREE,
    Assoc,
    Doc,
    Level,
    concat,
    joined,
    needs_parens,
    render as render_doc,
    text as raw,
)
from ocaml import syntax as s

from .parser import LEVELS

#: Where the binary operators start. Below it sit the forms that are not
#: operators, in the order `specification.md`, *Precedence*, gives them.
BINARY_BASE = 8

ASSOC = {"left": Assoc.LEFT, "right": Assoc.RIGHT}

#: Binding power per operator, from the parser's table. `LEVELS` is loosest
#: first, so the row's index is its power above `BINARY_BASE`.
OPERATOR_LEVEL: dict[str, Level] = {
    op: Level(BINARY_BASE + index, ASSOC[assoc])
    for index, (ops, assoc) in enumerate(LEVELS)
    for op in ops
}

EXTEND = Level(3, Assoc.NONE)  # let ... in, fun, function, match, try
ARM = Level(4, Assoc.NONE)  # where a `;` or a `|` would end the expression
SEMI = Level(4, Assoc.RIGHT)
COND = Level(5, Assoc.NONE)  # if, while, for
SET = Level(6, Assoc.RIGHT)  # := and <-
COMMA = Level(7, Assoc.NONE)
NEG = Level(16, Assoc.NONE)
APPLY = Level(17, Assoc.LEFT)
ACCESS = Level(18, Assoc.LEFT)
DEREF = Level(19, Assoc.NONE)

# Patterns have their own cascade, and the same rule brackets it.
P_ALIAS = Level(1, Assoc.LEFT)
P_OR = Level(2, Assoc.LEFT)
P_COMMA = Level(3, Assoc.NONE)
P_CONS = Level(4, Assoc.RIGHT)
P_APPLY = Level(5, Assoc.NONE)

T_FUN = Level(1, Assoc.RIGHT)
T_TUPLE = Level(2, Assoc.LEFT)
T_APPLY = Level(3, Assoc.LEFT)

_ESCAPES = {"\n": "\\n", "\t": "\\t", "\r": "\\r", "\b": "\\b", "\\": "\\\\"}


def unparse(structure: s.Structure) -> str:
    """Source that parses back to `structure`.

    Every item ends with `;;`. Without it two expression items run together,
    because juxtaposition is application: `print_int 1 print_int 2` is one
    call to `print_int` with three arguments.
    """
    return "".join(f"{render_doc(item_doc(item))};;\n" for item in structure.items)


# ------------------------------------------------------------------ helpers


def parens(doc: Doc) -> Doc:
    return concat(raw("("), doc, raw(")"))


def sub(node: Any, outer: Level, *, right: bool = False) -> Doc:
    """A child, bracketed where the declared powers say it must be."""
    doc, inner = expr_doc(node)
    return parens(doc) if needs_parens(inner, outer, on_right=right) else doc


def sub_pat(node: Any, outer: Level, *, right: bool = False) -> Doc:
    doc, inner = pat_doc(node)
    return parens(doc) if needs_parens(inner, outer, on_right=right) else doc


def sub_type(node: Any, outer: Level, *, right: bool = False) -> Doc:
    doc, inner = type_doc(node)
    return parens(doc) if needs_parens(inner, outer, on_right=right) else doc


def name_doc(name: str) -> Doc:
    """A value name, or an operator written as one: `( + )`."""
    plain = name[0].isalpha() or name[0] == "_"
    return raw(name if plain else f"( {name} )")


def quoted(value: str, mark: str) -> Doc:
    body = "".join(_ESCAPES.get(c, c) for c in value).replace(mark, f"\\{mark}")
    return raw(f"{mark}{body}{mark}")


def infix(op: str, left: Any, right: Any) -> tuple[Doc, Level]:
    level = OPERATOR_LEVEL.get(op, SET)
    doc = concat(sub(left, level), raw(f" {op} "), sub(right, level, right=True))
    return doc, level


def listing(open_: str, items: list[Any], close: str, sep: str = "; ") -> Doc:
    """`[a; b]`, `[| a; b |]`, `C (a, b)`. The separator is the difference:
    a list is `;` and a constructor's components are a tuple."""
    return concat(
        raw(open_), joined(sep, [sub(item, ARM) for item in items]), raw(close)
    )


def case_doc(case: s.Case) -> Doc:
    guard = concat(raw(" when "), sub(case.guard, FREE)) if case.guard else raw("")
    return concat(sub_pat(case.pattern, FREE), guard, raw(" -> "), sub(case.body, ARM))


def cases_doc(cases: list[s.Case]) -> Doc:
    return joined(" | ", [case_doc(case) for case in cases])


def binding_doc(binding: s.Binding) -> Doc:
    params = [concat(raw(" "), sub_pat(p, P_APPLY)) for p in binding.params]
    annot = (
        concat(raw(" : "), sub_type(binding.annot, FREE)) if binding.annot else raw("")
    )
    return concat(
        sub_pat(binding.pattern, P_APPLY),
        concat(*params) if params else raw(""),
        annot,
        raw(" = "),
        sub(binding.value, FREE),
    )


def bindings_doc(recursive: bool, bindings: list[s.Binding]) -> Doc:
    return concat(
        raw("let rec " if recursive else "let "),
        joined(" and ", [binding_doc(b) for b in bindings]),
    )


# -------------------------------------------------------------- expressions


def expr_doc(node: Any) -> tuple[Doc, Level]:
    """The document for one expression, and the power it binds with."""
    match node:
        case s.Int(value=value):
            return raw(str(value)), ATOM
        case s.Float(value=value):
            return raw(repr(value)), ATOM
        case s.Char(value=value):
            return quoted(value, "'"), ATOM
        case s.Str(value=value):
            return quoted(value, '"'), ATOM
        case s.Bool(value=value):
            return raw("true" if value else "false"), ATOM
        case s.Unit():
            return raw("()"), ATOM
        case s.Var(name=name):
            return name_doc(name), ATOM
        case s.Construct(name="::", args=[head, tail]):
            return infix("::", head, tail)
        case s.Construct(name=name, args=[]):
            return raw(name), ATOM
        case s.Construct(name=name, args=[only]):
            return concat(raw(name), raw(" "), sub(only, ACCESS)), APPLY
        case s.Construct(name=name, args=args):
            return concat(raw(name), raw(" "), listing("(", args, ")", ", ")), APPLY
        case s.Tuple(items=items):
            return joined(", ", [sub(i, COMMA) for i in items]), COMMA
        case s.ListLit(items=items):
            return listing("[", items, "]"), ATOM
        case s.ArrayLit(items=items):
            return listing("[| ", items, " |]"), ATOM
        case s.Record(fields=fields, base=base):
            head = concat(sub(base, ARM), raw(" with ")) if base else raw("")
            body = joined("; ", [field_bind_doc(f) for f in fields])
            return concat(raw("{ "), head, body, raw(" }")), ATOM
        case s.Apply(fn=fn, args=args):
            parts = [concat(raw(" "), sub(a, APPLY, right=True)) for a in args]
            return concat(sub(fn, APPLY), *parts), APPLY
        case s.BinOp(op=op, left=left, right=right):
            return infix(op, left, right)
        case s.UnOp(op="!", value=value):
            return concat(raw("!"), sub(value, DEREF)), DEREF
        case s.UnOp(op=op, value=value):
            return concat(raw(op), raw(" "), sub(value, NEG)), NEG
        case s.If(cond=cond, then=then, otherwise=otherwise):
            tail = concat(raw(" else "), sub(otherwise, COND)) if otherwise else raw("")
            body = concat(
                raw("if "), sub(cond, FREE), raw(" then "), sub(then, COND), tail
            )
            return body, COND
        case s.Seq(items=items):
            parts = [sub(i, SEMI) for i in items[:-1]]
            parts.append(sub(items[-1], SEMI, right=True))
            return joined("; ", parts), SEMI
        case s.LetIn(recursive=recursive, bindings=bindings, body=body):
            head = bindings_doc(recursive, bindings)
            return concat(head, raw(" in "), sub(body, FREE)), EXTEND
        case s.Fun(params=params, body=body):
            heads = [concat(raw(" "), sub_pat(p, P_APPLY)) for p in params]
            return concat(raw("fun"), *heads, raw(" -> "), sub(body, FREE)), EXTEND
        case s.Function(cases=cases):
            return concat(raw("function "), cases_doc(cases)), EXTEND
        case s.Match(scrutinee=scrutinee, cases=cases):
            head = concat(raw("match "), sub(scrutinee, FREE), raw(" with "))
            return concat(head, cases_doc(cases)), EXTEND
        case s.Try(body=body, cases=cases):
            head = concat(raw("try "), sub(body, FREE), raw(" with "))
            return concat(head, cases_doc(cases)), EXTEND
        case s.While(cond=cond, body=body):
            head = concat(raw("while "), sub(cond, FREE), raw(" do "))
            return concat(head, sub(body, FREE), raw(" done")), COND
        case s.For(var=var, start=start, stop=stop, down=down, body=body):
            return _for_doc(var, start, stop, down=down, body=body), COND
        case s.GetField(value=value, label=label):
            return concat(sub(value, ACCESS), raw(f".{label}")), ACCESS
        case s.SetField(value=value, label=label, rhs=rhs):
            head = concat(sub(value, ACCESS), raw(f".{label} <- "))
            return concat(head, sub(rhs, SET, right=True)), SET
        case s.ArrayGet(array=array, index=index):
            body = concat(raw(".("), sub(index, FREE), raw(")"))
            return concat(sub(array, ACCESS), body), ACCESS
        case s.ArraySet(array=array, index=index, rhs=rhs):
            head = concat(sub(array, ACCESS), raw(".("), sub(index, FREE), raw(") <- "))
            return concat(head, sub(rhs, SET, right=True)), SET
        case s.StringGet(value=value, index=index):
            body = concat(raw(".["), sub(index, FREE), raw("]"))
            return concat(sub(value, ACCESS), body), ACCESS
        case s.Constraint(value=value, annot=annot):
            body = concat(sub(value, FREE), raw(" : "), sub_type(annot, FREE))
            return parens(body), ATOM
    raise TypeError(f"no printer for {type(node).__name__}")


def _for_doc(var: s.PVar, start: Any, stop: Any, *, down: bool, body: Any) -> Doc:
    return concat(
        raw(f"for {var.name} = "),
        sub(start, FREE),
        raw(" downto " if down else " to "),
        sub(stop, FREE),
        raw(" do "),
        sub(body, FREE),
        raw(" done"),
    )


def field_bind_doc(bind: s.FieldBind) -> Doc:
    return concat(raw(f"{bind.label} = "), sub(bind.value, ARM))


# ------------------------------------------------------------------ patterns


def pat_doc(node: Any) -> tuple[Doc, Level]:
    match node:
        case s.PWild():
            return raw("_"), ATOM
        case s.PVar(name=name):
            return raw(name), ATOM
        case s.PLit(value=value):
            doc, _ = expr_doc(value)
            return doc, ATOM
        case s.PTuple(items=items):
            return joined(", ", [sub_pat(i, P_COMMA) for i in items]), P_COMMA
        case s.PList(items=items):
            return _pat_listing("[", items, "]"), ATOM
        case s.PArray(items=items):
            return _pat_listing("[| ", items, " |]"), ATOM
        case s.PConstruct(name="::", args=[head, tail]):
            body = concat(
                sub_pat(head, P_CONS), raw(" :: "), sub_pat(tail, P_CONS, right=True)
            )
            return body, P_CONS
        case s.PConstruct(name=name, args=[]):
            return raw(name), ATOM
        case s.PConstruct(name=name, args=[only]):
            return concat(raw(name), raw(" "), sub_pat(only, P_APPLY)), P_APPLY
        case s.PConstruct(name=name, args=args):
            return concat(
                raw(name), raw(" "), _pat_listing("(", args, ")", ", ")
            ), P_APPLY
        case s.PRecord(fields=fields):
            body = joined("; ", [pat_field_doc(f) for f in fields])
            return concat(raw("{ "), body, raw(" }")), ATOM
        case s.POr(alternatives=alternatives):
            return joined(" | ", [sub_pat(a, P_OR) for a in alternatives]), P_OR
        case s.PAlias(pattern=pattern, name=name):
            return concat(sub_pat(pattern, P_ALIAS), raw(f" as {name}")), P_ALIAS
        case s.PConstraint(pattern=pattern, annot=annot):
            body = concat(sub_pat(pattern, FREE), raw(" : "), sub_type(annot, FREE))
            return parens(body), ATOM
    raise TypeError(f"no printer for {type(node).__name__}")


def _pat_listing(open_: str, items: list[Any], close: str, sep: str = "; ") -> Doc:
    parts = [sub_pat(i, P_COMMA) for i in items]
    return concat(raw(open_), joined(sep, parts), raw(close))


def pat_field_doc(field: s.PField) -> Doc:
    return concat(raw(f"{field.label} = "), sub_pat(field.pattern, P_COMMA))


# ------------------------------------------------------------------- types


def type_doc(node: Any) -> tuple[Doc, Level]:
    match node:
        case s.TVar(name=name):
            return raw(name), ATOM
        case s.TCon(name=name, args=[]):
            return raw(name), ATOM
        case s.TCon(name=name, args=[only]):
            return concat(sub_type(only, T_APPLY), raw(f" {name}")), T_APPLY
        case s.TCon(name=name, args=args):
            parts = joined(", ", [sub_type(a, FREE) for a in args])
            return concat(parens(parts), raw(f" {name}")), T_APPLY
        case s.TFun(arg=arg, result=result):
            body = concat(
                sub_type(arg, T_FUN), raw(" -> "), sub_type(result, T_FUN, right=True)
            )
            return body, T_FUN
        case s.TTuple(items=items):
            return joined(" * ", [sub_type(i, T_TUPLE) for i in items]), T_TUPLE
    raise TypeError(f"no printer for {type(node).__name__}")


# ------------------------------------------------------------------- items


def item_doc(node: Any) -> Doc:
    match node:
        case s.LetItem(recursive=recursive, bindings=bindings):
            return bindings_doc(recursive, bindings)
        case s.TypeItem(defs=defs):
            body = joined(" and ", [typedef_doc(d) for d in defs])
            return concat(raw("type "), body)
        case s.ExnItem(name=name, args=args):
            return concat(raw(f"exception {name}"), _of_doc(args))
        case s.ExprItem(value=value):
            return sub(value, FREE)
    raise TypeError(f"no printer for {type(node).__name__}")


def _of_doc(args: list[s.TypeExpr]) -> Doc:
    if not args:
        return raw("")
    parts = joined(" * ", [sub_type(a, T_TUPLE) for a in args])
    return concat(raw(" of "), parts)


def typedef_doc(node: s.TypeDef) -> Doc:
    if not node.params:
        head = raw(node.name)
    elif len(node.params) == 1:
        head = raw(f"{node.params[0]} {node.name}")
    else:
        head = raw(f"({', '.join(node.params)}) {node.name}")
    return concat(head, raw(" = "), rhs_doc(node.rhs))


def rhs_doc(node: Any) -> Doc:
    match node:
        case s.Variants(variants=variants):
            return joined(" | ", [variant_doc(v) for v in variants])
        case s.RecordDef(fields=fields):
            body = joined("; ", [field_def_doc(f) for f in fields])
            return concat(raw("{ "), body, raw(" }"))
        case s.AliasDef(annot=annot):
            return sub_type(annot, FREE)
    raise TypeError(f"no printer for {type(node).__name__}")


def variant_doc(node: s.Variant) -> Doc:
    return concat(raw(node.name), _of_doc(node.args))


def field_def_doc(node: s.FieldDef) -> Doc:
    head = "mutable " if node.is_mutable else ""
    return concat(raw(f"{head}{node.name} : "), sub_type(node.annot, FREE))
