"""Emission as a declaration: one rule per production, guarded.

All three compilers in the corpus emit a *language*, not machine code, so
there is no register allocation, no scheduling and no cost model. What is left
is producing text with the children in the right places, bracketed and laid
out, and that is written today as `match`, `isinstance` and f-strings, once
per target.

A rule is a production name, a template, and an optional guard:

    JS.rule("BinOp", "{left} {op} {right}", when=Both(NUMERIC))
    JS.rule("BinOp", "_pyfunc_op_{op:name}({left}, {right})")

Rules are tried in order and the first whose guard holds wins, as in
`astero.python.rewriting`. A rule with no guard always holds, so it goes last and
gives the production an answer; a production with no answer at all is a hole
the coverage check reports rather than a `NotImplementedError` in someone's
program.

`{field}` emits that child and **brackets it if the precedence table says
so**, which is the part the grammar and `astero.emit` already know. `{field:x}`
is a projection when `x` is a declared projection name and a separator
otherwise, so `{args:, }` joins a sequence and `{result:type}` runs the
target's type spelling. `{field?}` omits an absent optional field.

A template cannot call, branch or hold state. Everything conditional is a
guard from the closed vocabulary below, and everything computed is a
projection declared once by name. That restriction is the same one
`Present`/`Absent` puts on the grammar, and Parr's on StringTemplate: a
template that can compute stops being a specification of output.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from astero.emit import (
    ATOM,
    FREE,
    Concat,
    Doc,
    Level,
    Line,
    Nest,
    Text,
    line,
    needs_parens,
    render,
    spans,
    text,
)
from astero.grammar import Grammar

_HOLE = re.compile(r"\{(&?\w+)(\?)?(?::([^}]*))?\}")

# `{{` and `}}` are literal braces, as in `str.format`. A target with object
# literals needs them: `Object.assign([{elts:, }], {{_is_list: true}})` was
# read as a hole named `_is_list` until this existed. They are normalised to
# single characters so the hole scan and the bracket depth scan see one token,
# and restored when the literal text is emitted.
_ESC_OPEN, _ESC_CLOSE = "\x01", "\x02"


def _normalise(template: str) -> str:
    return template.replace("{{", _ESC_OPEN).replace("}}", _ESC_CLOSE)


def _literal(text_: str) -> Doc:
    """A template's literal text, with its newlines as document breaks.

    A newline written in a template is *structure*: it separates one emitted
    line from the next. A newline that arrives inside a value is not — a string
    literal may contain one. Keeping the first as `Line` and the second as
    `Text` is what lets `to_lines` split soundly where `str.splitlines` cannot.
    """
    plain = text_.replace(_ESC_OPEN, "{").replace(_ESC_CLOSE, "}")
    parts = plain.split("\n")
    out = text(parts[0])
    for part in parts[1:]:
        out += line() + text(part)
    return out


# ----------------------------------------------------------------- guards
#
# Closed on purpose. A guard that admits host code readmits what the
# declaration exists to remove, and the rule set stops being readable as a
# table. Every branch in the corpus's operator emitters is one of these.


def _is_one_of(value: Any, types: tuple[Any, ...]) -> bool:
    """Whether an inferred type is one of the declared ones.

    Two type systems reach here and they answer differently. prescrypt-ng's
    `get_type` returns the class itself, so `Int in (Int, Float)` is the test.
    p2w's `get_expr_type` returns an *instance*, `FloatType()`, and a bare `in`
    is False against `(FloatType, IntType)` for every value. A declared type
    matches when the value is it, or is an instance of it; both are the same
    sentence read from the two sides, and neither back end has to translate.
    """
    if value in types:
        return True
    return any(isinstance(value, t) for t in types if isinstance(t, type))


@dataclass(frozen=True)
class Is:
    """The inferred type of `field` is one of `types`."""

    field: str
    types: tuple[Any, ...]

    def holds(self, node: ast.AST, ctx: Emitter) -> bool:
        return _is_one_of(ctx.type_of(getattr(node, self.field, None)), self.types)


@dataclass(frozen=True)
class Both:
    """Both operands of a binary production have one of `types`."""

    types: tuple[Any, ...]
    fields: tuple[str, str] = ("left", "right")

    def holds(self, node: ast.AST, ctx: Emitter) -> bool:
        return all(
            _is_one_of(ctx.type_of(getattr(node, f, None)), self.types)
            for f in self.fields
        )


@dataclass(frozen=True)
class OpIs:
    """The production's operator field is one of `ops`."""

    ops: tuple[type, ...]
    field: str = "op"

    def holds(self, node: ast.AST, _ctx: Emitter) -> bool:
        return isinstance(_only(getattr(node, self.field, None)), self.ops)


