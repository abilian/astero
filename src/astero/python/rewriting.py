"""Rewrite rules over Python ASTs.

A pass is a named rule set plus a traversal strategy. A rule is one string, with
`=>` between the pattern and its replacement:

    rule("hypot(_x, _y) => sqrt(_x ** 2 + _y ** 2)")

Several at once, one per line:

    rules('''
        exp(_x)   => e ** _x
        expm1(_x) => exp(_x) - 1
    ''')

Both sides are Python source. Identifiers spelled `_[a-z]...` are
metavariables: in expression position one binds a node, in an identifier field
(`Attribute.attr`, `arg.arg`, `FunctionDef.name`) it binds a string. A
metavariable used twice must bind equal subtrees. `_` on its own matches
anything and binds nothing. `*_xs` binds the rest of an argument list and
`**_kw` the rest of a keyword list, with `*_` and `**_` for the anonymous
cases, so `exp(_x, **_)` reads as "exp of one argument, whatever the keywords".

Where concrete Python syntax cannot say what a rule means (an operator hole, a
node constrained on some of its fields), write abstract syntax with an explicit
`ast.` prefix, positionally in field order or by keyword:

    rule("ast.AugAssign(_t, _o, _v) => ast.Assign([_t], ast.BinOp(_t, _o, _v))")

An abstract term constrains only the fields it names.

A rewrite no template can express, typically a fold over a list of arbitrary
length, carries its pattern on the function that performs it, and joins the
set through `rules`:

    @rewrite("ast.BoolOp(_o, _v)")
    def nest(m):
        ...                     # return the replacement, or None to decline

    rules('''
        -_x => 0 - _x
    ''', nest)

Rules never mention `ctx` or source positions. Both are derived from the shape
of the tree and reinstalled after rewriting.

`print(some_pass)` lists its rules. A rule that fails to compile names where it
was written, and each `Rule` keeps that location in `origin`.
"""

from __future__ import annotations

import ast
import copy
import enum
import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

from astero.grammar import Grammar, Kind
from astero.python.lang import PY, VARS

_META = re.compile(r"^_[a-z]\w*$")

# Matches anything, binds nothing.
WILDCARD = "_"

ARROW = "=>"

# Derived fields: never matched on, recomputed after rewriting.
DERIVED = frozenset({
    "ctx",
    "lineno",
    "col_offset",
    "end_lineno",
    "end_col_offset",
    "type_comment",
})

# A rewrite chain longer than this at one position means a cyclic rule set.
_MAX_CHAIN = 100

# Sentinel right-hand side: drop the matched node from its enclosing list.
DELETE = object()

# The productions carrying a `ctx` field. Written out so type checkers can
# narrow on it, and gated against the grammar by `test_ctx_nodes_matches_the_grammar`
# so the list cannot drift when Python gains a production.
CTX_NODES = (
    ast.Attribute,
    ast.List,
    ast.Name,
    ast.Starred,
    ast.Subscript,
    ast.Tuple,
)

# What a Python AST field holds when it holds neither a node nor a list: the
# constants `ast.Constant` admits, the identifiers, and the plain ints. CPython
# closes this set in its ASDL but exposes no list of it, so it is written out,
# and `test_copy_tree_leaves.py` gates it against the standard library the way
# `CTX_NODES` is gated against the parser. `bool` is absent because it is an
# `int`, and `type(Ellipsis)` has no builtin name.
#
# Only `copy_tree` without a grammar reads this, and only it can: the value
# space of a field is closed for Python and open for any other language, where
# an attr may hold whatever the host declares — an enum member, most often. So
# `_copy_declared` keeps passing an unrecognised value through, and this list
# stays a fact about Python rather than a rule about trees.
LEAVES = (str, bytes, int, float, complex, type(None), type(Ellipsis))

# Every production of Python's grammar, by name, for resolving `ast.Cls(...)`.
AST_CLASSES = {
    name: c
    for name, c in vars(ast).items()
    if isinstance(c, type) and issubclass(c, ast.AST)
}


