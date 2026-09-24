"""Every count the docs assert, checked against what reports it.

The README argues that a hand-maintained fact drifts and nobody notices, and
then made the case with hand-maintained facts. It claimed *fifteen* positions
hold a variable name, which was the production count of a different query;
`ident_slots` reports sixteen slots across fifteen productions and
`definitions` twenty-two positions. It claimed TinyPy is "about 170 lines"
when the compiler and its two back ends are 357.

Neither was ever true of anything. They are pinned here rather than corrected,
because correcting them again in six months is the failure this library is
about.

Version-dependent counts are asserted for the interpreter running the suite,
so the numbers below are the ones the prose qualifies with a version.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

from astero.python import PY, VARS

ROOT = pathlib.Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")
INDEX = (ROOT / "docs" / "src" / "index.md").read_text(encoding="utf-8")

#: The compiler and its two back ends. `run_c.py` is a runner, not the
#: compiler, and `__init__.py` is the package docstring.
TINYPY = ("compiler.py", "target_c.py", "vm.py")

#: The example is a project of its own, and its sources are a package. The
#: numbers the prose quotes are about these three files wherever they sit.
TINYPY_SOURCE = ROOT / "examples" / "tinypy" / "src" / "tinypy"


def _lines(*names: str) -> tuple[int, int]:
    """(total, non-comment) over the named files of the TinyPy example."""
    total = code = 0
    for name in names:
        for line in (TINYPY_SOURCE / name).read_text(encoding="utf-8").splitlines():
            total += 1
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                code += 1
    return total, code


def test_the_prose_is_not_empty() -> None:
    """Guard against every assertion below passing over a missing file."""
    assert len(README) > 4000
    assert len(INDEX) > 4000


@pytest.mark.skipif(sys.version_info < (3, 13), reason="the prose says 3.13")
def test_the_identifier_slot_counts_are_what_the_grammar_reports() -> None:
    slots = PY.ident_slots(VARS)
    assert sum(len(v) for v in slots.values()) == 16
    assert len(slots) == 15
    assert "**Sixteen identifier slots**, across fifteen productions" in INDEX
    assert "On Python 3.13 there are sixteen, across fifteen productions" in INDEX


@pytest.mark.skipif(sys.version_info < (3, 13), reason="the prose says 3.13+")
def test_the_binding_position_counts_are_what_the_grammar_reports() -> None:
    positions = sum(len(v) for v in PY.definitions(VARS).values())
    assert positions == 22
    assert "Twenty-two positions in Python bind a variable name" in README
    assert "**twenty-two positions** introduce one" in INDEX


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="the prose says 3.13")
def test_the_role_counts_are_what_the_grammar_reports() -> None:
    fields = [f for prod in PY.productions.values() for f in prod.fields]
    plain = sum(1 for f in fields if str(f.role) == "child")
    assert (
        f"{len(fields)} fields across {len(PY.productions)} productions on 3.13"
        in README
    )
    assert f"{plain} are plain subtrees" in README
    assert f"the other {len(fields) - plain} carry a **role**" in README


def test_the_tinypy_line_counts_are_what_the_files_report() -> None:
    total, code = _lines(*TINYPY)
    compiler, _ = _lines("compiler.py")
    biggest_backend = max(_lines("target_c.py")[0], _lines("vm.py")[0])

    assert biggest_backend < 100
    for page in (README, INDEX):
        assert f"in {total} lines of which {code} are code" in page
        assert f"code: the compiler is {compiler}, each back end under 100" in page


def test_no_page_still_says_fifteen_positions() -> None:
    """The specific wrong claim, named so a revert is caught."""
    for page in (README, INDEX):
        assert not re.search(r"[Ff]ifteen positions", page)
        assert "about 170 lines" not in page
