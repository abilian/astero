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
from pathlib import Path

from astero.python import PY, SCOPES, VARS, annotation_blocks, mangle
from astero.scopes import Block, scope_tree

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
