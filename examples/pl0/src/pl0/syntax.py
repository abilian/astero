"""PL/0's abstract syntax, as ordinary dataclasses.

PL/0 is Wirth's teaching language: constants, variables, nested procedures
without parameters, `begin`/`end`, `if`, `while`, `call`, and integer
arithmetic. It is the language most compiler courses build first.

Nothing here imports astero. These are the classes a compiler for this
language would have anyway, and `grammar.py` declares them afterwards.

`Ident` marks the fields that hold a *name* rather than a node or plain
data. astero is told about it once, as an ident sort, and every query about
names follows from that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: A field holding a name. Distinct from `str` so the declaration can say
#: which strings are identifiers and which are just data.
Ident = str


@dataclass
class Node:
    """Root of the hierarchy, so `concrete()` can tell abstract from real."""


@dataclass
class Expr(Node):
    """An integer-valued expression."""


@dataclass
class Cond(Node):
    """A truth-valued expression. PL/0 keeps the two sorts apart."""


@dataclass
class Stmt(Node):
    """A statement."""


# ------------------------------------------------------------- expressions


@dataclass
class Number(Expr):
    value: int


@dataclass
class Name(Expr):
    name: Ident


@dataclass
class Neg(Expr):
    value: Expr


@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


# -------------------------------------------------------------- conditions


@dataclass
class Odd(Cond):
    value: Expr


@dataclass
class Compare(Cond):
    op: str
    left: Expr
    right: Expr


# -------------------------------------------------------------- statements


@dataclass
class Assign(Stmt):
    name: Ident
    value: Expr


@dataclass
class Call(Stmt):
    name: Ident


@dataclass
class Begin(Stmt):
    body: list[Stmt] = field(default_factory=list)


@dataclass
class If(Stmt):
    cond: Cond
    then: Stmt


@dataclass
class While(Stmt):
    cond: Cond
    body: Stmt


@dataclass
class Write(Stmt):
    value: Expr


@dataclass
class Empty(Stmt):
    """The empty statement, which PL/0's grammar allows."""


# ----------------------------------------------------------- declarations


@dataclass
class Const(Node):
    name: Ident
    value: int


@dataclass
class Var(Node):
    name: Ident


@dataclass
class Procedure(Node):
    name: Ident
    block: Block


@dataclass
class Block(Node):
    consts: list[Const] = field(default_factory=list)
    variables: list[Var] = field(default_factory=list)
    procedures: list[Procedure] = field(default_factory=list)
    body: Stmt = field(default_factory=Empty)


@dataclass
class Program(Node):
    block: Block


#: Every class the grammar is read from. Order is irrelevant; the abstract
#: bases are included so `concrete("Stmt")` has something to answer with.
CLASSES = [
    Node,
    Expr,
    Cond,
    Stmt,
    Number,
    Name,
    Neg,
    BinOp,
    Odd,
    Compare,
    Assign,
    Call,
    Begin,
    If,
    While,
    Write,
    Empty,
    Const,
    Var,
    Procedure,
    Block,
    Program,
]
