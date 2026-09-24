"""Compile TinyPy to C, build it, and run it — so the C target has an oracle."""

from __future__ import annotations

import ast
import subprocess
import tempfile
from pathlib import Path

from . import compiler as tinypy, target_c


def to_c(source: str) -> str:
    tree = tinypy.DESUGAR(ast.parse(source))
    fn = tree.body[0]
    body = target_c.compile_function(fn, tinypy.TINYPY, set(tinypy.slots(fn)))
    return (
        "#include <stdio.h>\n#include <stdlib.h>\n\n"
        + body
        + (
            f"\nint main(int argc, char **argv) {{\n"
            f'    printf("%ld\\n", {fn.name}(atol(argv[1])));\n'
            f"    return 0;\n}}\n"
        )
    )


def run(source: str, argument: int) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "p.c"
        exe = Path(tmp) / "p"
        src.write_text(to_c(source))
        subprocess.run(["cc", "-O0", "-o", str(exe), str(src)], check=True)
        out = subprocess.run(
            [str(exe), str(argument)], capture_output=True, text=True, check=True
        )
        return int(out.stdout.strip())
