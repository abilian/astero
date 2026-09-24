"""Scopes, derived from a declared grammar.

The grammar already says which fields *bind* a name. This adds the second half:
which productions open a scope, and which of their fields are evaluated inside
it. Between them, the scope tree and the names bound in each block follow, with
nothing about lexical structure written out per production.

The declaration is small. What it buys is that Python's awkward cases become
statements rather than code: a function's `name` binds outside while its `args`
bind inside, a class body is a scope that nested functions cannot see, and a
comprehension is a scope on some versions and inlined on others.

CPython ships the oracle for this in `symtable`, which is what
`tests/b_integration/test_scopes_symtable.py` checks against.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from astero.grammar import Condition, Field, Grammar, Kind


@dataclass(frozen=True)
class Scope:
    """A scope a production opens.

    A production may open several, nested. `def f[T]()` opens a type-parameter
    scope wrapping the function scope, and only when it has type parameters,
    so a layer carries a condition and the layers are listed outermost first.
    """

    #: What kind of block this is, in `symtable`'s vocabulary.
    kind: str
    #: Fields evaluated inside the new scope. Every other field of the
    #: production is evaluated in the enclosing one, which is how a function's
    #: name binds outside while its parameters bind inside.
    inside: tuple[str, ...]
    #: Field holding the block's name, or None to use `fixed_name`.
    name_field: str | None = None
    fixed_name: str = ""
    #: When set, this layer exists only where the condition holds.
    when: Condition | None = None
    #: For a sibling block, at most one per enclosing block however many
    #: nodes ask for it. PEP 649 gives a block a single `__annotate__` for
    #: all of its annotated assignments.
    once: bool = False

    def applies(self, node: ast.AST) -> bool:
        return self.when is None or self.when.holds(node)


@dataclass
class Block:
    """A resolved scope: what it is, what it binds, what it contains."""

    kind: str
    name: str
    node: ast.AST
    bound: set[str] = field(default_factory=set)
    #: Names declared to live in another scope: `global` and `nonlocal`.
    declared_elsewhere: set[str] = field(default_factory=set)
    children: list[Block] = field(default_factory=list)

    def walk(self) -> Iterator[Block]:
        yield self
        for child in self.children:
            yield from child.walk()

    def owns(self) -> set[str]:
        """Names this block actually binds, less those declared elsewhere."""
        return self.bound - self.declared_elsewhere

    def shape(self) -> tuple:
        """A comparable summary: kind, name, and the shape of each child."""
        return (self.kind, self.name, tuple(c.shape() for c in self.children))

    def __str__(self) -> str:
        return _render(self, 0)


def _render(block: Block, depth: int) -> str:
    """A block and its children, indented. A function rather than a method, so
    recursing into a sibling is not a reach into a private member."""
    pad = "  " * depth
    names = ", ".join(sorted(block.owns()))
    lines = [f"{pad}{block.kind:9} {block.name:16} {{{names}}}"]
    lines += [_render(child, depth + 1) for child in block.children]
    return "\n".join(lines)


#: Sorts whose bound name is not the whole string. `import a.b` binds `a`.
DOTTED = "dotted_ident"


def names_bound_by(node: Any, grammar: Grammar, ns: str) -> set[str]:
    """Every identifier `node` itself introduces in `ns`, conditions applied.

    `bound_names` answers for one *field*, so a caller had to find the
    production, fetch the `Field` and pass its sort — a five-line dance that
    every consumer wrote. This is the identifier twin of `Grammar.binds`,
    which answers the same question for slot contents.

    The node only, not its children, which is the same rule `Grammar.binds`
    follows. So a `FunctionDef` answers with its own name and not its
    parameters, and a `With` answers with nothing: the binding lives on the
    `withitem`, as `import a.b as c`'s lives on the `alias` and `except E as
    err`'s on the `ExceptHandler`. A pass that wants everything a statement
    binds walks, and asks this of each node it reaches.
    """
    prod = grammar.productions.get(type(node).__name__)
    if prod is None:
        return set()
    out: set[str] = set()
    for slot in prod.fields:
        if not slot.role.binds or slot.role.ns != ns or not slot.applies(node):
            continue
        out |= set(bound_names(getattr(node, slot.name, None), slot.sort))
    return out


def target_nodes(value: object) -> Iterator[ast.Name]:
    """Every `Name` a Python binding position actually binds.

    Python's, not every language's: a target may nest (`(a, b), *c = ...`) and
    these four shapes are how it nests. It lives here rather than in
    `astero.python` because `astero.scopes` may not import that package — the
    Python grammar imports `Scope` from here, and the cycle only fires when a
    consumer imports `astero.scopes` first, which is what `examples/pl0` does.

    `bound_names` yields the identifiers and `hygiene` the nodes; before this
    they were the same walk written twice, the second copy captioned
    "mirroring `bound_names`".
    """
    match value:
        case list():
            for item in value:
                yield from target_nodes(item)
        case ast.Name():
            yield value
        case ast.Tuple() | ast.List():
            for elt in value.elts:
                yield from target_nodes(elt)
        case ast.Starred():
            yield from target_nodes(value.value)


def bound_names(value: object, sort: str | None = None) -> Iterator[str]:
    """The identifiers a binding position introduces.

    A binding field holds either a name outright (`arg.arg`) or an expression
    that is a target (`Assign.targets`), and a target may nest.
    """
    match value:
        case str():
            if sort != DOTTED:
                yield value
            elif value != "*":
                # `from m import *` names no binding a static pass can see.
                yield value.split(".")[0]
        case list():
            for item in value:
                yield from bound_names(item, sort)
        case _:
            # A Python target, which may nest: `(a, b), *c = ...`. The shapes
            # are Python's, so the walk over them is, and it is shared with
            # `hygiene` rather than spelled a second time there.
            for node in target_nodes(value):
                yield node.id


def _opened_fields(node: Any, scopes: Mapping[str, tuple[Scope, ...]]) -> set[str]:
    """Fields of `node` that are evaluated inside a scope `node` opens.

    Conditions apply: `def f[T]()` opens a type-parameter scope and
    `def f()` does not, so which fields are inner depends on the node.
    """
    layers = scopes.get(type(node).__name__, ())
    return {name for layer in layers if layer.applies(node) for name in layer.inside}


def binds_in_scope(
    node: Any,
    grammar: Grammar,
    ns: str,
    scopes: Mapping[str, tuple[Scope, ...]],
    *,
    stop: Collection[str] = (),
) -> set[str]:
    """Every name `node` introduces into the scope that *contains* it.

    `names_bound_by` answers for one node, and a pass that wants everything
    a statement binds has to walk. The walk is the part that goes wrong,
    because it has to stop at a scope boundary: a function's parameters and
    body bind inside the function, so `def f(a, b): ...` contributes `f` to
    the scope around it and nothing else. `scopes` is the layer table that
    says which fields those are, `astero.python.BINDING_SCOPES` for Python.

    Use `BINDING_SCOPES` rather than `SCOPES` here. They differ from 3.12,
    where PEP 709 stopped comprehensions opening a `symtable` block while
    leaving their targets local, and this is the binding question.

    `stop` names productions the walk will not enter, as a set of
    production names. A flow analysis visiting one statement at a time
    passes `grammar.concrete("stmt")`, so an `if` reports what its test
    binds without reporting what its branches bind::

        binds_in_scope(stmt, PY, VARS, BINDING_SCOPES, stop=PY.concrete("stmt"))

    `node` itself is entered whatever `stop` says, since it is the thing
    being asked about.

    Reaches through anything that is not a node of its own: `with a as b`
    binds `b` through a `withitem`, `import a.b as c` through an `alias`,
    `except E as err` through an `ExceptHandler`, and `case [x]` through a
    pattern. None of those are named here.
    """
    out = set(names_bound_by(node, grammar, ns))
    inner = _opened_fields(node, scopes)
    for name, value in _fields_of(node, grammar):
        if name in inner:
            continue
        for child in value if isinstance(value, list) else [value]:
            if _is_node(child, grammar) and type(child).__name__ not in stop:
                out |= binds_in_scope(child, grammar, ns, scopes, stop=stop)
    return out


def _is_node(value: Any, grammar: Grammar) -> bool:
    """Whether the grammar declares this value as a production.

    Not `isinstance(value, ast.AST)`. A grammar read off dataclasses has
    nodes that are not Python AST nodes, and this module is supposed to work
    over any declared grammar; testing against `ast.AST` quietly made it
    Python-only, which a PL/0 example found by getting an empty scope tree.
    """
    return type(value).__name__ in grammar.productions


def walk(node: Any, grammar: Grammar) -> Iterator[Any]:
    """Every declared node under `node`, itself included, in no fixed order.

    `ast.walk` reads `node._fields`, so it answers nothing for a tree the
    grammar declares off dataclasses — not an error, an empty iterator, which
    is how `hygiene.taken_names` came to report that no name was taken in a
    PL/0 program. `_fields_of` and `_is_node` are what make this the same walk
    for every grammar; see their notes for the same mistake made twice before.

    A list is walked as a root, so a body can be passed directly.
    """
    todo = list(node) if isinstance(node, list) else [node]
    while todo:
        current = todo.pop()
        if not _is_node(current, grammar):
            continue
        yield current
        for _name, value in _fields_of(current, grammar):
            todo.extend(value if isinstance(value, list) else [value])


def _fields_of(node: Any, grammar: Grammar) -> list[tuple[str, Any]]:
    """(name, value) per declared field, in declaration order.

    Replaces `ast.iter_fields`, which reads `node._fields` and so needs a
    Python AST. The declared order matches `iter_fields` for every node of
    the standard library; the grammar simply omits `ctx`, which is derived,
    and `type_comment`, which binds nothing.

    A field carrying two conditional roles is listed twice in the production
    and yielded once here.
    """
    prod = grammar.productions.get(type(node).__name__)
    if prod is None:
        return list(ast.iter_fields(node)) if isinstance(node, ast.AST) else []
    out: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for slot in prod.fields:
        if slot.name in seen:
            continue
        seen.add(slot.name)
        out.append((slot.name, getattr(node, slot.name, None)))
    return out


def _block_name(node: ast.AST, scope: Scope) -> str:
    """A block's name, from a field or a fixed string.

    `TypeAlias.name` holds a `Name` node rather than a bare string, so the
    field is unwrapped rather than stringified.
    """
    if not scope.name_field:
        return scope.fixed_name
    value = getattr(node, scope.name_field, None)
    if isinstance(value, ast.Name):
        return value.id
    return str(value) if value is not None else scope.fixed_name


#: A per-production rule for a binder a per-field role cannot express, because
#: which field binds depends on a sibling. Python's `import a.b as c` is the
#: only case in the corpus.
ExtraBinder = Callable[[ast.AST], str | None]

#: A block that is a *sibling* of a node's own rather than a layer around it,
#: keyed by production. A `Scope` in `scopes` wraps what the production
#: contains; one of these is a separate, empty block appended to the enclosing
#: block just before it.
#:
#: PEP 649 is the only case in the corpus, and it is why this cannot be a
#: `Scope` layer or a `Condition`: from Python 3.14 a `def`'s annotations
#: compile to an `__annotate__` function living in the *enclosing* scope, and
#: a block's annotated assignments compile to one more, shared between them.
#: Whether that block exists is a fact about a block's contents, which
#: `Present`/`Absent` cannot state.
SiblingBlocks = Mapping[str, Scope]

#: A name transform applied to identifiers written inside a class body.
#: Python mangles `__x` to `_ClassName__x`, so a renaming pass that does
#: not model it renames a name the interpreter never sees.
Mangler = Callable[[str, str], str]


def scope_tree(
    tree: Any,
    grammar: Grammar,
    scopes: Mapping[str, tuple[Scope, ...]],
    namespace: str,
    *,
    extra: Mapping[str, ExtraBinder] | None = None,
    mangle: Mangler | None = None,
    siblings: SiblingBlocks | None = None,
    root_kind: str = "module",
    root_name: str = "top",
) -> Block:
    """Resolve `tree` into a block tree with the names each block binds.

    `tree` is any node the grammar declares, not only an `ast.AST`: the walk
    reads its fields from `grammar`, which is what lets a tree of plain
    dataclasses resolve. The annotation said `ast.AST` for as long as the
    implementation was Python-only, and outlived it.
    """
    resolver = _Resolver(
        binding=grammar.positions((Kind.DEF, Kind.DEFUSE), namespace),
        declaring=grammar.positions(Kind.DECLARE, namespace),
        scopes=scopes,
        extra=dict(extra or {}),
        grammar=grammar,
        mangle=mangle,
        siblings=dict(siblings or {}),
    )
    root = Block(kind=root_kind, name=root_name, node=tree)
    resolver.descend(tree, root, None)
    return root


@dataclass(frozen=True)
class _Resolver:
    binding: Mapping[str, tuple[str, ...]]
    declaring: Mapping[str, tuple[str, ...]]
    scopes: Mapping[str, tuple[Scope, ...]]
    extra: Mapping[str, ExtraBinder]
    grammar: Grammar | None = None
    mangle: Mangler | None = None
    siblings: Mapping[str, Scope] = field(default_factory=dict)
    #: Enclosing blocks that already have a `once` sibling, by kind and name.
    _placed: set[tuple[int, str, str]] = field(default_factory=set)

    def descend(self, node: ast.AST, block: Block, owner: str | None) -> None:
        for fname, value in self.fields_of(node):
            for child in value if isinstance(value, list) else [value]:
                if self.is_node(child):
                    self.visit(child, fname, node, block, owner)

    def visit(
        self,
        child: ast.AST,
        fname: str,
        parent: ast.AST,
        block: Block,
        owner: str | None,
    ) -> None:
        # A binding position on the parent binds whatever this child names.
        field = self._binding_field(parent, fname)
        if field is not None:
            self._bind(block, bound_names(child, field.sort), owner)

        self.own_names(child, block, owner)

        layers = [
            layer
            for layer in self.scopes.get(type(child).__name__, ())
            if layer.applies(child)
        ]
        if not layers:
            self.place_sibling(child, block)
            self.descend(child, block, owner)
            return

        # Layers nest outermost first, so a type-parameter scope encloses the
        # function scope its production also opens.
        blocks = _open_layers(child, layers, owner)
        # A sibling belongs beside the production's *innermost* layer, which
        # is the scope its contents are compiled in. The annotations of
        # `def f[T](x: T)` may name `T`, so CPython puts `__annotate__`
        # inside the type-parameter block rather than beside it.
        if len(blocks) > 1:
            self.place_sibling(child, blocks[-2][1], before=blocks[-1][1])
        else:
            self.place_sibling(child, block)
        # Fields evaluated in the enclosing scope come first, because CPython
        # compiles a decorator or a default argument before the block the
        # production opens. Appending the block first put a lambda in a default
        # after its own function among the parent's children.
        for inner_pass in (False, True):
            for sub_name, sub_value in self.fields_of(child):
                target, target_owner = _route(sub_name, blocks, block, owner)
                if (target is not block) != inner_pass:
                    continue
                for sub in sub_value if isinstance(sub_value, list) else [sub_value]:
                    if self.is_node(sub):
                        self.visit(sub, sub_name, child, target, target_owner)
            if not inner_pass:
                block.children.append(blocks[0][1])

    def place_sibling(
        self, child: ast.AST, block: Block, before: Block | None = None
    ) -> None:
        """A sibling block this node contributes to the scope around it.

        It goes before the node's own block, because that is the order
        CPython compiles them in: `def f` emits its `__annotate__` and then
        the function itself.
        """
        layer = self.siblings.get(type(child).__name__)
        if layer is None or not layer.applies(child):
            return
        name = _block_name(child, layer)
        if layer.once:
            mark = (id(block), layer.kind, name)
            if mark in self._placed:
                return
            self._placed.add(mark)
        made = Block(kind=layer.kind, name=name, node=child)
        if before is None:
            block.children.append(made)
        else:
            block.children.insert(block.children.index(before), made)

    def fields_of(self, node: Any) -> list[tuple[str, Any]]:
        if self.grammar is None:
            return list(ast.iter_fields(node))
        return _fields_of(node, self.grammar)

    def is_node(self, value: Any) -> bool:
        if self.grammar is None:
            return isinstance(value, ast.AST)
        return _is_node(value, self.grammar)

    def own_names(self, node: ast.AST, block: Block, owner: str | None) -> None:
        """Bindings and declarations a node makes about itself."""
        name = type(node).__name__
        for fname in self.binding.get(name, ()):
            field = self._binding_field(node, fname)
            value = getattr(node, fname, None)
            if field is not None and _is_plain(value):
                self._bind(block, bound_names(value, field.sort), owner)
        for fname in self.declaring.get(name, ()):
            value = getattr(node, fname, None)
            if _is_plain(value):
                block.declared_elsewhere.update(
                    self._mangled(bound_names(value), owner)
                )
        binder = self.extra.get(name)
        if binder is not None:
            bound = binder(node)
            if bound:
                self._bind(block, [bound], owner)

    def _binding_field(self, node: ast.AST, fname: str) -> Field | None:
        """The declared field, when its role is in force for this node."""
        prod = self.grammar[type(node).__name__] if self.grammar else None
        if prod is None:
            return None
        field = prod.field(fname)
        if field is None or fname not in self.binding.get(type(node).__name__, ()):
            return None
        return field if field.applies(node) else None

    def _bind(self, block: Block, names: Iterable[str], owner: str | None) -> None:
        block.bound.update(self._mangled(names, owner))

    def _mangled(self, names: Iterable[str], owner: str | None) -> list[str]:
        if self.mangle is None or owner is None:
            return list(names)
        return [self.mangle(n, owner) for n in names]


def _open_layers(
    node: ast.AST, layers: list[Scope], owner: str | None
) -> list[tuple[Scope, Block, str | None]]:
    """Create the nested blocks a production opens, outermost first."""
    out: list[tuple[Scope, Block, str | None]] = []
    current: Block | None = None
    current_owner = owner
    for layer in layers:
        name = _block_name(node, layer)
        opened = Block(kind=layer.kind, name=name, node=node)
        if current is not None:
            current.children.append(opened)
        current = opened
        current_owner = name if layer.kind == "class" else current_owner
        out.append((layer, opened, current_owner))
    return out


def _route(
    fname: str,
    blocks: list[tuple[Scope, Block, str | None]],
    outside: Block,
    owner: str | None,
) -> tuple[Block, str | None]:
    """The innermost layer claiming this field, or the enclosing scope."""
    target, target_owner = outside, owner
    for layer, opened, opened_owner in blocks:
        if fname in layer.inside:
            target, target_owner = opened, opened_owner
    return target, target_owner


def _is_plain(value: object) -> bool:
    """A field holding bare identifiers rather than child nodes."""
    return isinstance(value, str) or (
        isinstance(value, list) and all(isinstance(v, str) for v in value)
    )
