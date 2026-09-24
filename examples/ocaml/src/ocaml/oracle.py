"""Asking the real OCaml compiler whether we got it right.

A test suite that only compares this compiler against itself proves that it
is consistent, not that it is correct. So where a real `ocaml` is installed,
the tests run the same programme through it and compare: `reference_output`
for what a programme prints, and `reference_signature` for the types
`ocamlc -i` infers.

With no OCaml installed, `available()` says so and those tests skip. If you
want them, `opam switch create 5.2.0` is what installs one.

Both entry points take a path. Where the corpus lives is the tests'
business, not the compiler's.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def available() -> bool:
    return shutil.which("ocaml") is not None


def reference_output(path: Path) -> str:
    """What `ocaml` prints for this programme. Raises if it refuses one."""
    done = subprocess.run(
        ["ocaml", str(path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if done.returncode != 0:
        raise RuntimeError(f"{path.name}: ocaml refused it\n{done.stderr}")
    return done.stdout


def reference_signature(path: Path) -> list[str]:
    """The `val` lines `ocamlc -i` infers for this programme.

    `-i` prints the interface it inferred and writes nothing, which is the
    oracle for `types.py`: the reference implementation's own answer, not a
    second opinion from the same code.
    """
    done = subprocess.run(
        ["ocamlc", "-i", str(path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if done.returncode != 0:
        raise RuntimeError(f"{path.name}: ocamlc refused it\n{done.stderr}")
    # `ocamlc -i` wraps a long `val` onto indented lines; join them back.
    joined = re.sub(r"\n\s+", " ", done.stdout)
    return [line for line in joined.splitlines() if line.startswith("val ")]


def typing_available() -> bool:
    return shutil.which("ocamlc") is not None
