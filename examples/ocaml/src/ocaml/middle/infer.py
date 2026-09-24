"""Type inference, part two: one rule per kind of node.

`unify.py` supplies the machinery and `prelude.py` the starting
environment; this supplies the rules. An `if` needs its condition to be
`bool` and both branches to agree. An application `f x` needs `f` to be a
function whose argument type matches `x`. A `match` needs every arm's
pattern to fit the scrutinee and every arm's body to agree. Written out,
that is most of this file.

Three pieces are less obvious than the rest:

* **Let-polymorphism.** `let id x = x` gets the type `'a -> 'a`, which
  means it can be used at `int` in one place and at `string` in another.
  That is what generalizing at a `let` buys.

* **The value restriction.** `let r = ref []` must *not* be generalized, or
  the same cell could be filled with an `int` and read back as a `string`,
  and the type system would be lying. Only a syntactic value is
  generalized. A variable left ungeneralized prints as `'_weak1`, exactly
  as OCaml prints it.

* **Nominal records and variants.** A field name or a constructor name
  determines which type it belongs to, so the tables in `Declarations` are
  looked up by label rather than matched structurally.

**astero contributes nothing to this file, and that is the point of it.**
Its plan marks type inference as the one front-end job it does not do, and
these three modules are the measurement of what that costs: nothing here is
derived from a declaration, and it is the largest part of the compiler.
"""

from __future__ import annotations

from collections import ChainMap
from dataclasses import dataclass, field
from typing import Any

from ocaml import syntax as s
from ocaml.front.formats import LETTERS, FormatError, conversions
from ocaml.front.parser import parse_type

from .prelude import (
    CONSTRUCTOR_RESULTS,
    CONSTRUCTORS,
    PRELUDE_TYPES,
    TYPE_ARITY,
    UNARY_TYPES,
)
from .unify import (
    ARROW,
    BOOL,
    CHAR,
    EXN,
    FLOAT,
    INT,
    STRING,
    TUPLE,
    UNIT,
    Con,
    Fresh,
    Scheme,
    Type,
    TypingError,
    Var,
    arrow,
    expand,
    generalize,
    instantiate,
    prune,
    resolved,
    show_scheme,
    unify,
)

# --------------------------------------------------------- what is declared


@dataclass(frozen=True)
class Constructor:
    """A variant constructor, or an exception. `args` may be empty."""

    quantified: tuple[int, ...]
    args: tuple[Type, ...]
    result: Type


@dataclass(frozen=True)
class RecordType:
    """A record type and all of its labels, quantified together.

    Together, because instantiating one label has to instantiate the others
    the same way: `{ fst_ = 1; snd_ = true }` is one `('a, 'b) pair`.
    """

    name: str
    quantified: tuple[int, ...]
    owner: Type
    labels: dict[str, tuple[Type, bool]]


@dataclass
class Declarations:
    """The nominal tables: what `type` and `exception` items introduce."""

    arity: dict[str, int] = field(default_factory=lambda: dict(TYPE_ARITY))
    constructors: dict[str, Constructor] = field(default_factory=dict)
    records: dict[str, RecordType] = field(default_factory=dict)
    #: `type position = point` is transparent in OCaml: an alias keeps its
    #: name, and `Con.expansion` says what it stands for.
    aliases: dict[str, tuple[tuple[int, ...], Type]] = field(default_factory=dict)

    def record_of(self, labels: list[str], known: Type | None = None) -> RecordType:
        """The record type these labels belong to, as OCaml disambiguates.

        Two types may share a label. A type already known from the context
        decides, as `(p : processor).id` does; otherwise the latest type
        declaring every one of the labels wins, as a later declaration
        shadows an earlier one.
        """
        known = expand(known) if known is not None else None
        if isinstance(known, Con) and known.name in self.records:
            record = self.records[known.name]
            if set(labels) <= set(record.labels):
                return record
        for record in reversed(self.records.values()):
            if set(labels) <= set(record.labels):
                return record
        raise TypingError(f"unbound record field {labels[0]}")


