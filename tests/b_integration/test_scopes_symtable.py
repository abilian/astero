"""D1 and D2: derived scopes against CPython's own symbol table.

`symtable` is to binding what `ctx` was to roles: CPython computes the answer
itself, so a declared scoping spec can be checked rather than argued about.

Two residual divergence classes are known and recorded in
`notes/common/scopes-result.md`. The thresholds here hold the line at what has
been measured, so a regression shows up as a failure rather than as drift.
"""

from __future__ import annotations

import ast
import symtable
import sysconfig
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from astero.python import (
    BINDING_SCOPES,
    PY,
    SCOPES,
    VARS,
    annotation_blocks,
    free_names,
    mangle,
)
from astero.python.hygiene import binding_occurrences, shadowed_at
from astero.scopes import Block, evaluated_outside, scope_tree

#: CPython's implicit comprehension argument, not a source-level name.
_INTERNAL = {
    ".0",
    ".defaults",
    ".generic_base",
    ".type_params",
    "__type_params__",
    ".format",
}


def _resolve(tree: ast.AST) -> Block:
    return scope_tree(
        tree, PY, SCOPES, VARS, mangle=mangle, siblings=annotation_blocks(tree)
    )


def _sym_shape(block: symtable.SymbolTable) -> tuple:
    kind = block.get_type()
    return (
        str(getattr(kind, "value", kind)),
        block.get_name(),
        tuple(_sym_shape(c) for c in block.get_children()),
    )


def _sym_locals(block: symtable.SymbolTable, out: list[set[str]]) -> list[set[str]]:
    out.append({s.get_name() for s in block.get_symbols() if s.is_local()} - _INTERNAL)
    for child in block.get_children():
        _sym_locals(child, out)
    return out


def test_d1_the_scope_tree_matches_cpython() -> None:
    """D1: block kinds, names and nesting, over the standard library."""
    files = sorted(Path(sysconfig.get_paths()["stdlib"]).rglob("*.py"))
    examined = mismatched = 0
    for path in files:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
            table = symtable.symtable(source, str(path), "exec")
        except (SyntaxError, ValueError, UnicodeDecodeError, RecursionError):
            continue
        examined += 1
        mismatched += _resolve(tree).shape() != _sym_shape(table)
    assert examined > 300, f"corpus too small: {examined} files"
    # PEP 695 annotation scopes are not modelled; see the result note.
    assert mismatched / examined < 0.02, f"{mismatched} of {examined} trees differ"


def test_d2_the_bound_names_match_cpython() -> None:
    """D2: what each block binds, over the standard library."""
    files = sorted(Path(sysconfig.get_paths()["stdlib"]).rglob("*.py"))
    agree = differ = 0
    for path in files:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
            table = symtable.symtable(source, str(path), "exec")
        except (SyntaxError, ValueError, UnicodeDecodeError, RecursionError):
            continue
        block = _resolve(tree)
        if block.shape() != _sym_shape(table):
            continue
        for theirs, ours in zip(_sym_locals(table, []), block.walk(), strict=True):
            if theirs == ours.owns():
                agree += 1
            else:
                differ += 1
    assert agree > 20_000, f"only {agree} blocks compared"
    assert differ / (agree + differ) < 0.001, f"{differ} of {agree + differ} differ"


def test_the_awkward_cases_resolve_as_cpython_does() -> None:
    """The cases a hand-written binder gets wrong, checked one by one."""
    source = (
        "import os.path\n"
        "import json as J\n"
        "from re import sub\n"
        "from os import *\n"
        "class C:\n"
        "    __marker = 1\n"
        "    def m(self):\n"
        "        global counter\n"
        "        counter = 1\n"
        "        __local = 2\n"
        "        return [i for i in range(3)]\n"
    )
    block = _resolve(ast.parse(source))
    table = symtable.symtable(source, "<t>", "exec")
    assert block.shape() == _sym_shape(table)
    for theirs, ours in zip(_sym_locals(table, []), block.walk(), strict=True):
        assert theirs == ours.owns(), f"{ours.name}: {ours.owns()} vs {theirs}"


# ------------------------------------------------ D3: what each block reads