class Strategy(enum.Enum):
    """Where in the traversal a rule set is applied.

    INNERMOST: children first, then re-apply at the node until nothing fires.
    TOPDOWN:   apply once at the node, then continue into the result.
    OUTERMOST: apply at the shallowest matching nodes and stop there.
    """

    INNERMOST = "innermost"
    TOPDOWN = "topdown"
    OUTERMOST = "outermost"


def _is_meta(name: Any) -> bool:
    return isinstance(name, str) and _META.match(name) is not None


def _is_hole(name: Any) -> bool:
    """A metavariable or the anonymous wildcard."""
    return _is_meta(name) or name == WILDCARD


def _splice(node: Any) -> str | None:
    """Name spliced by a `*_xs` or `**_kw` element, or None if not a splice."""
    match node:
        case ast.Starred():
            inner: Any = node.value
        case ast.keyword(arg=None):
            inner = node.value
        case _:
            return None
    return inner.id if isinstance(inner, ast.Name) and _is_hole(inner.id) else None


def key(node: Any, ignore: frozenset = DERIVED) -> Any:
    """Structural key over a tree, skipping `ignore`d fields."""
    match node:
        case ast.AST():
            return (
                type(node).__name__,
                *(
                    key(getattr(node, f, None), ignore)
                    for f in node._fields
                    if f not in ignore
                ),
            )
        case list():
            return tuple(key(x, ignore) for x in node)
    return node


# --------------------------------------------------------------------- patterns


@dataclass(frozen=True)
class Term:
    """Abstract-syntax pattern: matches `cls`, constraining only `fields`."""

    cls: type
    fields: tuple[tuple[str, Any], ...]


def _as_term(node: Any) -> Term | None:
    """Read `ast.Cls(...)` as an abstract pattern.

    Positional patterns bind to `cls._fields` in order; keyword patterns name
    their field. Fields left out are unconstrained.
    """
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)):
        return None
    if func.value.id != "ast":
        return None
    cls = AST_CLASSES.get(func.attr)
    if cls is None:
        raise ValueError(f"unknown AST class: ast.{func.attr}")
    if len(node.args) > len(cls._fields):
        raise ValueError(
            f"ast.{func.attr} has fields {cls._fields}, "
            f"got {len(node.args)} positional patterns"
        )
    fields: list[tuple[str, Any]] = [
        (name, _compile(arg, True))
        # Fewer positional patterns than fields is the point: a term
        # constrains only what it names.
        for name, arg in zip(cls._fields, node.args, strict=False)
    ]
    fields += [(kw.arg, _compile(kw.value, True)) for kw in node.keywords if kw.arg]
    return Term(cls, tuple(fields))


def _compile(node: Any, abstract: bool = False) -> Any:
    """Rewrite abstract-syntax calls into Terms, in place.

    Inside an abstract term a list display denotes a sequence of patterns and a
    literal denotes a plain field value, so `ast.Assign([_t])` and
    `ast.Name("x")` constrain those fields rather than matching `ast.List` and
    `ast.Constant` nodes. Write `ast.List(elts=[...])` and
    `ast.Constant(value=...)` for the latter.
    """
    term = _as_term(node)
    if term is not None:
        return term
    match node:
        case ast.List() if abstract:
            return [_compile(e, True) for e in node.elts]
        case ast.Constant() if abstract:
            return node.value
        case ast.AST():
            for f in node._fields:
                setattr(node, f, _compile(getattr(node, f, None), abstract))
            return node
        case list():
            return [_compile(x, abstract) for x in node]
    return node


# ---------------------------------------------------------------------- match


def match(pat: Any, node: Any) -> dict[str, Any] | None:
    """Match `node` against pattern `pat`; return bindings, or None."""
    binds: dict[str, Any] = {}
    return binds if _match(pat, node, binds) else None