@dataclass
class State:
    fresh: Fresh = field(default_factory=Fresh)
    decls: Declarations = field(default_factory=Declarations)
    #: Prefix `-`, `-.` and `!`, which are not the binary operators of the
    #: same spelling. Filled by `prelude`.
    unary: dict[str, Scheme] = field(default_factory=dict)


Env = ChainMap[str, Scheme]


def convert(node: Any, tyvars: dict[str, Var], state: State, level: int) -> Type:
    """A written type expression as a type, with `'a` shared across one
    declaration."""
    match node:
        case s.TVar(name=name):
            return tyvars.setdefault(name, state.fresh(level))
        case s.TFun(arg=arg, result=result):
            return Con(
                ARROW,
                (
                    convert(arg, tyvars, state, level),
                    convert(result, tyvars, state, level),
                ),
            )
        case s.TTuple(items=items):
            return Con(TUPLE, tuple(convert(i, tyvars, state, level) for i in items))
        case s.TCon(name=name, args=args):
            wanted = state.decls.arity.get(name)
            if wanted is None:
                raise TypingError(f"unbound type constructor {name}")
            if wanted != len(args):
                raise TypingError(
                    f"{name} takes {wanted} argument(s), given {len(args)}"
                )
            parts = tuple(convert(a, tyvars, state, level) for a in args)
            alias = state.decls.aliases.get(name)
            if alias is None:
                return Con(name, parts)
            quantified, body = alias
            inside = _expand(body, dict(zip(quantified, parts, strict=True)))
            return Con(name, parts, inside)
    raise TypingError(f"no rule for {type(node).__name__}")


def _expand(body: Type, mapping: dict[int, Type]) -> Type:
    """Substitute an alias's parameters. `type position = point` is `point`."""
    body = prune(body)
    if isinstance(body, Var):
        return mapping.get(body.id, body)
    return body.rebuilt(lambda part: _expand(part, mapping))


def instantiate_all(
    quantified: tuple[int, ...], parts: tuple[Type, ...], state: State, level: int
) -> tuple[Type, ...]:
    """Instantiate several types under one substitution."""
    made = {name: state.fresh(level) for name in quantified}

    def copy(current: Type) -> Type:
        current = prune(current)
        if isinstance(current, Var):
            return made.get(current.id, current)
        return current.rebuilt(copy)

    return tuple(copy(part) for part in parts)


# ------------------------------------------------------------- the prelude


def prelude(state: State) -> Env:
    """The initial environment, and the constructors that come with it."""
    env: dict[str, Scheme] = {}
    for name, written in PRELUDE_TYPES.items():
        env[name] = _scheme_of(written, state)
    for name, written in UNARY_TYPES.items():
        state.unary[name] = _scheme_of(written, state)
    for name, args in CONSTRUCTORS.items():
        tyvars: dict[str, Var] = {}
        written = CONSTRUCTOR_RESULTS.get(name, "exn")
        result = convert(parse_type(written), tyvars, state, 1)
        parts = tuple(convert(parse_type(a), tyvars, state, 1) for a in args)
        quantified = tuple(var.id for var in tyvars.values())
        state.decls.constructors[name] = Constructor(quantified, parts, result)
    return ChainMap({}, env)


def _scheme_of(written: str, state: State) -> Scheme:
    tyvars: dict[str, Var] = {}
    body = convert(parse_type(written), tyvars, state, 1)
    return Scheme(tuple(var.id for var in tyvars.values()), body)


# ------------------------------------------------------------- declarations