@dataclass(frozen=True)
class Const:
    """`field` is a literal, optionally of a given Python type."""

    field: str
    of: type | None = None

    def holds(self, node: ast.AST, _ctx: Emitter) -> bool:
        value = getattr(node, self.field, None)
        if not isinstance(value, ast.Constant):
            return False
        return self.of is None or isinstance(value.value, self.of)


@dataclass(frozen=True)
class Has:
    """The field is present and not empty.

    The same question `Present` asks in the grammar, and for the same reason:
    `yield` with a value and `yield` without are two spellings, not one
    spelling with an optional hole, because the second has no trailing space.
    """

    field: str

    def holds(self, node: ast.AST, _ctx: Emitter) -> bool:
        return bool(getattr(node, self.field, None))


@dataclass(frozen=True)
class All:
    """Every guard holds. `Any` is the other connective."""

    guards: tuple[Guard, ...]

    def holds(self, node: ast.AST, ctx: Emitter) -> bool:
        return all(g.holds(node, ctx) for g in self.guards)


@dataclass(frozen=True)
class Either:
    """At least one guard holds."""

    guards: tuple[Guard, ...]

    def holds(self, node: ast.AST, ctx: Emitter) -> bool:
        return any(g.holds(node, ctx) for g in self.guards)


@dataclass(frozen=True)
class Not:
    """The guard does not hold.

    A connective rather than a new predicate, which matters: the atoms stay
    four. `can_use_strict_equality` is expressible without it, as a
    disjunction of two `Both`s, and unreadably so.
    """

    guard: Guard

    def holds(self, node: ast.AST, ctx: Emitter) -> bool:
        return not self.guard.holds(node, ctx)


Guard = Is | Both | OpIs | Const | Has | All | Either | Not


# ------------------------------------------------------------------ rules


@dataclass(frozen=True)
class Rule:
    production: str
    template: str
    when: Guard | None = None
    origin: str = ""

    def applies(self, node: ast.AST, ctx: Emitter) -> bool:
        return self.when is None or self.when.holds(node, ctx)

    def __str__(self) -> str:
        guard = "" if self.when is None else f"   when {type(self.when).__name__}"
        return f"{self.production:14} {self.template}{guard}"


def _only(value: Any) -> Any:
    """A one-element sequence stands for its element.

    `Compare` holds lists because Python chains comparisons, and every
    compiler in the corpus desugars the chain before emitting, so asking about
    "the operator" or "the right operand" of a Compare is well defined. A
    longer list is left alone and will simply not match.
    """
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _all_holes_bracketed(template: str) -> bool:
    """Whether every hole sits inside a bracket the template opened.

    Such a result is an atom however loosely its parts bind, because the
    template's own brackets already hold it together.
    """
    masked = _mask(template)
    depth = 0
    seen = False
    for char in masked:
        if char in _OPENS:
            depth += 1
        elif char in _CLOSES:
            depth -= 1
        elif char == "\x00":
            seen = True
            if depth <= 0:
                return False
    return seen


_OPENS = "([{" + _ESC_OPEN
_CLOSES = ")]}" + _ESC_CLOSE