def _match(pat: Any, node: Any, binds: dict[str, Any]) -> bool:
    match pat:
        case ast.Name() if _is_hole(pat.id):
            return _bind(binds, pat.id, node)
        case Term():
            return isinstance(node, pat.cls) and all(
                _match(p, getattr(node, f, None), binds) for f, p in pat.fields
            )
        case str():
            return _bind(binds, pat, node) if _is_hole(pat) else pat == node
        case ast.AST():
            # `isinstance`, not `type(...) is ...`: a host's generated node classes
            # subclass CPython's, and a pattern written in concrete syntax is built
            # by CPython's parser. Exact identity made those patterns silently fail
            # to match on a host tree while abstract terms matched, so `-_x` did
            # nothing where `ast.UnaryOp(...)` worked.
            return isinstance(node, type(pat)) and all(
                _match(getattr(pat, f, None), getattr(node, f, None), binds)
                for f in pat._fields
                if f not in DERIVED
            )
        case list():
            return isinstance(node, list) and _match_list(pat, node, binds)
    return pat == node


def _match_list(pat: list, node: list, binds: dict[str, Any]) -> bool:
    star = next((i for i, p in enumerate(pat) if _splice(p) is not None), None)
    if star is None:
        return len(pat) == len(node) and all(
            _match(p, n, binds) for p, n in zip(pat, node, strict=True)
        )
    head, tail = pat[:star], pat[star + 1 :]
    if len(node) < len(head) + len(tail):
        return False
    cut = len(node) - len(tail)
    name = _splice(pat[star])
    assert name is not None
    return (
        # head matches a prefix of node; tail matches a slice cut to its length.
        all(_match(p, n, binds) for p, n in zip(head, node, strict=False))
        and all(_match(p, n, binds) for p, n in zip(tail, node[cut:], strict=True))
        and _bind(binds, name, node[len(head) : cut])
    )


def _bind(binds: dict[str, Any], name: str, value: Any) -> bool:
    if name == WILDCARD:
        return True
    if name in binds:
        return key(binds[name]) == key(value)
    binds[name] = value
    return True


# ---------------------------------------------------------------------- build


def copy_tree(node: Any, grammar: Grammar | None = None) -> Any:
    """Copy a node along its declared fields and source positions.

    `copy.deepcopy` follows every attribute an object has, which is wrong for a
    syntax tree that a host has decorated. prescrypt-ng's converter gives each
    node a `_parent` back-pointer, so deep-copying any node copied the entire
    module, and the whole enclosing CPython tree with it through `_orig_node`.
    Desugaring one 400-line file took 1.6 seconds and grew faster than the
    square of its size.

    A node's parts are what the grammar says they are. Everything a host hangs
    off a node besides that is its own bookkeeping, and a pass that rebuilds
    the syntax is not entitled to guess whether it still applies.

    **Pass `grammar` for a tree that is not Python's.** Without it the fields
    come from `node._fields`, which only a Python AST has, so a node of any
    other kind cannot be copied here and is refused by name rather than handed
    back — returning it unchanged aliases the original, and a caller that then
    mutates its "copy" has mutated the input. `ast.walk` in `hygiene` and
    `ast.iter_fields` in `scopes` made the same mistake and answered emptily,
    which is wrong but harmless; this one corrupted.

    The two paths are not two thoroughnesses of one copy, and the parameter is
    not an optimisation. **They produce different trees on purpose.** A
    declared copy carries what the grammar declares, and the declaration omits
    what is derived, so `copy_tree(t, PY)` returns a `Name` with no `ctx` and
    a `FunctionDef` with no `type_comment`: correct for a pass that runs
    `fix_contexts` afterwards, uncompilable for one that does not. Choose by
    which tree you want, not by which is safer.
    """
    if grammar is not None:
        return _copy_declared(node, grammar)
    match node:
        case ast.AST():
            out = type(node)(**{
                f: copy_tree(getattr(node, f)) for f in node._fields if hasattr(node, f)
            })
            return ast.copy_location(out, node)
        case list():
            return [copy_tree(x) for x in node]
        case _ if isinstance(node, LEAVES):
            return node
    raise TypeError(
        f"copy_tree cannot copy a {type(node).__name__}: it is not a Python AST "
        "node, a list, or a value one can hold. Pass `grammar=` to copy a tree "
        "the grammar declares."
    )