def declare_types(defs: list[s.TypeDef], state: State) -> None:
    """Register a `type` item. Arities first, so a group may be recursive."""
    for definition in defs:
        state.decls.arity[definition.name] = len(definition.params)
    for definition in defs:
        tyvars: dict[str, Var] = {}
        params = [tyvars.setdefault(p, state.fresh(1)) for p in definition.params]
        quantified = tuple(var.id for var in params)
        owner = Con(definition.name, tuple(params))
        declare_rhs(definition, owner, quantified, tyvars, state)
        _only_parameters(tyvars, definition.params)


def declare_rhs(
    definition: s.TypeDef,
    owner: Type,
    quantified: tuple[int, ...],
    tyvars: dict[str, Var],
    state: State,
) -> None:
    match definition.rhs:
        case s.Variants(variants=variants):
            for variant in variants:
                args = tuple(convert(a, tyvars, state, 1) for a in variant.args)
                state.decls.constructors[variant.name] = Constructor(
                    quantified, args, owner
                )
        case s.RecordDef(fields=fields):
            labels = {
                f.name: (convert(f.annot, tyvars, state, 1), f.is_mutable)
                for f in fields
            }
            state.decls.records[definition.name] = RecordType(
                definition.name, quantified, owner, labels
            )
        case s.AliasDef(annot=annot):
            body = convert(annot, tyvars, state, 1)
            state.decls.aliases[definition.name] = (quantified, body)


def declare_exception(node: s.ExnItem, state: State) -> None:
    tyvars: dict[str, Var] = {}
    args = tuple(convert(a, tyvars, state, 1) for a in node.args)
    _only_parameters(tyvars, [])
    state.decls.constructors[node.name] = Constructor((), args, EXN)


def _only_parameters(tyvars: dict[str, Var], params: list[str]) -> None:
    """A declaration may mention no type variable it does not take.

    In a value annotation `'a` declares itself, and `grammar.py` says so;
    in `type t = 'a list` it is an error, and this is where OCaml reports
    it, since the resolver cannot tell the two positions apart.
    """
    for name in tyvars.keys() - set(params):
        raise TypingError(
            f"the type variable {name} is unbound in this type declaration"
        )


# --------------------------------------------------------------- patterns

Holes = dict[str, Type]


def literal_type(node: Any) -> Type:
    match node:
        case s.Int():
            return INT
        case s.Float():
            return FLOAT
        case s.Char():
            return CHAR
        case s.Str():
            return STRING
        case s.Bool():
            return BOOL
        case s.Unit():
            return UNIT
    raise TypingError(f"{type(node).__name__} is not a literal")


def infer_pattern(node: Any, holes: Holes, state: State, level: int) -> Type:
    """The type a pattern matches, binding its variables into `holes`."""
    match node:
        case s.PWild():
            return state.fresh(level)
        case s.PVar(name=name):
            holes[name] = made = state.fresh(level)
            return made
        case s.PLit(value=value):
            return literal_type(value)
        case s.PTuple(items=items):
            return Con(
                TUPLE, tuple(infer_pattern(i, holes, state, level) for i in items)
            )
        case s.PList(items=items):
            return Con("list", (_same(items, holes, state, level),))
        case s.PArray(items=items):
            return Con("array", (_same(items, holes, state, level),))
        case s.PConstruct(name=name, args=args):
            result, wanted = constructor_types(name, len(args), state, level)
            for argument, expected in zip(args, wanted, strict=True):
                unify(infer_pattern(argument, holes, state, level), expected)
            return result
        case s.PRecord(fields=fields):
            record = state.decls.record_of([f.label for f in fields])
            owner, labels = _open_record(record, state, level)
            for entry in fields:
                unify(
                    infer_pattern(entry.pattern, holes, state, level),
                    labels[entry.label][0],
                )
            return owner
        case s.POr(alternatives=alternatives):
            return _or_pattern(alternatives, holes, state, level)
        case s.PAlias(pattern=pattern, name=name):
            found = infer_pattern(pattern, holes, state, level)
            holes[name] = found
            return found
        case s.PConstraint(pattern=pattern, annot=annot):
            written = convert(annot, {}, state, level)
            unify(infer_pattern(pattern, holes, state, level), written)
            # The written type, so an abbreviation it names is what is printed.
            return written
    raise TypingError(f"no rule for {type(node).__name__}")


