"""Every `case Cls()` in the library names something that is a class.

`case X()` where `X` is a tuple compiles without complaint and raises
`TypeError: called match pattern must be a class` when the arm is reached.
`isinstance(node, X)` accepts a tuple, so converting one to the other is
exactly where the mistake gets made: `case CTX_NODES()` looked right, was
accepted by the compiler, by ruff and by four type checkers, and took out
226 tests the moment `fix_contexts` ran.

The second test is the other half. `match` tries arms in order, so a base
class above a subclass makes the lower arm unreachable, which an
`isinstance` chain has as a hazard too but does not rearrange.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "astero"

#: Every module under `src/astero`, dotted. `rglob`, not `glob`: when the
#: package grew `astero.python` and `astero.testing`, a non-recursive scan
#: stopped seeing them and this file quietly went from linting the emitter's
#: 38 class patterns to linting none of them, without failing.
MODULES = sorted(
    ".".join(p.relative_to(SRC).with_suffix("").parts)
    for p in SRC.rglob("*.py")
    if p.stem != "__init__"
)


def _path(name: str) -> Path:
    """The file a dotted module name under `astero` lives in."""
    return SRC / (name.replace(".", "/") + ".py")


def _class_patterns(path: Path, module):
    """(lineno, source text, resolved object) per class pattern in `path`."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Match):
            continue
        for case in node.cases:
            for pat in ast.walk(case.pattern):
                if not isinstance(pat, ast.MatchClass):
                    continue
                name = ast.unparse(pat.cls)
                obj = module
                for part in name.split("."):
                    obj = getattr(obj, part, None)
                yield case, pat.lineno, name, obj


@pytest.mark.parametrize("name", MODULES)
def test_every_class_pattern_names_a_class(name: str) -> None:
    module = importlib.import_module(f"astero.{name}")
    bad = [
        f"{name}.py:{line}  case {text}() -> {type(obj).__name__}"
        for _case, line, text, obj in _class_patterns(_path(name), module)
        if obj is not None and not isinstance(obj, type)
    ]
    assert not bad, (
        "a class pattern needs a class; use a guard for a tuple:\n" + "\n".join(bad)
    )


@pytest.mark.parametrize("name", MODULES)
def test_no_case_is_shadowed_by_an_earlier_one(name: str) -> None:
    module = importlib.import_module(f"astero.{name}")
    path = _path(name)
    unreachable = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Match):
            continue
        seen: list[tuple[str, type]] = []
        for case in node.cases:
            if case.guard is not None:
                continue  # a guard can narrow whatever the pattern admits
            here = [
                (text, obj)
                for c, _line, text, obj in _class_patterns(path, module)
                if c is case and isinstance(obj, type)
            ]
            for text, cls in here:
                unreachable += [
                    f"{name}.py:{case.pattern.lineno}  {text} is covered by {above}"
                    for above, acls in seen
                    if cls is not acls and issubclass(cls, acls)
                ]
            seen += here
    assert not unreachable, "\n".join(unreachable)