def _copy_declared(node: Any, grammar: Grammar) -> Any:
    """`copy_tree` over whatever the grammar declares, Python's tree or not."""
    if isinstance(node, list):
        return [_copy_declared(x, grammar) for x in node]
    prod = grammar.productions.get(type(node).__name__)
    if prod is None:
        return node
    parts = {}
    for f in prod.fields:
        if not hasattr(node, f.name):
            continue
        value = getattr(node, f.name)
        # A reference sort is a leaf the grammar can name, and it has to be
        # copied rather than shared: `rename` rewrites the object in place, so
        # a clone sharing one would rename its original too. That aliasing is
        # what postpile's `_rename_instr` keeps a per-clone cache to avoid.
        parts[f.name] = (
            _copy_references(value)
            if f.sort in grammar.reference_sorts
            else _copy_declared(value, grammar)
        )
    out = type(node)(**parts)
    return ast.copy_location(out, node) if isinstance(node, ast.AST) else out


def _copy_references(value: Any) -> Any:
    """A reference object, or a list of them, copied one level."""
    if isinstance(value, list):
        return [_copy_references(x) for x in value]
    return copy.copy(value) if value is not None else None


def _ctor(cls: type, grammar: Grammar | None) -> type:
    """The class `grammar` builds `cls`'s production with.

    A pattern matches against CPython's classes whatever the host, because a
    generated hierarchy subclasses them and every dispatch here is an
    `isinstance`. Construction is the one place that cannot: prescrypt-ng's
    `Assign` carries a mixin its later passes read, and `ast.Assign` does not.
    """
    return cls if grammar is None else grammar.constructor(cls.__name__)


def build(tpl: Any, binds: dict[str, Any], grammar: Grammar | None = None) -> Any:
    """Instantiate template `tpl` with `binds`, in `grammar`'s node classes."""
    match tpl:
        case ast.Name() if _is_meta(tpl.id):
            value = binds[tpl.id]
            # An identifier metavariable standing in expression position denotes a
            # variable reference. A sorted grammar would state this; untyped
            # patterns have to coerce.
            if isinstance(value, str):
                return _ctor(ast.Name, grammar)(id=value, ctx=_ctx(ast.Load, grammar)())
            return copy_tree(value)
        case Term():
            return _ctor(tpl.cls, grammar)(**{
                f: build(p, binds, grammar) for f, p in tpl.fields
            })
        case str():
            return binds[tpl] if _is_meta(tpl) else tpl
        case ast.AST():
            fields = {
                f: build(getattr(tpl, f, None), binds, grammar) for f in tpl._fields
            }
            return _ctor(type(tpl), grammar)(**fields)
        case list():
            out = []
            for item in tpl:
                name = _splice(item)
                if name is None:
                    out.append(build(item, binds, grammar))
                elif name == WILDCARD:
                    raise ValueError("cannot build from an anonymous `*_` or `**_`")
                else:
                    out.extend(copy_tree(v) for v in binds[name])
            return out
    return tpl


# ----------------------------------------------------------------------- rules


@dataclass(frozen=True)
class Match:
    """What a rule's right-hand side and guard get to see."""

    node: ast.AST
    binds: dict[str, Any]
    env: Any
    rewrite: Callable[..., Any]
    #: The pass's grammar, so a callable right-hand side builds the same node
    #: classes a template would. Without it the escape hatch would name a host
    #: directly, and a rewrite too irregular for a template is exactly the one
    #: that should still be shareable between compilers.
    grammar: Grammar | None = None

    def new(self, cls: type, **fields: Any) -> Any:
        """Build a node of the grammar's class for `cls`'s production."""
        return _ctor(cls, self.grammar)(**fields)