def _same(items: list[Any], holes: Holes, state: State, level: int) -> Type:
    """One element type for every item, which is what a literal needs."""
    element = state.fresh(level)
    for item in items:
        unify(element, infer_pattern(item, holes, state, level))
    return element


def _or_pattern(
    alternatives: list[Any], holes: Holes, state: State, level: int
) -> Type:
    """Every alternative has the same type and binds the same names.

    The second half is the rule `specification.md`, *Patterns*, states, and
    it is checked here because nothing in the grammar can say it.
    """
    found = state.fresh(level)
    bound: list[Holes] = []
    for alternative in alternatives:
        side: Holes = {}
        unify(found, infer_pattern(alternative, side, state, level))
        bound.append(side)
    first = bound[0]
    for side in bound[1:]:
        if side.keys() != first.keys():
            missing = sorted(set(first) ^ set(side))
            raise TypingError(
                f"the alternatives of this or-pattern bind different names: {missing}"
            )
        for name, found_type in side.items():
            unify(first[name], found_type)
    holes.update(first)
    return found


def _open_record(
    record: RecordType, state: State, level: int
) -> tuple[Type, dict[str, tuple[Type, bool]]]:
    """One instantiation shared by the record type and all of its labels."""
    order = list(record.labels)
    parts = instantiate_all(
        record.quantified,
        (record.owner, *(record.labels[name][0] for name in order)),
        state,
        level,
    )
    labels = {
        name: (parts[index + 1], record.labels[name][1])
        for index, name in enumerate(order)
    }
    return parts[0], labels


def constructor_types(
    name: str, given: int, state: State, level: int
) -> tuple[Type, tuple[Type, ...]]:
    """What a constructor yields and what it takes, freshly instantiated.

    Returned rather than checked here, so a pattern unifies the arguments
    against patterns and an expression against expressions, and the arity
    rule is stated once.
    """
    found = state.decls.constructors.get(name)
    if found is None:
        raise TypingError(f"unbound constructor {name}")
    parts = instantiate_all(found.quantified, (found.result, *found.args), state, level)
    if given != len(parts) - 1:
        raise TypingError(f"{name} takes {len(parts) - 1} argument(s), given {given}")
    return parts[0], parts[1:]


# ------------------------------------------------------------- expressions


def _format(argument: Any, callee: Type) -> Type | None:
    """A string literal where a `format` is expected, typed from inside.

    OCaml types `"%d: %s"` as a format when the context wants one, and as a
    `string` otherwise, which is how `Printf.printf "%d: %s" n name` knows it
    takes an `int` and then a `string`. The context here is the callee's
    parameter, so a format must be written where it is used; one bound by
    `let` first is a string, and OCaml accepts that where this does not.
    """
    wanted = expand(callee)
    if not (
        isinstance(argument, s.Str) and isinstance(wanted, Con) and wanted.name == ARROW
    ):
        return None
    parameter = expand(wanted.args[0])
    if not (isinstance(parameter, Con) and parameter.name == "format"):
        return None
    result, _channel, final = parameter.args
    try:
        found = conversions(argument.value)
    except FormatError as error:
        raise TypingError(str(error)) from None
    takes = [Con(LETTERS[conversion.letter]) for conversion in found]
    unify(result, arrow(*takes, final))
    return parameter


