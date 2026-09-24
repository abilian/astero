"""The command line: `python -m ocaml`.

    python -m ocaml corpus/sorting.ml            run it
    python -m ocaml --types corpus/tree.ml       print the types inferred
    python -m ocaml --names corpus/fact.ml       print the scopes
    python -m ocaml --python corpus/fact.ml      print the Python it emits
    python -m ocaml --printed corpus/fact.ml     print it back out

One flag per view, and the flags come from `pipeline.VIEWS` rather than
being listed here, so a view added there is a flag without another edit.

A programme that does not compile prints why, on standard error, and exits
non-zero.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import VIEWS, analyse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ocaml",
        description="A compiler for the OCaml subset taught in prépa.",
    )
    parser.add_argument("file", type=Path, help="a caml-prépa programme")
    shown = parser.add_mutually_exclusive_group()
    for view, what in VIEWS.items():
        shown.add_argument(
            f"--{view}", dest="show", action="store_const", const=view, help=what
        )
    parser.set_defaults(show="run")
    args = parser.parse_args(argv)

    found = analyse(args.file.read_text(encoding="utf-8"))
    for problem in found["errors"]:
        print(problem, file=sys.stderr)
    text = found[args.show]
    if text:
        sys.stdout.write(text if text.endswith("\n") else f"{text}\n")
    return 1 if found["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