# A rule's right-hand side: a compiled template, DELETE, or a function of a Match.
Rhs = Any


def _name_of(obj: Any) -> str:
    if obj is DELETE:
        return "(delete)"
    return getattr(obj, "__name__", str(obj))


@dataclass(frozen=True, repr=False)
class Rule:
    lhs: Any
    rhs: Rhs
    when: Callable[[Match], bool] | None = None
    lhs_text: str = ""
    rhs_text: str = ""
    origin: str = ""

    def __str__(self) -> str:
        guard = "" if self.when is None else f"  if {_name_of(self.when)}"
        return f"{self.lhs_text} {ARROW} {self.rhs_text}{guard}"

    __repr__ = __str__


def _caller() -> str:
    """`file:line` of the code that called into this module.

    An origin is a diagnostic label, so an interpreter without frame support
    degrades it rather than failing.
    """
    here = inspect.currentframe()
    outer = here.f_back.f_back if here and here.f_back else None
    if outer is None:
        return "<unknown>"
    return f"{PurePath(outer.f_code.co_filename).name}:{outer.f_lineno}"


def rule(
    text: str,
    rhs: Rhs | None = None,
    when: Callable[[Match], bool] | None = None,
    origin: str = "",
) -> Rule:
    """Compile a rule.

    With one argument, `text` is `"pattern => replacement"`. With two, `text` is
    the pattern and `rhs` is `DELETE` or a function of a `Match`, the escape
    hatch for rewrites a template cannot express.

    `origin` names the rule in compile errors, and defaults to the call site.
    """
    origin = origin or _caller()
    try:
        return _compile_rule(text, rhs, when, origin)
    except ValueError as error:
        raise ValueError(f"{origin}: {error}") from error


def rewrite(
    pattern: str,
    when: Callable[[Match], bool] | None = None,
) -> Callable[[Callable[[Match], Any]], Rule]:
    """Declare a rule whose replacement is the function it decorates.

    A rewrite a template cannot express still wants its pattern next to the
    code that carries it out, rather than a name pointing somewhere else:

        @rewrite("ast.BoolOp(_o, _v)")
        def nest(m):
            "`a and b and c` becomes `a and (b and c)`."
            values = list(m.node.values)
            if len(values) <= 2:
                return None
            ...

    Returning None declines, and the next rule is tried, exactly as a guard
    that returns False. So a condition the function has to compute anyway is
    written once, inside it, and `when` is for a guard worth naming.
    """
    origin = _caller()

    def declare(fn: Callable[[Match], Any]) -> Rule:
        return rule(pattern, fn, when, origin=origin)

    return declare


def _compile_rule(
    text: str,
    rhs: Rhs | None,
    when: Callable[[Match], bool] | None,
    origin: str,
) -> Rule:
    lhs_src: str
    rhs_src: Any
    if rhs is None:
        lhs_src, rhs_src = _split_arrow(text)
    else:
        lhs_src, rhs_src = text.strip(), rhs

    left = _one(lhs_src)
    unwrap = isinstance(left, ast.Expr)
    if unwrap:
        left = left.value
    left = _compile(left)
    _check_splices(left)

    if rhs_src is DELETE or callable(rhs_src):
        return Rule(left, rhs_src, when, lhs_src, _name_of(rhs_src), origin)

    assert isinstance(rhs_src, str)  # narrowed: DELETE and callables handled above
    right: Any = _one(rhs_src)
    if unwrap:
        if not isinstance(right, ast.Expr):
            raise ValueError(f"expression rule needs an expression result: {rhs_src!r}")
        right = right.value
    elif isinstance(right, ast.Expr):
        raise ValueError(f"statement rule needs a statement result: {rhs_src!r}")
    return Rule(left, _compile(right), when, lhs_src, rhs_src, origin)


