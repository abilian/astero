"""A1: `ctx` derived from declared roles alone, checked against CPython.

The role table is the one piece of the Python grammar written by hand, so it
earns its place by being auditable against the parser that produced the trees.
This walks the whole standard library, which is why it is an integration test.
"""

from __future__ import annotations

import ast
import sysconfig
from pathlib import Path

from astero import grammar
from astero.python import PY, VARS


def _stdlib_files(limit: int | None = None) -> list[Path]:
    root = Path(sysconfig.get_paths()["stdlib"])
    # Test directories are kept: they hold the strangest legal Python there is.
    files = sorted(root.rglob("*.py"))
    return files[:limit] if limit else files


def _reconstruct_ctx(tree: ast.AST) -> dict[int, str]:
    """Assign every `ctx` from declared roles alone, ignoring what the parser said."""
    binding = PY.positions(grammar.Kind.DEF, VARS)
    defusing = PY.positions(grammar.Kind.DEFUSE, VARS)
    deleting = PY.positions(grammar.Kind.DEL, VARS)
    out: dict[int, str] = {}

    def mark(node: object, ctx: str) -> None:
        if isinstance(node, (ast.Tuple, ast.List)):
            out[id(node)] = ctx
            for elt in node.elts:
                mark(elt, ctx)
        elif isinstance(node, ast.Starred):
            out[id(node)] = ctx
            mark(node.value, ctx)
        elif isinstance(node, ast.AST) and "ctx" in node._fields:
            out[id(node)] = ctx

    for node in ast.walk(tree):
        if "ctx" in node._fields:
            out.setdefault(id(node), "Load")
        name = type(node).__name__
        for fields, ctx in (
            (binding.get(name, ()), "Store"),
            (defusing.get(name, ()), "Store"),
            (deleting.get(name, ()), "Del"),
        ):
            _mark_fields(node, fields, ctx, mark)
    return out


def _mark_fields(node: ast.AST, fields, ctx: str, mark) -> None:
    for fname in fields:
        value = getattr(node, fname, None)
        for target in value if isinstance(value, list) else [value]:
            if target is not None:
                mark(target, ctx)


def test_a1_ctx_is_derivable_from_roles() -> None:
    checked = disagreements = examined = 0
    for path in _stdlib_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, ValueError, UnicodeDecodeError, RecursionError):
            continue
        examined += 1
        derived = _reconstruct_ctx(tree)
        for node in ast.walk(tree):
            if "ctx" in node._fields:
                checked += 1
                ctx = getattr(node, "ctx", None)
                if derived.get(id(node), "Load") != type(ctx).__name__:
                    disagreements += 1
    # The floor only guards against a vacuous pass. Stdlib size varies by build
    # and by version, so it stays well under the smallest corpus seen (3.15's
    # ~516k positions) rather than tracking any particular one.
    assert examined > 300, f"corpus too small to mean anything: {examined} files"
    assert checked > 50_000, f"only {checked} ctx positions examined"
    assert disagreements == 0, (
        f"{disagreements} of {checked} ctx positions across {examined} files "
        "disagree with CPython"
    )