def infer_expr(node: Any, env: Env, state: State, level: int) -> Type:
    match node:
        case s.Int() | s.Float() | s.Char() | s.Str() | s.Bool() | s.Unit():
            return literal_type(node)
        case s.Var(name=name):
            found = env.get(name)
            if found is None:
                raise TypingError(f"unbound value {name}")
            return instantiate(found, level, state.fresh)
        case s.Construct(name=name, args=args):
            result, wanted = constructor_types(name, len(args), state, level)
            for argument, expected in zip(args, wanted, strict=True):
                unify(infer_expr(argument, env, state, level), expected)
            return result
        case s.Tuple(items=items):
            return Con(TUPLE, tuple(infer_expr(i, env, state, level) for i in items))
        case s.ListLit(items=items):
            return Con("list", (_same_expr(items, env, state, level),))
        case s.ArrayLit(items=items):
            return Con("array", (_same_expr(items, env, state, level),))
        case s.Record(fields=fields, base=base):
            return _record(fields, base, env, state, level)
        case s.Apply(fn=fn, args=args):
            found = infer_expr(fn, env, state, level)
            for argument in args:
                given = _format(argument, found) or infer_expr(
                    argument, env, state, level
                )
                result = state.fresh(level)
                unify(found, Con(ARROW, (given, result)))
                found = result
            return found
        case s.BinOp(op=op, left=left, right=right):
            return _operator(env[op], [left, right], env, state, level)
        case s.UnOp(op=op, value=value):
            return _operator(state.unary[op], [value], env, state, level)
        case s.If(cond=cond, then=then, otherwise=otherwise):
            unify(infer_expr(cond, env, state, level), BOOL)
            found = infer_expr(then, env, state, level)
            if otherwise is None:
                unify(found, UNIT)
                return UNIT
            unify(found, infer_expr(otherwise, env, state, level))
            return found
        case s.Seq(items=items):
            found = UNIT
            for item in items:
                found = infer_expr(item, env, state, level)
            return found
        case s.LetIn(recursive=recursive, bindings=bindings, body=body):
            bound = infer_bindings(recursive, bindings, env, state, level)
            return infer_expr(body, env.new_child(dict(bound)), state, level)
        case s.Fun(params=params, body=body):
            return _function(params, body, env, state, level)
        case s.Function(cases=cases):
            argument = state.fresh(level)
            return Con(ARROW, (argument, _cases(cases, argument, env, state, level)))
        case s.Match(scrutinee=scrutinee, cases=cases):
            found = infer_expr(scrutinee, env, state, level)
            return _cases(cases, found, env, state, level)
        case s.Try(body=body, cases=cases):
            found = infer_expr(body, env, state, level)
            unify(found, _cases(cases, EXN, env, state, level))
            return found
        case s.While(cond=cond, body=body):
            unify(infer_expr(cond, env, state, level), BOOL)
            infer_expr(body, env, state, level)
            return UNIT
        case s.For(var=var, start=start, stop=stop, body=body):
            unify(infer_expr(start, env, state, level), INT)
            unify(infer_expr(stop, env, state, level), INT)
            inner = env.new_child({var.name: Scheme((), INT)})
            infer_expr(body, inner, state, level)
            return UNIT
        case s.GetField(value=value, label=label):
            given = infer_expr(value, env, state, level)
            owner, labels = _label(label, given, state, level)
            unify(given, owner)
            return labels[label][0]
        case s.SetField(value=value, label=label, rhs=rhs):
            given = infer_expr(value, env, state, level)
            owner, labels = _label(label, given, state, level)
            if not labels[label][1]:
                raise TypingError(f"the field {label} is not mutable")
            unify(given, owner)
            unify(infer_expr(rhs, env, state, level), labels[label][0])
            return UNIT
        case s.ArrayGet(array=array, index=index):
            element = state.fresh(level)
            unify(infer_expr(array, env, state, level), Con("array", (element,)))
            unify(infer_expr(index, env, state, level), INT)
            return element
        case s.ArraySet(array=array, index=index, rhs=rhs):
            element = state.fresh(level)
            unify(infer_expr(array, env, state, level), Con("array", (element,)))
            unify(infer_expr(index, env, state, level), INT)
            unify(infer_expr(rhs, env, state, level), element)
            return UNIT
        case s.StringGet(value=value, index=index):
            unify(infer_expr(value, env, state, level), STRING)
            unify(infer_expr(index, env, state, level), INT)
            return CHAR
        case s.Constraint(value=value, annot=annot):
            written = convert(annot, {}, state, level)
            unify(infer_expr(value, env, state, level), written)
            # The written type, so an abbreviation it names is what is printed.
            return written
    raise TypingError(f"no rule for {type(node).__name__}")