def rules(block: str, *also: Rule, origin: str = "") -> tuple[Rule, ...]:
    """Compile one `pattern => replacement` per non-blank, non-`#` line.

    `also` takes rules already compiled, which is how a `@rewrite` function
    joins the set without the whole thing splitting into two shapes spliced
    together. They are tried after the block, in the order given.

    Each rule's origin is the call site plus its line within the block, since
    the absolute line of a string literal is not recoverable from the caller.
    """
    origin = origin or _caller()
    return (
        *(
            rule(line.strip(), origin=f"{origin} block line {lineno}")
            for lineno, line in enumerate(block.splitlines(), 1)
            if line.strip() and not line.strip().startswith("#")
        ),
        *also,
    )


def _split_arrow(text: str) -> tuple[str, str]:
    """Split on the `=>` that leaves two parsable halves."""
    splits = []
    start = 0
    while True:
        cut = text.find(ARROW, start)
        if cut < 0:
            break
        splits.append((text[:cut].strip(), text[cut + len(ARROW) :].strip()))
        start = cut + len(ARROW)

    for lhs, rhs in splits:
        if lhs and rhs and _parses(lhs) and _parses(rhs):
            return lhs, rhs
    if not splits:
        raise ValueError(f"rule needs a {ARROW!r} separator: {text!r}")

    # An arrow is present but a half will not parse. Report that instead,
    # taking the earliest split whose left side parses as the intended one.
    for half in next((s for s in splits if _parses(s[0])), splits[0]):
        try:
            ast.parse(half)
        except SyntaxError as error:
            raise ValueError(f"cannot parse {half!r}: {error.msg}") from error
    raise ValueError(f"rule needs a {ARROW!r} separator: {text!r}")


def _parses(src: str) -> bool:
    try:
        ast.parse(src)
    except SyntaxError:
        return False
    return True


def _one(src: str) -> Any:
    body = ast.parse(src).body
    if len(body) != 1:
        raise ValueError(f"pattern must be a single statement or expression: {src!r}")
    return body[0]


def _check_splices(pat: Any) -> None:
    """One splice per list; two would make matching ambiguous."""
    match pat:
        case list():
            if sum(_splice(p) is not None for p in pat) > 1:
                raise ValueError("at most one `*` or `**` pattern per list")
            for item in pat:
                _check_splices(item)
        case Term():
            for _, sub in pat.fields:
                _check_splices(sub)
        case ast.AST():
            for f in pat._fields:
                _check_splices(getattr(pat, f, None))


# -------------------------------------------------------------------- traversal


