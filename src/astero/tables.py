"""Families: the tables a grammar cannot derive, declared once.

`astero.grammar` handles structure the grammar determines. This handles the
other kind. Which runtime symbol implements list-append for `Str` is a fact
about the runtime, so nothing derives it and it has to be authored.

What goes wrong is not that it is authored. It is that a family of related
operations gets written as N separate dictionaries, each repeating the index,
each free to disagree about the shared rules, and each with its own way of
saying "this combination does not exist". A `Family` is one declaration:

    LIST = Family.parse(
        "list",
        normalize={"Bool": "Int64"},
        matrix='''
                          Int64            Float64          Str
            append        LIST_APPEND_I64  LIST_APPEND_F64  LIST_APPEND_STR
            get           LIST_GET_I64     LIST_GET_F64     LIST_GET_STR
            get_unchecked LIST_GET_I64_U   LIST_GET_F64_U   .
        ''',
    )

Three things follow. The normalization is stated once and applies to every row,
so a rule like "a Bool crosses as an Int64" cannot be spelled one way here and
another way there. A hole is written as a hole, rather than as a missing key
plus a `.get()` that returns None. And totality is checkable: every row covers
the index, or says explicitly where it does not.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Final

#: A cell with no symbol. Written `.` in a matrix.
#: A family that does not define a symbol at some (operation, key). Spelled
#: `Final[None]` rather than bare, so `symbol is not HOLE` narrows the way
#: `is not None` does: to a checker the two are the same test only when the
#: name cannot be rebound.
HOLE: Final[None] = None

_HOLE_MARKERS = frozenset({".", "-", "_"})


class TableError(ValueError):
    """A family that does not describe a rectangle."""


@dataclass(frozen=True)
class Family:
    """A set of operations over one index, with one normalization."""

    name: str
    #: The keys every row is defined over, in declaration order.
    index: tuple[str, ...]
    #: Keys that stand for another key. Applied before every lookup.
    normalize: Mapping[str, str]
    #: operation -> key -> symbol, or HOLE where the combination does not exist.
    rows: Mapping[str, Mapping[str, str | None]]

    # ------------------------------------------------------------- queries

    def __iter__(self) -> Iterator[str]:
        return iter(self.rows)

    def keys(self) -> tuple[str, ...]:
        """Every key a lookup accepts, including the normalized aliases."""
        return (*self.index, *sorted(self.normalize))

    def resolve(self, key: str) -> str:
        """Apply the normalization. `Bool` is an `Int64` on the wire."""
        return self.normalize.get(key, key)

    def lookup(self, op: str, key: str) -> str | None:
        """The symbol for `op` at `key`, or None where the family has a hole."""
        if op not in self.rows:
            msg = f"family {self.name!r} has no operation {op!r}"
            raise KeyError(msg)
        resolved = self.resolve(key)
        if resolved not in self.index:
            msg = (
                f"family {self.name!r} is not defined at {key!r}"
                f" (index: {', '.join(self.index)})"
            )
            raise KeyError(msg)
        return self.rows[op][resolved]

    def column(self, key: str) -> dict[str, str | None]:
        """Every operation at one key."""
        return {op: self.lookup(op, key) for op in self.rows}

    def as_dict(self, op: str, *, include_aliases: bool = True) -> dict[str, str]:
        """One row as the plain dictionary a hand-written table would be.

        Holes are absent, which is what a dictionary can express. This is the
        shape a consumer that has not adopted families still expects.
        """
        keys = self.keys() if include_aliases else self.index
        out = {}
        for key in keys:
            symbol = self.lookup(op, key)
            if symbol is not HOLE:
                out[key] = symbol
        return out

    def holes(self) -> tuple[tuple[str, str], ...]:
        """Every declared hole, as (operation, key)."""
        return tuple(
            (op, key)
            for op, cells in self.rows.items()
            for key in self.index
            if cells[key] is HOLE
        )

    def check(self) -> list[str]:
        """Complaints about the family's shape. Empty when it is a rectangle."""
        problems = []
        if len(set(self.index)) != len(self.index):
            problems.append(f"{self.name}: duplicate key in the index")
        for alias, target in self.normalize.items():
            if target not in self.index:
                problems.append(
                    f"{self.name}: {alias!r} normalizes to {target!r}, "
                    "which is not in the index"
                )
            if alias in self.index:
                problems.append(
                    f"{self.name}: {alias!r} is both an index key and an alias"
                )
        for op, cells in self.rows.items():
            missing = [k for k in self.index if k not in cells]
            extra = [k for k in cells if k not in self.index]
            if missing:
                problems.append(f"{self.name}.{op}: no cell for {', '.join(missing)}")
            if extra:
                problems.append(
                    f"{self.name}.{op}: {', '.join(extra)} is not in the index"
                )
        return problems

    def as_matrix(self) -> str:
        """The declaration, rendered back. Holes show as `.`."""
        ops = list(self.rows)
        first = max((len(o) for o in ops), default=0) + 2
        widths = [
            max(len(k), *(len(self.rows[o][k] or ".") for o in ops)) + 2
            if ops
            else len(k) + 2
            for k in self.index
        ]
        head = "".ljust(first) + "".join(
            k.ljust(w) for k, w in zip(self.index, widths, strict=True)
        )
        lines = [head.rstrip()]
        for op in ops:
            cells = "".join(
                (self.rows[op][k] or ".").ljust(w)
                for k, w in zip(self.index, widths, strict=True)
            )
            lines.append((op.ljust(first) + cells).rstrip())
        return "\n".join(lines)

    # ----------------------------------------------------------- building

    @classmethod
    def parse(
        cls,
        name: str,
        matrix: str,
        normalize: Mapping[str, str] | None = None,
    ) -> Family:
        """Read a whitespace-aligned matrix. First non-blank line is the index."""
        lines = [
            line.split("#", 1)[0].rstrip()
            for line in matrix.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not lines:
            msg = f"family {name!r} has no rows"
            raise TableError(msg)
        index = tuple(lines[0].split())
        rows: dict[str, dict[str, str | None]] = {}
        for line in lines[1:]:
            op, *cells = line.split()
            if len(cells) != len(index):
                msg = (
                    f"family {name!r}, row {op!r}: {len(cells)} cells "
                    f"for {len(index)} keys. A hole is written `.`"
                )
                raise TableError(msg)
            rows[op] = {
                key: (HOLE if cell in _HOLE_MARKERS else cell)
                for key, cell in zip(index, cells, strict=True)
            }
        family = cls(name=name, index=index, normalize=dict(normalize or {}), rows=rows)
        problems = family.check()
        if problems:
            joined = "\n  ".join(problems)
            raise TableError(f"family {name!r} is not well-formed:\n  {joined}")
        return family
