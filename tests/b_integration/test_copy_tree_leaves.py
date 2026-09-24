"""`LEAVES` checked against the standard library.

`copy_tree` without a grammar refuses anything that is not a node, a list, or
a value a Python AST field can hold. That last set is authored — CPython's
ASDL closes it but exposes no list of it — so it earns its place the way
`CTX_NODES` does, by being derived again from the corpus and compared.

The refusal is the point: before it, a node of a foreign kind fell through and
came back aliased, so a caller who mutated the "copy" mutated the original. A
list that is too narrow turns that silent corruption into a loud failure on
ordinary Python, which is the direction an error should fail in, but it would
still be a regression. This is what says it is not too narrow.
"""

from __future__ import annotations

import ast
import sysconfig
from collections import Counter
from pathlib import Path

from astero.python.rewriting import LEAVES


def _stdlib_files(limit: int | None = None) -> list[Path]:
    root = Path(sysconfig.get_paths()["stdlib"])
    files = sorted(root.rglob("*.py"))
    return files[:limit] if limit else files


def test_leaves_covers_every_value_the_standard_library_holds() -> None:
    """Nothing in the corpus falls outside the list, and nothing in it is dead.

    Both directions, because they catch opposite mistakes: a missing entry
    makes `copy_tree` refuse ordinary Python, and a speculative one is an
    authored claim about the language that nothing supports.
    """
    seen: Counter[type] = Counter()
    unlisted: dict[str, str] = {}
    for path in _stdlib_files():
        try:
            tree = ast.parse(path.read_bytes())
        except (SyntaxError, ValueError):
            continue  # a 3.x-only or deliberately broken fixture
        for node in ast.walk(tree):
            for _name, value in ast.iter_fields(node):
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, (ast.AST, list)):
                        continue
                    seen[type(item)] += 1
                    if not isinstance(item, LEAVES):
                        unlisted.setdefault(type(item).__name__, str(path))

    assert not unlisted, f"a field value no `LEAVES` entry admits: {unlisted}"

    unused = [t.__name__ for t in LEAVES if not any(issubclass(o, t) for o in seen)]
    assert not unused, f"`LEAVES` entries the corpus never produces: {unused}"

    # A line, not a number: the measured count is 3,017,268 on 3.12, of which
    # `complex` is the rarest real entry at 653. A corpus that stopped yielding
    # leaves would pass both assertions above vacuously.
    assert seen.total() > 1_000_000, seen


def test_copy_tree_reaches_them_and_returns_the_tree_it_was_given() -> None:
    """The refusal never fires on real Python, and the copy is still a copy."""
    from astero.python.rewriting import copy_tree

    for path in _stdlib_files(limit=300):
        try:
            tree = ast.parse(path.read_bytes())
        except (SyntaxError, ValueError):
            continue
        clone = copy_tree(tree)
        assert clone is not tree
        assert ast.dump(clone) == ast.dump(tree), path