def _mask(template: str) -> str:
    """The template with each hole replaced by one placeholder character.

    The holes are written with braces, which are also target syntax, so the
    scan below has to be able to tell them apart.
    """
    return _HOLE.sub("\x00", template)


def _delimited(template: str, hole: re.Match[str]) -> bool:
    """Whether a separator or bracket stands on each side of this hole.

    Not depth: `Math.floor({left}/{right})` has both holes inside a bracket
    and a `/` between them, whose precedence the declaration never states, so
    treating them as delimited emitted `Math.floor(hi - lo/2)` for
    `Math.floor((hi - lo)/2)`. A hole is free of brackets only when nothing
    but a separator sits beside it.
    """
    masked = _mask(template)
    index = len(_mask(template[: hole.start()]))
    before = masked[:index].rstrip()
    after = masked[index + 1 :].lstrip()
    left = not before or before[-1] in _OPENS + ","
    right = not after or after[0] in _CLOSES + ","
    return left and right


def _at(doc: Doc, node: Any) -> Doc:
    """Tag `doc` with where `node` came from, when the node knows.

    `lineno`/`col_offset` is the position CPython records and what
    `astero.python.emit` already puts in a span, so a consumer reading either gets the
    same convention. A synthesized node carries neither and is left alone,
    rather than given a position it does not have.
    """
    line = getattr(node, "lineno", None)
    col = getattr(node, "col_offset", None)
    if line is None or col is None:
        return doc
    return dataclasses.replace(doc, span=(line, col))


class EmitError(Exception):
    """No rule applied, or a template named something the grammar lacks."""