class _Rewriter:
    def __init__(
        self,
        rule_set: tuple[Rule, ...],
        strategy: Strategy,
        grammar: Grammar | None = None,
        stop_at: tuple[type, ...] = (),
    ) -> None:
        self._rules = rule_set
        self._strategy = strategy
        self._grammar = grammar
        self._stop_at = stop_at

    def run(self, node: Any, env: Any = None, chain: int = 0) -> Any:
        if chain > _MAX_CHAIN:
            raise RecursionError("rewriting did not terminate; rule set is cyclic")

        if self._strategy is Strategy.INNERMOST:
            self._descend(node, env, chain)
            new = self._apply(node, env)
            if new is None:
                return node
            if new is DELETE:
                return DELETE
            # A rule may answer one node with several. Each is rewritten in
            # turn and the list is handed back for `_descend` to splice; there
            # is no node here to carry on rewriting.
            if isinstance(new, list):
                return [self.run(n, env, chain + 1) for n in new]
            return self.run(new, env, chain + 1)

        new = self._apply(node, env)
        if new is DELETE:
            return DELETE
        if isinstance(new, list):
            return new
        if new is not None:
            if self._strategy is Strategy.OUTERMOST:
                return new
            node = new
        self._descend(node, env, chain)
        return node

    def _descend(self, node: Any, env: Any, chain: int) -> None:
        for f in node._fields:
            value = getattr(node, f, None)
            match value:
                case list():
                    setattr(node, f, self._rewrite_slots(value, env, chain))
                case ast.AST():
                    setattr(node, f, self._rewrite_slot(value, f, env, chain))

    def _rewrite_slots(self, items: list, env: Any, chain: int) -> list:
        """A field holding several nodes, which is where a rule may add one.

        `val = yield from it` is a loop *and* an assignment, so a rule answers
        one statement with two. Only a list field can hold them, and appending
        the list itself would nest it and corrupt the tree.
        """
        out: list = []
        for item in items:
            if not isinstance(item, ast.AST) or isinstance(item, self._stop_at):
                out.append(item)
                continue
            new = self.run(item, env, chain)
            if new is DELETE:
                continue
            out.extend(new) if isinstance(new, list) else out.append(new)
        return out

    def _rewrite_slot(self, value: ast.AST, f: str, env: Any, chain: int) -> Any:
        """A field holding exactly one node."""
        if isinstance(value, self._stop_at):
            return value
        new = self.run(value, env, chain)
        if new is DELETE:
            raise ValueError(f"cannot delete {type(value).__name__} from field {f!r}")
        if isinstance(new, list):
            msg = (
                f"a rule answered {type(value).__name__} with {len(new)} nodes, "
                f"but field {f!r} holds one"
            )
            raise TypeError(msg)
        return new

    def _apply(self, node: Any, env: Any) -> Any:
        for r in self._rules:
            binds = match(r.lhs, node)
            if binds is None:
                continue
            m = Match(
                node=node,
                binds=binds,
                env=env,
                rewrite=self.run,
                grammar=self._grammar,
            )
            if r.when is not None and not r.when(m):
                continue
            if r.rhs is DELETE:
                return DELETE
            if not callable(r.rhs):
                return build(r.rhs, binds, self._grammar)
            out = r.rhs(m)
            # A callable right-hand side declines by returning None, and the
            # next rule is tried, exactly as for a guard that returns False.
            # Without this a rule whose condition is a count would need that
            # count written twice, once in a guard and once in the body.
            if out is not None:
                return out
        return None


# --------------------------------------------------------------------- contexts


def _ctx(cls: type, grammar: Grammar | None) -> type:
    """The host's class for a *context*, declared or not.

    Deliberately unlike `_ctor`, which raises for a production the grammar does
    not declare, because silently building CPython's class there would defer
    the failure downstream: a rule asking for an `AnnAssign` the host lacks
    must fail at the rule. A context is not something a rule asks for. It is
    machinery astero applies on the way out, and a grammar declaring a
    *subset* of a language will not have named `Store`, `Load` or `Del` —
    which is what `Grammar.subset` failed on before this existed.
    """
    if grammar is None or cls.__name__ not in grammar:
        return cls
    return grammar.constructor(cls.__name__)


def target_fields(grammar: Grammar) -> dict[str, tuple[tuple[str, ...], type]]:
    """Production name -> (fields holding a target, the context it implies).

    Derived, never authored. This used to be a literal table, and it silently
    fell behind Python 3.12: `TypeAlias.name` is a binding position, so
    `type X = int` was given a Load context where CPython says Store.
    """
    store_cls = _ctx(ast.Store, grammar)
    del_cls = _ctx(ast.Del, grammar)
    store = grammar.positions((Kind.DEF, Kind.DEFUSE), VARS)
    delete = grammar.positions(Kind.DEL, VARS)
    out: dict[str, tuple[tuple[str, ...], type]] = {
        name: (fields, store_cls) for name, fields in store.items()
    }
    for name, fields in delete.items():
        out[name] = (fields, del_cls)
    return out


#: The default derivation, computed once. Grammars are immutable.
_PY_TARGETS = target_fields(PY)


def fix_contexts(tree: ast.AST, grammar: Grammar | None = None) -> ast.AST:
    """Recompute every `ctx` from the shape of the tree.

    Which positions are targets comes from the declared grammar, so the
    engine and the grammar cannot disagree about it.
    """
    targets = _PY_TARGETS if grammar is None else target_fields(grammar)
    load = _ctx(ast.Load, grammar)
    for node in ast.walk(tree):
        if isinstance(node, CTX_NODES):
            node.ctx = load()
    for node in ast.walk(tree):
        spec = targets.get(type(node).__name__)
        if spec is None:
            continue
        fields, ctx = spec
        for name in fields:
            value = getattr(node, name, None)
            for target in value if isinstance(value, list) else [value]:
                if target is not None:
                    _set_ctx(target, ctx)
    return tree