def _same_expr(items: list[Any], env: Env, state: State, level: int) -> Type:
    element = state.fresh(level)
    for item in items:
        unify(element, infer_expr(item, env, state, level))
    return element


def _operator(
    scheme: Scheme, operands: list[Any], env: Env, state: State, level: int
) -> Type:
    """An operator is a function, applied. `a + b` and `( + ) a b` agree
    because they take the same scheme from the same table."""
    found = instantiate(scheme, level, state.fresh)
    for operand in operands:
        result = state.fresh(level)
        unify(found, Con(ARROW, (infer_expr(operand, env, state, level), result)))
        found = result
    return found


def _function(params: list[Any], body: Any, env: Env, state: State, level: int) -> Type:
    holes: Holes = {}
    taken = [infer_pattern(p, holes, state, level) for p in params]
    inner = env.new_child({n: Scheme((), t) for n, t in holes.items()})
    return arrow(*taken, infer_expr(body, inner, state, level))


def _cases(
    cases: list[s.Case], subject: Type, env: Env, state: State, level: int
) -> Type:
    result = state.fresh(level)
    for case in cases:
        holes: Holes = {}
        unify(subject, infer_pattern(case.pattern, holes, state, level))
        inner = env.new_child({n: Scheme((), t) for n, t in holes.items()})
        if case.guard is not None:
            unify(infer_expr(case.guard, inner, state, level), BOOL)
        unify(result, infer_expr(case.body, inner, state, level))
    return result


def _label(
    label: str, known: Type, state: State, level: int
) -> tuple[Type, dict[str, tuple[Type, bool]]]:
    return _open_record(state.decls.record_of([label], known), state, level)


def _record(
    fields: list[s.FieldBind], base: Any, env: Env, state: State, level: int
) -> Type:
    given = None if base is None else infer_expr(base, env, state, level)
    record = state.decls.record_of([f.label for f in fields], given)
    owner, labels = _open_record(record, state, level)
    for entry in fields:
        unify(infer_expr(entry.value, env, state, level), labels[entry.label][0])
    if given is not None:
        unify(given, owner)
    elif {f.label for f in fields} != set(labels):
        missing = sorted(set(labels) - {f.label for f in fields})
        raise TypingError(f"this record is missing {missing}")
    return owner


# ---------------------------------------------------------------- bindings


def is_value(node: Any) -> bool:
    """Whether generalizing this is sound.

    The value restriction, syntactically: `let r = ref []` must not
    generalize, or `r` could be filled with an int and read as a string.
    OCaml's relaxed rule admits more; this one admits what a prépa programme
    writes, and `specification.md`, *Typing*, says so.
    """
    match node:
        case s.Int() | s.Float() | s.Char() | s.Str() | s.Bool() | s.Unit():
            return True
        case s.Var() | s.Fun() | s.Function():
            return True
        case s.Construct(args=args):
            return all(is_value(a) for a in args)
        case s.Tuple(items=items) | s.ListLit(items=items):
            return all(is_value(i) for i in items)
        case s.Constraint(value=value):
            return is_value(value)
    return False


