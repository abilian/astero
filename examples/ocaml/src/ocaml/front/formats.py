"""The format strings `Printf.printf` and `Printf.sprintf` take.

A format is a small language inside a string literal, and two stages read
it: the checker, to know that `"%d: %s\\n"` makes `printf` take an `int` and
then a `string`, and the runtime, to render it. Both call `conversions`, so
they cannot disagree about which directives there are.

The subset is what a prépa programme writes: flags, a width, a precision,
and one of the letters in `LETTERS`. `%a` and `%t` take a printing function
as an argument and are not in it; neither is `%S`, nor the `l`, `n` and `L`
integer sizes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Each conversion letter, with the OCaml type of the argument it consumes.
LETTERS: dict[str, str] = {
    "d": "int",
    "i": "int",
    "u": "int",
    "x": "int",
    "X": "int",
    "o": "int",
    "s": "string",
    "c": "char",
    "f": "float",
    "F": "float",
    "e": "float",
    "E": "float",
    "g": "float",
    "G": "float",
    "b": "bool",
    "B": "bool",
}

_DIRECTIVE = re.compile(r"%([-0+ #]*)(\d*)(?:\.(\d+))?(.)")


class FormatError(ValueError):
    """A directive outside the subset, or a `%` at the end of the string."""


@dataclass(frozen=True)
class Conversion:
    """One `%` directive that consumes an argument."""

    flags: str
    width: str
    precision: str | None
    letter: str


def pieces(fmt: str) -> list[str | Conversion]:
    """The format as literal text and conversions, in order.

    `%%` is literal text, and `%!` (flush) is nothing at all.
    """
    out: list[str | Conversion] = []
    at = 0
    for found in _DIRECTIVE.finditer(fmt):
        out.append(fmt[at : found.start()])
        at = found.end()
        flags, width, precision, letter = found.groups()
        if letter == "%":
            out.append("%")
        elif letter == "!":
            pass
        elif letter in LETTERS:
            out.append(Conversion(flags, width, precision, letter))
        else:
            raise FormatError(f"unsupported format directive %{letter}")
    rest = fmt[at:]
    if "%" in rest:
        raise FormatError("incomplete format directive at the end")
    out.append(rest)
    return [piece for piece in out if piece]


def conversions(fmt: str) -> list[Conversion]:
    """The directives that consume an argument, in order."""
    return [piece for piece in pieces(fmt) if isinstance(piece, Conversion)]