def _set_ctx(node: ast.AST, ctx: type) -> None:
    match node:
        case ast.Tuple() | ast.List():
            node.ctx = ctx()
            for elt in node.elts:
                _set_ctx(elt, ctx)
        case ast.Starred():
            node.ctx = ctx()
            _set_ctx(node.value, ctx)
        case _ if isinstance(node, CTX_NODES):
            # A guard, not `case CTX_NODES()`: a class pattern needs a class,
            # and this is the tuple gated against the grammar above. Spelling
            # its members out here would be the second copy that gate exists
            # to prevent. `case CTX_NODES()` compiles and raises
            # `TypeError: called match pattern must be a class` when reached.
            node.ctx = ctx()


# ------------------------------------------------------------------------ pass


@dataclass(frozen=True, repr=False)
class Pass:
    """A named rule set, a traversal strategy, and a postcondition."""

    name: str
    rules: tuple[Rule, ...]
    strategy: Strategy = Strategy.INNERMOST
    eliminates: tuple[type, ...] = field(default_factory=tuple)
    #: The grammar whose roles decide the derived fields.
    grammar: Grammar | None = None
    #: Productions the traversal skips. A rewrite is sometimes local to one
    #: scope: `yield from` inside a nested function belongs to *that*
    #: generator, so a pass lowering it must not reach in.
    #:
    #: The node is skipped whole: neither entered nor offered to the rules.
    #: The one exception is the tree the pass is called on, which is offered
    #: before the traversal begins. `test_stop_at_skips_the_boundary_node`
    #: pins both halves.
    stop_at: tuple[type, ...] = field(default_factory=tuple)

    # Returns Any, not ast.AST: a rule may replace the root with a node of a
    # different type (an AugAssign statement becomes an Assign).
    def __call__(self, tree: ast.AST, env: Any = None) -> Any:
        out = _Rewriter(self.rules, self.strategy, self.grammar, self.stop_at).run(
            copy_tree(tree), env
        )
        if out is DELETE:
            raise ValueError(f"pass {self.name!r} deleted its own root")
        fix_contexts(out, self.grammar)
        ast.fix_missing_locations(out)
        left = [n for n in ast.walk(out) if isinstance(n, self.eliminates)]
        if left:
            raise AssertionError(
                f"pass {self.name!r} left {len(left)} "
                f"{type(left[0]).__name__} node(s) in its output"
            )
        return out

    def visit(self, tree: ast.AST) -> Any:
        """Accepted so a Pass can stand in for an ast.NodeTransformer."""
        return self(tree)

    def __repr__(self) -> str:
        return f"<Pass {self.name}: {len(self.rules)} rules, {self.strategy.value}>"

    def __str__(self) -> str:
        plural = "" if len(self.rules) == 1 else "s"
        header = (
            f"pass {self.name}  [{self.strategy.value}, {len(self.rules)} rule{plural}]"
        )
        lines = [header]
        if self.eliminates:
            names = ", ".join(c.__name__ for c in self.eliminates)
            lines.append(f"  eliminates {names}")
        if self.stop_at:
            names = ", ".join(c.__name__ for c in self.stop_at)
            lines.append(f"  does not enter {names}")
        if not self.rules:
            lines.append("  (no rules)")
        width = max((len(r.lhs_text) for r in self.rules), default=0)
        for i, r in enumerate(self.rules, 1):
            guard = "" if r.when is None else f"  if {_name_of(r.when)}"
            lines.append(f"  {i:>2}. {r.lhs_text:<{width}} {ARROW} {r.rhs_text}{guard}")
        return "\n".join(lines)