#: Names CPython adds on its own: `super()`'s cell, PEP 695 and PEP 649 plumbing.
_SYNTHETIC = _INTERNAL | {"__class__", "__classdict__", "__conditional_annotations__"}


def _kind(block: symtable.SymbolTable) -> str:
    kind = block.get_type()
    return str(getattr(kind, "value", kind))


def _sym_reads(
    block: symtable.SymbolTable, out: dict[int, set[str]]
) -> tuple[set[str], set[str]]:
    """What `block` and the blocks inside it read from outside `block`, as
    (globals, names from an enclosing function).

    A global, declared or not, passes every function on its way to the module,
    even one binding the same name. A free name stops at the first function
    that binds it. A class stops neither: its bindings are invisible to the
    functions inside it.
    """
    symbols = [s for s in block.get_symbols() if s.is_referenced()]
    # `not is_local()`: `symtable` takes any table named `top` for the module,
    # so a function called `top` reports its own parameters as global.
    globals_ = {s.get_name() for s in symbols if s.is_global() and not s.is_local()}
    free = {s.get_name() for s in symbols if s.is_free()}
    local = {s.get_name() for s in block.get_symbols() if s.is_local()}
    for child in block.get_children():
        below_globals, below_free = _sym_reads(child, out)
        globals_ |= below_globals
        free |= below_free if _kind(block) == "class" else below_free - local
    if _kind(block) == "module":
        globals_ -= local
    out[block.get_id()] = globals_ | free
    return globals_, free


def _nodes(value: object) -> list[ast.AST]:
    if isinstance(value, list):
        return [v for v in value if isinstance(v, ast.AST)]
    return [value] if isinstance(value, ast.AST) else []


def _our_reads(block: Block) -> set[str]:
    """The same question asked of astero: `free_names` for a module, and for
    any other block the uses in its own layer's fields that `shadowed_at`,
    walking from the block's node, finds bound by nothing inside it."""
    node = block.node
    if isinstance(node, ast.Module):
        return free_names(list(node.body), PY, VARS, scopes=BINDING_SCOPES)
    shadows = shadowed_at(node, PY, VARS, BINDING_SCOPES)
    binders = binding_occurrences(node, PY, VARS)
    layers = [
        layer
        for layer in BINDING_SCOPES.get(type(node).__name__, ())
        if layer.kind == block.kind and layer.applies(node)
    ]
    cut = {
        id(c)
        for layer in layers
        for _, _, c in evaluated_outside(node, layer, BINDING_SCOPES)
    }
    todo = [
        child
        for layer in layers
        for field in layer.inside
        for child in _nodes(getattr(node, field, None))
    ]
    reads: set[str] = set()
    while todo:
        current = todo.pop()
        if id(current) in cut:
            continue
        if (
            isinstance(current, ast.Name)
            and id(current) not in binders
            and current.id not in shadows[id(current)]
        ):
            reads.add(current.id)
        todo.extend(ast.iter_child_nodes(current))
    return reads


def _paired(table: symtable.SymbolTable, block: Block):
    """Blocks matched to tables. `symtable` does not list two same-named
    siblings in source order (a function defined in both arms of an `if`), so
    siblings are matched on kind, name and line rather than on position."""
    yield table, block

    def key_theirs(t: symtable.SymbolTable) -> tuple:
        return (_kind(t), t.get_name(), t.get_lineno())

    def key_ours(b: Block) -> tuple:
        return (b.kind, b.name, getattr(b.node, "lineno", 0))

    theirs = sorted(table.get_children(), key=key_theirs)
    ours = sorted(block.children, key=key_ours)
    for t, b in zip(theirs, ours, strict=True):
        yield from _paired(t, b)


def _private(tree: ast.AST) -> Callable[[str], bool]:
    """Whether a name is private, in either spelling: `__x` as written, or
    `_C__x` as `symtable` mangles it inside `class C`. Mangling is D2's
    subject, and `free_names` does not model it."""
    prefixes = tuple(
        f"_{n.name.lstrip('_')}__"
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef)
    )

    def private(name: str) -> bool:
        written = name.startswith("__") and not name.endswith("__")
        return written or bool(prefixes and name.startswith(prefixes))

    return private


