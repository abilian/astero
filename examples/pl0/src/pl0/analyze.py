"""Names: what each block declares, and where a use resolves to.

Two jobs, both answered from the grammar rather than from a table of field
names written here.

`check` walks the scope tree astero builds and reports uses that nothing
declares. `frames` assigns every variable a slot in its procedure's stack
frame, which is what the P-machine's `LOD level offset` needs.

The one thing worth noticing: nothing below asks which *fields* hold a
declaration, and nothing mentions `Var` or `Procedure` at all. Which
fields declare a name is `PL0.definitions(ns)`, and whether a given node
declares one is `names_bound_by`. `Const` appears once, to tell a value
known at compile time from one that needs a slot, which is a fact about
the target and not about the grammar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from astero.scopes import names_bound_by, scope_tree

from . import syntax
from .grammar import PL0, PROCS, SCOPES, VARS

#: The P-machine reserves three words at the base of every frame: the static
#: link, the dynamic link, and the return address. Locals start after them.
FRAME_HEADER = 3


def declarations(block: syntax.Block, ns: str) -> list[syntax.Node]:
    """The nodes in `block` that declare a name in `ns`, in source order.

    Derived twice over: `children` says which fields of a `Block` hold
    nodes, and `names_bound_by` says which of those nodes declare anything
    in this namespace. A procedure declares in `procs` and not in `vars`, so
    asking for `vars` skips it without a special case.
    """
    out: list[syntax.Node] = []
    for slot in PL0.children("Block"):
        value = getattr(block, slot.name, None)
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, syntax.Node) and names_bound_by(item, PL0, ns):
                out.append(item)
    return out


@dataclass
class Frame:
    """One procedure's names: its constants, its slots, and its parent."""

    name: str
    level: int
    parent: Frame | None = None
    consts: dict[str, int] = field(default_factory=dict)
    offsets: dict[str, int] = field(default_factory=dict)
    procedures: dict[str, str] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return FRAME_HEADER + len(self.offsets)

    def lookup(self, name: str) -> tuple:
        """('const', value) or ('var', levels_up, offset). Raises if unknown."""
        frame, up = self, 0
        while frame is not None:
            if name in frame.consts:
                return ("const", frame.consts[name])
            if name in frame.offsets:
                return ("var", up, frame.offsets[name])
            frame, up = frame.parent, up + 1
        raise KeyError(name)

    def procedure(self, name: str) -> str:
        """`levels label`, where levels is how far out the procedure lives.

        The callee's static link must point at the frame of the procedure
        that *declares* it, which is that many links out from this one.
        """
        frame, up = self, 0
        while frame is not None:
            if name in frame.procedures:
                return f"{up} {frame.procedures[name]}"
            frame, up = frame.parent, up + 1
        raise KeyError(name)


def frames(program: syntax.Program) -> dict[int, Frame]:
    """A `Frame` per PL/0 block, keyed by `id` of the block node."""
    out: dict[int, Frame] = {}

    def visit(block: syntax.Block, name: str, level: int, parent: Frame | None):
        frame = Frame(name=name, level=level, parent=parent)
        for node in declarations(block, VARS):
            # The declared name comes from the grammar too, not from a field
            # this file names: `names_bound_by` already answers it, and asking
            # it is what keeps `Var` out of the code below.
            for declared in names_bound_by(node, PL0, VARS):
                match node:
                    case syntax.Const(value=value):
                        frame.consts[declared] = value
                    case _:
                        frame.offsets[declared] = FRAME_HEADER + len(frame.offsets)
        for node in declarations(block, PROCS):
            for declared in names_bound_by(node, PL0, PROCS):
                frame.procedures[declared] = f"{name}${declared}"
        out[id(block)] = frame
        for proc in block.procedures:
            visit(proc.block, frame.procedures[proc.name], level + 1, frame)

    visit(program.block, "main", 0, None)
    return out


def check(program: syntax.Program) -> list[str]:
    """Uses that nothing in scope declares, in both namespaces."""
    problems: list[str] = []
    for ns in (VARS, PROCS):
        tree = scope_tree(
            program, PL0, SCOPES, ns, root_kind="program", root_name="main"
        )
        _visit_scope(program.block, tree, ns, [], problems)
    return problems


def _visit_scope(block, resolved, ns, enclosing, problems):
    """Compare each block's uses against the names visible where it sits."""
    visible = [*enclosing, resolved.bound]
    for node in _nodes(block):
        for name in PL0.reads(node, ns):
            if not any(name in level for level in visible):
                problems.append(f"{type(node).__name__}: {name!r} is not declared")
    children = {c.name: c for c in resolved.children}
    for proc in block.procedures:
        inner = children.get(proc.name)
        if inner is not None:
            _visit_scope(proc.block, inner, ns, visible, problems)


def _nodes(block: syntax.Block):
    """Every node of a block except the bodies of nested procedures."""
    stack: list[object] = [block.body, *block.consts, *block.variables]
    while stack:
        node = stack.pop()
        if not isinstance(node, syntax.Node):
            continue
        yield node
        for slot in PL0.children(type(node).__name__):
            value = getattr(node, slot.name, None)
            stack += value if isinstance(value, list) else [value]