@dataclass
class Emitter:
    """A target's emission rules, over one grammar."""

    grammar: Grammar
    #: Binding power per production or per operator class. None for a target
    #: whose syntax is self-bracketing, such as WebAssembly text.
    levels: Mapping[Any, Level] | None = None
    rules: list[Rule] = field(default_factory=list)
    projections: dict[str, Callable[[Any], str]] = field(default_factory=dict)
    #: How to ask for a node's inferred type. The one hook into host analysis.
    typer: Callable[[Any], Any] | None = None
    #: What to do with a production that has no rule. Without one, a missing
    #: rule is an error; with one, the host's existing generator handles it,
    #: which is how a back end is converted a production at a time rather than
    #: all at once. Its result is taken as already bracketed.
    fallback: Callable[[Any], str] | None = None
    #: The prefix for labels a `{&name}` hole generates.
    label_prefix: str = "L"
    _labels: dict[tuple[int, str], str] = field(default_factory=dict)
    _pinned: list[Any] = field(default_factory=list)
    _counter: int = 0

    def rule(
        self, production: str, template: str, when: Guard | None = None
    ) -> Emitter:
        if production not in self.grammar:
            raise EmitError(
                f"grammar {self.grammar.name!r} has no production {production!r}"
            )
        for name, _opt, _spec in _HOLE.findall(_normalise(template)):
            if name.startswith("&"):
                continue  # a label, not a field
            if self.grammar[production].field(name) is None:
                raise EmitError(f"{production} has no field {name!r}: {template!r}")
        self.rules.append(Rule(production, template, when))
        return self

    def projection(self, name: str, fn: Callable[[Any], str]) -> Emitter:
        self.projections[name] = fn
        return self

    def type_of(self, node: Any) -> Any:
        return self.typer(_only(node)) if self.typer is not None else None

    # ------------------------------------------------------------ emitting

    def declared_level(self, node: Any) -> Level | None:
        """The binding power the table gives `node`, or None if it gives none.

        Undeclared is not a level, and the two questions below answer it
        differently, so the lookup is separate from both.
        """
        if self.levels is None or not isinstance(node, ast.AST):
            return None
        # A production's binding power may be keyed on its operator rather
        # than on itself, and `Compare` carries a *list* of operators because
        # Python chains them, so all three places are looked at.
        ops = getattr(node, "ops", None)
        candidates = (
            getattr(node, "op", None),
            ops[0] if isinstance(ops, list) and ops else None,
            node,
        )
        for key in candidates:
            found = self.levels.get(type(key)) if key is not None else None
            if found is not None:
                return found
        return None

    def level_of(self, node: Any) -> Level:
        """How tightly `node` binds *as emitted*.

        Which rule fires decides this, not the node alone: `a + b` spelled
        `a + b` binds at the `+` level, and spelled `_pyfunc_op_add(a, b)` it
        is an atom. Reading the node alone bracketed the call.

        Undeclared means `ATOM` here: a production the table omits is emitted
        as a primary, so nothing brackets it.
        """
        rule = self._chosen(node)
        if rule is not None and _all_holes_bracketed(_normalise(rule.template)):
            return ATOM
        declared = self.declared_level(node)
        return ATOM if declared is None else declared

    def inner_level(self, node: Any) -> Level:
        """How tightly the operator *inside* a template binds.

        Not the same question as `level_of`, and undeclared means the opposite
        thing: a production the table omits imposes nothing on its holes. A
        statement is the case that matters, and it is most of a target. `t = 0`
        came out `t = (0)` and `return n * 2` came out `return (n * 2)`,
        because `Assign` and `Return` are in no precedence table, and the
        missing entry was read as `ATOM`, the tightest context there is,
        rather than as no context at all.

        `//` emitted as `Math.floor({left}/{right})` is why this is not simply
        `level_of`: the result is an atom and the holes sit either side of a
        `/`, so bracketing them against the atom gave `Math.floor((hi - lo)/(2))`.
        """
        declared = self.declared_level(node)
        return FREE if declared is None else declared

    def emit(
        self, node: Any, outer: Level | None = None, *, right: bool = False
    ) -> Doc:
        """The text for `node`, bracketed for the context it sits in."""
        body = self._body(node)
        if outer is None or self.levels is None:
            return body
        if needs_parens(self.level_of(node), outer, on_right=right):
            return text("(") + body + text(")")
        return body

    def _body(self, node: Any) -> Doc:
        name = type(node).__name__
        for rule in self.rules:
            if rule.production == name and rule.applies(node, self):
                return _at(self._fill(rule, node), node)
        if self.fallback is not None:
            return _at(text(self.fallback(node)), node)
        raise EmitError(f"no rule for {name} in {self.grammar.name!r}")

    def source_map(self, node: Any) -> list[tuple[int, int, tuple[int, int]]]:
        """(start, end, (line, column)) for every emitted node with a position.

        `start` and `end` index `to_text(node)`, and the pair is where in the
        source that text came from. A source map is this list in whatever
        encoding the target wants.

        Every rule's output carries the position of the node it emitted, so
        this needs no cooperation from the rules and no extra hole. A node
        the host built rather than parsed has no position and contributes
        nothing, which is why the list is usually shorter than the tree.
        """
        return list(spans(self.emit(node)))

    def label(self, node: Any, name: str) -> str:
        """A label unique to `node`, stable for the same `name`.

        A statement that branches needs somewhere to jump to, and the same
        label appears twice: once where it is defined and once where it is
        named. `{&done}` gives both the same text, and a second `While` in the
        same function gets a different one.

        This is what a flat target was missing. Statement *structure* already
        worked — a body hole renders the list, and a newline separator joins
        it — so `while` on a stack machine is a template like any other:

            "{&top}:\n{test}\nJZ {&done}\n{body:\n}\nJMP {&top}\n{&done}:"
        """
        # Keyed on identity, so the node has to be kept alive: a tree that is
        # collected frees its addresses, and the next tree reuses them. On
        # 3.11 that happened between two `to_text` calls and the second `While`
        # got the first one's labels.
        key = (id(node), name)
        if key not in self._labels:
            self._counter += 1
            self._labels[key] = f"{self.label_prefix}{self._counter}"
            self._pinned.append(node)
        return self._labels[key]

    def _fill(self, rule: Rule, node: ast.AST) -> Doc:
        here = self.inner_level(node)
        template = _normalise(rule.template)
        out = text("")
        last = 0
        holes = list(_HOLE.finditer(template))
        for index, m in enumerate(holes):
            out += _literal(template[last : m.start()])
            # A hole the template itself delimits needs no brackets of its own:
            # `f({args:, })` already separates its arguments, so an argument is
            # emitted at atom level however loosely it binds. That is the same
            # fact a grammar states by wrapping a nonterminal in literal
            # tokens, read off the template instead.
            context = None if _delimited(template, m) else here
            # Which side of the operator a hole sits on comes from the
            # template, not from the production's field list: `!{operand}` has
            # one operand and `UnaryOp` has two fields, and reading the fields
            # made `not a` into `!(a)`.
            on_right = len(holes) > 1 and index == len(holes) - 1
            name, optional, spec = m.groups()
            if name.startswith("&"):
                out += text(self.label(node, name[1:]))
                last = m.end()
                continue
            out += self._hole(
                node,
                context,
                on_right=on_right,
                name=name,
                optional=optional,
                spec=spec,
            )
            last = m.end()
        return out + _literal(template[last:])

    def _hole(
        self,
        node: ast.AST,
        here: Level | None,
        *,
        on_right: bool,
        name: str,
        optional: str | None,
        spec: str | None,
    ) -> Doc:
        value = getattr(node, name, None)
        if value is None:
            if optional:
                return text("")
            raise EmitError(f"{type(node).__name__}.{name} is absent and not optional")
        projection = self.projections.get(spec) if spec is not None else None
        if projection is not None and not isinstance(value, list):
            return text(projection(value))
        if isinstance(value, list):
            # A projection over a sequence maps, so `{ops:sym}` spells each
            # operator of a chained comparison rather than the list itself.
            sep = "" if projection is not None else (spec if spec is not None else ", ")
            parts = [
                text(projection(v)) if projection is not None else self.emit(v, here)
                for v in value
            ]
            # The separator is template text like any other, so a newline in
            # it is a document break rather than a character. `{body:\n}` on a
            # statement list is what made this matter: joined as text, the last
            # line of one statement and the first of the next became one.
            joined = text("")
            for i, part in enumerate(parts):
                joined += (_literal(sep) if i else text("")) + part
            return joined
        return self.emit(value, here, right=on_right)

    def to_text(self, node: Any) -> str:
        return render(self.emit(node))

    def to_lines(self, node: Any) -> list[str]:
        """The emitted lines, split where the *templates* said to.

        `to_text(node).splitlines()` is the obvious thing and it is wrong as
        soon as a value contains a newline: a string literal splits into two
        instructions. This walks the document, so only a break a template
        wrote is a break.
        """
        lines: list[str] = [""]

        def walk(doc: Doc) -> None:
            match doc:
                case Text(text=text):
                    lines[-1] += text
                case Concat(parts=parts):
                    for part in parts:
                        walk(part)
                case Line():
                    lines.append("")
                case Nest(doc=inner):
                    # `emit_rules` writes no `Nest`; a document built
                    # elsewhere and handed here may contain one, and its
                    # content is still flat as far as lines are concerned.
                    walk(inner)
                case _:
                    # `Doc` is a base class, not a closed union, so a new
                    # subclass reaches here. Saying so beats the `else` this
                    # replaced, which read `doc.doc` off whatever arrived.
                    raise TypeError(f"unhandled document {type(doc).__name__}")

        walk(self.emit(node))
        return lines

    def _chosen(self, node: Any) -> Rule | None:
        name = type(node).__name__
        for rule in self.rules:
            if rule.production == name and rule.applies(node, self):
                return rule
        return None

    def covered_by_rule(self, node: Any) -> bool:
        name = type(node).__name__
        return any(r.production == name and r.applies(node, self) for r in self.rules)

    def covered(self) -> frozenset[str]:
        return frozenset(r.production for r in self.rules)

    def __str__(self) -> str:
        return "\n".join(str(r) for r in self.rules)
