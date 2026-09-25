"""Fresh names, renaming, and capture-avoiding substitution.

A pass that moves code from one place to another has to answer three questions
about names, and every one of them is a question the grammar already answers.

*Which occurrences of a name may be replaced?* Only the ones that **use** it.
p2w's inliner substituted at every `Name` node, so inlining `f(99)` into a body
containing `[x for x in ...]` produced `[99 for 99 in ...]`, which is not a
program. Whether a position uses or binds is what roles say.

*Which slots does renaming have to reach?* Every slot holding an identifier,
not the ones a pass happens to remember. latexify's renamer listed them by hand
and missed `vararg`, `kwarg`, lambda parameters and `async def` parameters, so
it renamed references to parameters it left alone.

*When is a substitution unsafe?* When the expression being moved has a free
name that the destination binds, so moving it would capture that name. That is
computable from the same two answers.

Nothing here decides policy. A caller that cannot supply fresh names gets a
refusal naming the obstruction, which is what p2w's inliner does today by
declining to inline at all.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from astero.grammar import Grammar, Kind, Production
from astero.python.rewriting import copy_tree
from astero.scopes import (
    DOTTED,
    Scope,
    binds_in_scope,
    bound_names,
    evaluated_outside,
    layer_binds,
    target_nodes,
    walk,
)


class CaptureError(Exception):
    """A substitution could not be made without capturing a name."""


@dataclass
class Fresh:
    """A supply of names that avoids a set of names already in use.

    Every name handed out is added to `taken`, so two calls never collide even
    when the caller does not record the first one.
    """

    prefix: str = "_t"
    taken: set[str] = field(default_factory=set)
    _next: int = 0

    def __call__(self) -> str:
        while True:
            self._next += 1
            candidate = f"{self.prefix}{self._next}"
            if candidate not in self.taken:
                self.taken.add(candidate)
                return candidate

    @classmethod
    def avoiding(cls, node: Any, grammar: Grammar, prefix: str = "_t") -> Fresh:
        """A supply avoiding every name that appears anywhere in `node`."""
        return cls(prefix=prefix, taken=set(all_names(node, grammar)))


# ------------------------------------------------------------------ positions


# `ident_slots` and `reference_slots` each scan the whole grammar, so every
# walk below reads them once and indexes the result per node. Calling them
# inside the walk made `all_names` quadratic in the size of the declaration:
# 0.40s over a 4800-node module against 0.016s hoisted, same answer. The
# lookups they replace are exact — a field name from either table is a field
# of that production, so `prod[fname]` is right and `prod.field(fname)` with
# a `None` check re-asks a question the table already answered.


def _referenced_objects(value: object) -> Iterator[Any]:
    """The reference objects a field holds, through a list or alone."""
    for item in value if isinstance(value, list) else [value]:
        if item is not None:
            yield item


def _referenced_names(value: object, slot: str) -> Iterator[str]:
    """The identifiers a reference field holds, through a list or alone.

    The grammar names `slot`; it does not promise the host put a string
    there, and this is the boundary where a foreign object is read.
    """
    for item in _referenced_objects(value):
        name = getattr(item, slot, None)
        if isinstance(name, str):
            yield name


def _binding_fields(grammar: Grammar, ns: str) -> Mapping[str, tuple[str, ...]]:
    """Fields that introduce or remove a name, by production."""
    out: dict[str, tuple[str, ...]] = {}
    for kinds in ((Kind.DEF, Kind.DEFUSE), (Kind.DEL,)):
        for name, fields in grammar.positions(kinds, ns).items():
            out[name] = out.get(name, ()) + fields
    return out


def binding_occurrences(node: Any, grammar: Grammar, ns: str) -> set[int]:
    """`id()` of every node that *binds* rather than uses a name.

    A binding field may hold a target that is not itself a binding: `b[i] = v`
    binds nothing, and reads both `b` and `i`. `bound_names` already draws that
    line, so this walks the same shapes it does.
    """
    binding = _binding_fields(grammar, ns)
    idents = grammar.ident_slots()
    out: set[int] = set()
    for parent in walk(node, grammar):
        prod = grammar.productions.get(type(parent).__name__)
        if prod is None:
            continue
        for fname in binding.get(prod.name, ()):
            if not prod[fname].applies(parent):
                continue
            out |= {id(n) for n in target_nodes(getattr(parent, fname, None))}
        # An identifier field that binds is a binding occurrence of the node
        # holding it, which is how `arg.arg` and `FunctionDef.name` are marked.
        for fname in idents.get(prod.name, ()):
            if prod[fname].role.binds:
                out.add(id(parent))
    return out


# ---------------------------------------------------------------------- names


def _walk_py(node: Any) -> Iterator[ast.AST]:
    """`ast.walk` over a node or a list, for the Python-only substitution."""
    roots = node if isinstance(node, list) else [node]
    for root in roots:
        if isinstance(root, ast.AST):
            yield from ast.walk(root)


def all_names(node: Any, grammar: Grammar) -> set[str]:
    """Every identifier appearing anywhere in `node`, bound or used.

    No namespace argument: an identifier slot is a slot whatever namespace its
    role names, and renaming has to reach all of them.
    """
    idents = grammar.ident_slots()
    references = grammar.reference_slots()
    out: set[str] = set()
    for sub in walk(node, grammar):
        prod = grammar.productions.get(type(sub).__name__)
        if prod is None:
            continue
        for fname in idents.get(prod.name, ()):
            value = getattr(sub, fname, None)
            if isinstance(value, (str, list)):
                out |= set(bound_names(value, prod[fname].sort))
        for fname, slot in references.get(prod.name, ()):
            out |= set(_referenced_names(getattr(sub, fname, None), slot))
    return out


def bound_here(node: Any, grammar: Grammar, ns: str) -> set[str]:
    """Names `node` introduces anywhere inside itself.

    Accepts a node or a list of them, so a caller holding one field's value
    does not have to wrap it.
    """
    binding = _binding_fields(grammar, ns)
    idents = grammar.ident_slots()
    out: set[str] = set()
    for sub in walk(node, grammar):
        prod = grammar.productions.get(type(sub).__name__)
        if prod is None:
            continue
        for fname in binding.get(prod.name, ()):
            declared = prod[fname]
            if declared.applies(sub):
                out |= set(bound_names(getattr(sub, fname, None), declared.sort))
        for fname in idents.get(prod.name, ()):
            declared = prod[fname]
            if declared.role.binds:
                out |= set(bound_names(getattr(sub, fname, None), declared.sort))
    return out


def free_names(
    node: Any,
    grammar: Grammar,
    ns: str,
    *,
    scopes: Mapping[str, tuple[Scope, ...]] | None = None,
) -> set[str]:
    """Names `node` uses without introducing.

    Without `scopes`, `node` counts as one scope, so a name bound anywhere in
    it is bound everywhere. That can miss a free name, which is the unsafe
    direction for a capture check: the first `t` of `t + sum(t for t in xs)`
    is free, and moving the expression under a binder of `t` captures it.

    With `scopes` the answer is exact: a name is free where a `Name` uses it
    outside every region of `node` that binds it. That needs Python's `Name`,
    as substitution does.
    """
    if scopes is None:
        return all_names(node, grammar) - bound_here(node, grammar, ns)
    shadows = shadowed_at(node, grammar, ns, scopes)
    top = {
        name
        for child in _as_node_list(node)
        for name in binds_in_scope(child, grammar, ns, scopes)
    }
    binders = binding_occurrences(node, grammar, ns)
    return {
        sub.id
        for sub in _walk_py(node)
        if isinstance(sub, ast.Name)
        and id(sub) not in binders
        and sub.id not in top
        and sub.id not in shadows.get(id(sub), frozenset())
    }


# ------------------------------------------------------------------- renaming


def rename(node: Any, mapping: Mapping[str, str], grammar: Grammar, ns: str) -> Any:
    """Rename identifiers of namespace `ns`, in every slot the grammar declares.

    Both binding and using occurrences, because a rename that reaches only one
    of them changes what the program means.

    The namespace matters. `Attribute.attr` and `keyword.arg` are identifier
    slots too, in a different namespace, and renaming a variable `foo` must not
    rewrite `x.foo` into a different attribute.

    A dotted identifier is skipped. `import a.b as c` holds a module path in
    `alias.name`, and while that is an identifier position the renaming surface
    has to know about, it names a module rather than a local. Renaming a
    variable `a` must not rewrite the import it happens to share a spelling
    with. Renaming the binding of a bare `import a` is a different operation,
    since it has to become `import a as ...` to keep meaning the same thing.
    """
    if not mapping:
        return node
    idents = grammar.ident_slots(ns)
    references = grammar.reference_slots(ns)
    for sub in walk(node, grammar):
        prod = grammar.productions.get(type(sub).__name__)
        if prod is None:
            continue
        _rename_idents(sub, prod, idents.get(prod.name, ()), mapping)
        _rename_references(sub, references.get(prod.name, ()), mapping)
    return node


def _rename_idents(
    sub: Any, prod: Production, fields: tuple[str, ...], mapping: Mapping[str, str]
) -> None:
    """Slots holding the identifier itself, as a string or a list of them."""
    for fname in fields:
        if prod[fname].sort == DOTTED:
            continue
        match getattr(sub, fname, None):
            case str() as value if value in mapping:
                setattr(sub, fname, mapping[value])
            case list() as items if all(isinstance(x, str) for x in items):
                setattr(sub, fname, [mapping.get(x, x) for x in items])


def _rename_references(
    sub: Any, slots: tuple[tuple[str, str], ...], mapping: Mapping[str, str]
) -> None:
    """Slots holding an object whose named field is the identifier.

    The object is what gets rewritten, since the name is one level down.
    Written in place like the rest of `rename`: a reference shared by two
    instructions is one binding, and renaming it once renames it everywhere,
    which is what a rename means.
    """
    for fname, slot in slots:
        for item in _referenced_objects(getattr(sub, fname, None)):
            current = getattr(item, slot, None)
            if isinstance(current, str) and current in mapping:
                setattr(item, slot, mapping[current])


# -------------------------------------------------------------------- scopes


def _scope_layers(
    node: Any, scopes: Mapping[str, tuple[Scope, ...]]
) -> tuple[Scope, ...]:
    """The scope layers `node` opens, those whose condition holds."""
    return tuple(
        layer for layer in scopes.get(type(node).__name__, ()) if layer.applies(node)
    )


def shadowed_at(
    node: Any,
    grammar: Grammar,
    ns: str,
    scopes: Mapping[str, tuple[Scope, ...]],
) -> dict[int, frozenset[str]]:
    """`id()` of every node, mapped to the names shadowed around it.

    A name bound by an inner scope hides the outer one inside that scope's own
    fields and nowhere else, which is why this cannot be a flat set. A
    function's parameters shadow inside its body, and its decorators are
    evaluated outside where they do not.

    What a scope binds stops at the scopes nested in it. The `v` of
    `lambda: [v for v in xs] + [v]` belongs to the comprehension, and counting
    it as the lambda's hid the lambda's own free `v` from substitution.

    A declared name is not the declaring scope's: `global g` and `nonlocal x`
    bind nothing where they are written, and a `global` name is not any
    enclosing function's either. A class body's names are visible in the body
    and in the annotation scopes inside it, and not in a function or generator
    nested in it: `class C: x = 1; def m(self): return x` reads the global `x`.
    `symtable` is the oracle for all of it, in `test_scopes_symtable.py`.
    """
    out: dict[int, frozenset[str]] = {}
    declaring = grammar.positions(Kind.DECLARE, ns)
    #: What a layer evaluates outside itself sees the names around the layer.
    around: dict[int, tuple[frozenset[str], frozenset[str]]] = {}

    def walk(current: Any, outer: frozenset[str], klass: frozenset[str]) -> None:
        if isinstance(current, list):
            for item in current:
                walk(item, outer, klass)
            return
        if not isinstance(current, ast.AST):
            return
        outer, klass = around.pop(id(current), (outer, klass))
        out[id(current)] = outer | klass
        inner: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
        o, k = outer, klass
        for layer, bound in layer_binds(current, grammar, ns, scopes):
            for _, _, child in evaluated_outside(current, layer, scopes):
                around[id(child)] = (o, k)
            region = [
                child
                for f in layer.inside
                for child in _as_node_list(getattr(current, f, None))
            ]
            declared, global_ = _declared_in(region, declaring, scopes)
            binds = frozenset(bound) - declared
            o -= global_
            if layer.kind == "class":
                k = binds
            elif layer.kind == "function":
                o, k = o | binds, frozenset()
            else:  # an annotation scope sees the class around it (PEP 695)
                o |= binds
            inner.update(dict.fromkeys(layer.inside, (o, k)))
        for fname in current._fields:
            walk(getattr(current, fname, None), *inner.get(fname, (outer, klass)))

    walk(node, frozenset(), frozenset())
    return out


def _declared_in(
    region: list,
    declaring: Mapping[str, tuple[str, ...]],
    scopes: Mapping[str, tuple[Scope, ...]],
) -> tuple[frozenset[str], frozenset[str]]:
    """Names `region` declares to live elsewhere, and those of them declared
    `global`, not counting the scopes nested in it.

    The grammar says `global` and `nonlocal` both declare. Only `global` also
    skips every enclosing function, which no role says.
    """
    declared: set[str] = set()
    global_: set[str] = set()
    todo = list(region)
    while todo:
        current = todo.pop()
        if not isinstance(current, ast.AST):
            continue
        for fname in declaring.get(type(current).__name__, ()):
            names = set(getattr(current, fname, ()))
            declared |= names
            if isinstance(current, ast.Global):
                global_ |= names
        nested = {f for layer in _scope_layers(current, scopes) for f in layer.inside}
        for fname in current._fields:
            if fname not in nested:
                value = getattr(current, fname, None)
                todo.extend(value if isinstance(value, list) else [value])
    return frozenset(declared), frozenset(global_)


def _as_node_list(value: object) -> list:
    """Wrap a field value so `bound_here` can walk it uniformly."""
    if isinstance(value, list):
        return [v for v in value if isinstance(v, ast.AST)]
    return [value] if isinstance(value, ast.AST) else []


# --------------------------------------------------------------- substitution


def substitute(
    node: Any,
    mapping: Mapping[str, ast.AST],
    grammar: Grammar,
    ns: str,
    *,
    scopes: Mapping[str, tuple[Scope, ...]] | None = None,
    fresh: Fresh | None = None,
) -> Any:
    """Replace *uses* of the names in `mapping`, avoiding capture.

    `node` is copied, so the argument is left alone. Each replacement is copied
    too, so two occurrences of one name do not share a subtree.

    Raises `CaptureError` when the substitution cannot be made safely and
    `fresh` was not supplied:

    * `node` binds one of the names being substituted, by assigning it or by
      shadowing it in an inner scope. Not every occurrence then means the same
      thing, so replacing them all is wrong.
    * a replacement has a free name that `node` binds, so moving it in would
      capture that name.

    With `fresh`, the second is repaired by renaming the offending binders. The
    first is always refused. A repair renames a name where the binding that
    captures gives it its meaning, which takes `scopes` to know; without it the
    tree counts as one scope and the name is renamed throughout.

    With `scopes`, shadowing stops counting as rebinding: a name bound by an
    inner scope hides the outer one inside that scope and is left alone there,
    rather than making the whole substitution impossible. Pass the table that
    says what a name binds over, `astero.python.BINDING_SCOPES` for Python, which is
    not the same as the one saying what `symtable` calls a block.
    """
    out = copy_tree(node)
    shadows: Mapping[int, frozenset[str]] = (
        shadowed_at(out, grammar, ns, scopes) if scopes is not None else {}
    )

    rebound = set(mapping) & _bound_unshadowed(out, grammar, ns, shadows)
    if rebound:
        raise CaptureError(
            f"cannot substitute for {sorted(rebound)}: the target binds "
            "them, by assignment or by shadowing, so not every occurrence "
            "means the same thing"
        )

    incoming: set[str] = set()
    for value in mapping.values():
        incoming |= free_names(value, grammar, ns, scopes=scopes)
    captured = incoming & bound_here(out, grammar, ns)
    if captured:
        if fresh is None:
            raise CaptureError(
                f"substituting would capture {sorted(captured)}; pass `fresh` "
                "to rename the binders instead"
            )
        renames = {n: fresh() for n in sorted(captured)}
        if scopes is None:
            rename(out, renames, grammar, ns)
        else:
            _rename_where_bound(
                out, renames, grammar, ns, scopes=scopes, shadows=shadows
            )

    binders = binding_occurrences(out, grammar, ns)
    _replace_uses(out, mapping, binders, shadows)
    # `_replace_uses` writes into a parent's field, so the root has no parent
    # to be swapped by. Substituting into a bare name silently did nothing
    # until prescrypt-ng lowered `[n for n, _ in pairs]` and got `n` back.
    return _swap(out, mapping, binders, shadows)


def _rename_where_bound(
    node: Any,
    mapping: Mapping[str, str],
    grammar: Grammar,
    ns: str,
    *,
    scopes: Mapping[str, tuple[Scope, ...]],
    shadows: Mapping[int, frozenset[str]],
) -> None:
    """Rename a name only where a binding inside `node` gives it its meaning.

    That is under a region of `node` that binds it, or anywhere when `node`
    binds it at its own level, in the scope it will be placed into. Elsewhere
    the name is free and means what the replacement's free names mean, so
    renaming it with its captor cut it loose: `v + sum(v * z for v in xs)` with
    `z := v` came out as `_t1 + sum(_t1 * v for _t1 in xs)`.
    """
    top = {
        name
        for child in _as_node_list(node)
        for name in binds_in_scope(child, grammar, ns, scopes)
    }
    idents = grammar.ident_slots(ns)
    references = grammar.reference_slots(ns)
    for sub in walk(node, grammar):
        prod = grammar.productions.get(type(sub).__name__)
        if prod is None:
            continue
        bound = top | shadows.get(id(sub), frozenset())
        here = {old: new for old, new in mapping.items() if old in bound}
        _rename_idents(sub, prod, idents.get(prod.name, ()), here)
        _rename_references(sub, references.get(prod.name, ()), here)


def _bound_unshadowed(
    node: Any,
    grammar: Grammar,
    ns: str,
    shadows: Mapping[int, frozenset[str]],
) -> set[str]:
    """Names bound somewhere they are not already shadowed.

    Without a scope table `shadows` is empty and this is `bound_here`, which
    is the conservative answer: every binding counts.
    """
    binding = _binding_fields(grammar, ns)
    idents = grammar.ident_slots()
    out: set[str] = set()
    for sub in walk(node, grammar):
        prod = grammar.productions.get(type(sub).__name__)
        if prod is None:
            continue
        hidden = shadows.get(id(sub), frozenset())
        fields = list(binding.get(prod.name, ()))
        fields += [f for f in idents.get(prod.name, ()) if prod[f].role.binds]
        for fname in fields:
            declared = prod[fname]
            if not declared.applies(sub):
                continue
            out |= {
                name
                for name in bound_names(getattr(sub, fname, None), declared.sort)
                if name not in hidden
            }
    return out


def _replace_uses(
    node: Any,
    mapping: Mapping[str, ast.AST],
    binders: set[int],
    shadows: Mapping[int, frozenset[str]],
) -> None:
    """Swap `Name` uses for their replacements, skipping binding occurrences.

    The one part of this module that stays Python's, and not by omission.
    Substituting a *subtree* for a use needs the language to spell uses as
    nodes in expression position. Python does: an `ast.Name` can be replaced
    by any expression. PL/0 does not — `Assign.name` is typed `Ident`, a bare
    string, and no `BinOp` can go there. So `rename` generalises and this does
    not, and the grammar is what says which case a language is in.
    """
    for parent in _walk_py(node):
        for fname in getattr(parent, "_fields", ()):
            value = getattr(parent, fname, None)
            if isinstance(value, list):
                setattr(
                    parent,
                    fname,
                    [_swap(item, mapping, binders, shadows) for item in value],
                )
            else:
                new = _swap(value, mapping, binders, shadows)
                if new is not value:
                    setattr(parent, fname, new)


def _swap(
    value: Any,
    mapping: Mapping[str, ast.AST],
    binders: set[int],
    shadows: Mapping[int, frozenset[str]],
) -> Any:
    if (
        isinstance(value, ast.Name)
        and value.id in mapping
        and id(value) not in binders
        and value.id not in shadows.get(id(value), frozenset())
    ):
        return copy_tree(mapping[value.id])
    return value


def taken_names(nodes: Iterable[Any], grammar: Grammar) -> set[str]:
    """Every name appearing in any of `nodes`, for seeding a `Fresh`."""
    out: set[str] = set()
    for node in nodes:
        out |= all_names(node, grammar)
    return out