def infer_binding(
    binding: s.Binding, target: Type, env: Env, state: State, level: int
) -> Type:
    """The type of one `let` binding's right-hand side.

    `let f x : t = e` annotates the **result**, not `f`: OCaml reads the
    annotation as the type of `e`, so with parameters it constrains the body
    and without them it constrains the value. Typing `let translate (dx :
    float) (dy : float) : transform = ...` the other way is what found it.
    """
    holes: Holes = {}
    taken = [infer_pattern(p, holes, state, level) for p in binding.params]
    written = binding.annot
    result = (
        state.fresh(level) if written is None else convert(written, {}, state, level)
    )
    # What the parameters and the annotation say is settled before the body
    # is read, as OCaml settles it: a recursive call inside then meets
    # `word` where the programme wrote `word`, and the signature says so.
    whole = arrow(*taken, result)
    unify(target, whole)
    inner = env.new_child({n: Scheme((), t) for n, t in holes.items()})
    unify(infer_expr(binding.value, inner, state, level), result)
    return whole


def infer_bindings(
    recursive: bool,
    bindings: list[s.Binding],
    env: Env,
    state: State,
    level: int,
) -> list[tuple[str, Scheme]]:
    """The names one `let` introduces, with their schemes.

    `recursive` decides which environment the right-hand sides see, which is
    the difference the scope declaration in `grammar.py` cannot express and
    the reason it is written out here.
    """
    inner = level + 1
    # Each binding's pattern is inferred **once**, and its type is what the
    # right-hand side is unified with. Inferring it a second time to get a
    # target left the recursive occurrence linked to nothing, so
    # `let rec f x = f` typed and `let rec f n = if n = 0 then "" else f true`
    # did too. The occurs check found it, by not firing.
    shapes: list[tuple[Type, Holes]] = []
    for binding in bindings:
        holes: Holes = {}
        shapes.append((infer_pattern(binding.pattern, holes, state, inner), holes))
    if recursive:
        mono = {n: Scheme((), t) for _, holes in shapes for n, t in holes.items()}
        scope = env.new_child(mono)
        for binding, (target, _) in zip(bindings, shapes, strict=True):
            infer_binding(binding, target, scope, state, inner)
    else:
        for binding, (target, _) in zip(bindings, shapes, strict=True):
            infer_binding(binding, target, env, state, inner)
    out: list[tuple[str, Scheme]] = []
    for binding, (_, holes) in zip(bindings, shapes, strict=True):
        keep = bool(binding.params) or is_value(binding.value)
        for name, found_type in holes.items():
            out.append((
                name,
                generalize(found_type, level)
                if keep
                else Scheme((), resolved(found_type)),
            ))
    return out


# ------------------------------------------------------------------- items


def infer_item(
    node: Any, env: Env, state: State
) -> tuple[list[tuple[str, Scheme]], Env]:
    """What this item binds, and the scope after it.

    A `let` opens a new scope rather than writing into the one it was given,
    which is the shape `interpret.run_item` needs and the one this keeps so
    the two read alike.
    """
    match node:
        case s.LetItem(recursive=recursive, bindings=bindings):
            bound = infer_bindings(recursive, bindings, env, state, 0)
            return bound, env.new_child(dict(bound))
        case s.TypeItem(defs=defs):
            declare_types(defs, state)
            return [], env
        case s.ExnItem():
            declare_exception(node, state)
            return [], env
        case s.ExprItem(value=value):
            infer_expr(value, env, state, 0)
            return [], env
    raise TypingError(f"no rule for {type(node).__name__}")


def infer_structure(
    structure: s.Structure, state: State | None = None
) -> list[tuple[str, Scheme]]:
    """Every top-level name, with its scheme, in source order."""
    state = state if state is not None else State()
    env = prelude(state)
    out: list[tuple[str, Scheme]] = []
    for item in structure.items:
        bound, env = infer_item(item, env, state)
        out += bound
    return out


def signature(structure: s.Structure) -> list[str]:
    """The `val` lines `ocamlc -i` prints for this structure."""
    return [
        f"val {name} : {show_scheme(scheme)}"
        for name, scheme in infer_structure(structure)
    ]