def _reads_compared(
    source: str, path: str
) -> Iterator[tuple[Block, set[str], set[str]]]:
    """(block, what symtable says it reads, what free_names says), per block."""
    tree = ast.parse(source)
    table = symtable.symtable(source, path, "exec")
    root = _resolve(tree)
    if root.shape() != _sym_shape(table):
        return
    private = _private(tree)
    theirs_of: dict[int, set[str]] = {}
    _sym_reads(table, theirs_of)
    for t, b in _paired(table, root):
        if b.kind not in {"module", "function", "class"}:
            continue
        keep = {
            n for n in theirs_of[t.get_id()] if n not in _SYNTHETIC and not private(n)
        }
        ours = {n for n in _our_reads(b) if n not in _SYNTHETIC and not private(n)}
        yield b, keep, ours


def test_d3_what_each_block_reads_matches_cpython() -> None:
    """D3: the names each block reads from outside itself, over the standard
    library. D1 and D2 check where names are bound; this checks where a use
    resolves, which is what substitution and capture checking rest on."""
    files = sorted(Path(sysconfig.get_paths()["stdlib"]).rglob("*.py"))
    agree = differ = 0
    for path in files:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            compared = list(_reads_compared(source, str(path)))
        except (SyntaxError, ValueError, UnicodeDecodeError, RecursionError):
            continue
        for _block, theirs, ours in compared:
            if theirs == ours:
                agree += 1
            else:
                differ += 1
    assert agree > 20_000, f"only {agree} blocks compared"
    # The line held on the worst interpreter's stdlib: 4.2% on 3.15, 0.1% on
    # 3.11. Nearly all of it is annotations CPython never evaluates (PEP 563
    # modules, and local annotations from 3.14), one of the two causes in
    # `test_d3_what_the_scope_table_cannot_say_yet`; see
    # notes/common/reads-result.md.
    assert differ / (agree + differ) < 0.05, f"{differ} of {agree + differ} differ"


def _reads_disagree(source: str) -> list[tuple[str, set[str], set[str]]]:
    return [
        (b.name, theirs, ours)
        for b, theirs, ours in _reads_compared(source, "<t>")
        if theirs != ours
    ]


_RESOLVED = {
    "global": "def f():\n    global g\n    g = 1\n    return g\n",
    "global through an enclosing binding": (
        "def outer():\n    g = 1\n    def inner():\n        global g\n        return g\n"
    ),
    "nonlocal": (
        "def f():\n    x = 1\n    def g():\n        nonlocal x\n        x = 2\n"
        "        return x\n"
    ),
    "a class body is invisible to its methods": (
        "class C:\n    x = 1\n    def m(self):\n        return x\n"
    ),
    "and to its generators": "class C:\n    x = 1\n    y = list(x for _ in (1, 2))\n",
    "a default is evaluated outside the function": (
        "def f(a=v):\n    v = 1\n    return a\n"
    ),
    "so is an annotation": "def f(a: T):\n    T = 1\n",
    "a generator's first iterable is evaluated outside it": "g = (x for x in xs)\n",
    "but its other iterables inside": "g = (y for x in xs for y in x)\n",
    "a class's first iterable sees the class": (
        "class C:\n    xs = [1]\n    g = list(x for x in xs)\n"
    ),
}


@pytest.mark.parametrize("source", _RESOLVED.values(), ids=_RESOLVED.keys())
def test_d3_the_awkward_reads_resolve_as_cpython_does(source: str) -> None:
    assert _reads_disagree(source) == []


#: Where astero and CPython still disagree. Closing one makes its case fail
#: here until it moves to `_RESOLVED`.
_UNRESOLVED = {
    "PEP 563 annotations are never evaluated": (
        "from __future__ import annotations\ndef f(a: T) -> U:\n    pass\n"
    ),
    "a walrus in a comprehension binds around it (PEP 572)": (
        "def f(xs):\n    return sum((d := x) * d for x in xs)\n"
    ),
}


@pytest.mark.xfail(
    strict=True,
    reason="an annotation CPython never evaluates is still a use to astero, and a "
    "comprehension's walrus binds inside it",
)
@pytest.mark.parametrize("source", _UNRESOLVED.values(), ids=_UNRESOLVED.keys())
def test_d3_what_the_scope_table_cannot_say_yet(source: str) -> None:
    assert _reads_disagree(source) == []
