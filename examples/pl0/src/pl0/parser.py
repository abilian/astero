"""A recursive-descent parser for PL/0.

Included because astero does not parse, and a tutorial that started from a
tree would leave that boundary vague. This is the part you write yourself,
in whatever way you like; astero begins at the tree it returns.

The grammar, in Wirth's notation:

    program    = block "." .
    block      = [ "const" ident "=" number { "," ident "=" number } ";" ]
                 [ "var" ident { "," ident } ";" ]
                 { "procedure" ident ";" block ";" } statement .
    statement  = [ ident ":=" expression | "call" ident | "!" expression
                 | "begin" statement { ";" statement } "end"
                 | "if" condition "then" statement
                 | "while" condition "do" statement ] .
    condition  = "odd" expression | expression relop expression .
    expression = [ "+" | "-" ] term { ( "+" | "-" ) term } .
    term       = factor { ( "*" | "/" ) factor } .
    factor     = ident | number | "(" expression ")" .
"""

from __future__ import annotations

import re

from .syntax import (
    Assign,
    Begin,
    BinOp,
    Block,
    Call,
    Compare,
    Const,
    Empty,
    If,
    Name,
    Neg,
    Number,
    Odd,
    Procedure,
    Program,
    Var,
    While,
    Write,
)

KEYWORDS = frozenset({
    "begin",
    "call",
    "const",
    "do",
    "end",
    "if",
    "odd",
    "procedure",
    "then",
    "var",
    "while",
})

_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+)|(?P<name>[A-Za-z_]\w*)|(?P<sym>:=|<=|>=|[-+*/()=#<>,;.!]))"
)


class ParseError(SyntaxError):
    """The source is not PL/0."""


def tokenize(source: str) -> list[tuple[str, str]]:
    """(kind, text) pairs, where kind is 'num', 'name', 'sym' or 'kw'."""
    out: list[tuple[str, str]] = []
    at = 0
    while at < len(source):
        if source[at].isspace():
            at += 1
            continue
        found = _TOKEN.match(source, at)
        if found is None:
            raise ParseError(f"stray character {source[at]!r} at {at}")
        at = found.end()
        kind = found.lastgroup
        text = found.group()
        assert kind is not None
        text = text.strip()
        if kind == "name" and text in KEYWORDS:
            kind = "kw"
        out.append((kind, text))
    return out


class Parser:
    def __init__(self, source: str) -> None:
        self.tokens = tokenize(source)
        self.at = 0

    # ------------------------------------------------------------- helpers

    def peek(self) -> tuple[str, str]:
        return self.tokens[self.at] if self.at < len(self.tokens) else ("eof", "")

    def take(self) -> tuple[str, str]:
        token = self.peek()
        self.at += 1
        return token

    def at_text(self, *texts: str) -> bool:
        return self.peek()[1] in texts

    def expect(self, text: str) -> None:
        _kind, got = self.take()
        if got != text:
            raise ParseError(f"expected {text!r}, found {got!r}")

    def name(self) -> str:
        kind, text = self.take()
        if kind != "name":
            raise ParseError(f"expected a name, found {text!r}")
        return text

    # ------------------------------------------------------------ grammar

    def program(self) -> Program:
        block = self.block()
        self.expect(".")
        if self.peek()[0] != "eof":
            raise ParseError(f"trailing input at {self.peek()[1]!r}")
        return Program(block=block)

    def block(self) -> Block:
        out = Block()
        if self.at_text("const"):
            self.take()
            while True:
                name = self.name()
                self.expect("=")
                out.consts.append(Const(name=name, value=self.number()))
                if not self.at_text(","):
                    break
                self.take()
            self.expect(";")
        if self.at_text("var"):
            self.take()
            while True:
                out.variables.append(Var(name=self.name()))
                if not self.at_text(","):
                    break
                self.take()
            self.expect(";")
        while self.at_text("procedure"):
            self.take()
            name = self.name()
            self.expect(";")
            out.procedures.append(Procedure(name=name, block=self.block()))
            self.expect(";")
        out.body = self.statement()
        return out

    def number(self) -> int:
        kind, text = self.take()
        if kind != "num":
            raise ParseError(f"expected a number, found {text!r}")
        return int(text)

    def statement(self):
        """Dispatch on the lookahead token: its kind for an assignment, its
        text for every keyword form. Anything else is the empty statement,
        which is how `if c then ;` and a trailing `end` are legal."""
        match self.peek():
            case ("name", _):
                name = self.name()
                self.expect(":=")
                return Assign(name=name, value=self.expression())
            case (_, "call"):
                self.take()
                return Call(name=self.name())
            case (_, "!"):
                self.take()
                return Write(value=self.expression())
            case (_, "begin"):
                self.take()
                body = [self.statement()]
                while self.at_text(";"):
                    self.take()
                    body.append(self.statement())
                self.expect("end")
                return Begin(body=body)
            case (_, "if"):
                self.take()
                cond = self.condition()
                self.expect("then")
                return If(cond=cond, then=self.statement())
            case (_, "while"):
                self.take()
                cond = self.condition()
                self.expect("do")
                return While(cond=cond, body=self.statement())
            case _:
                return Empty()

    def condition(self):
        if self.at_text("odd"):
            self.take()
            return Odd(value=self.expression())
        left = self.expression()
        _kind, op = self.take()
        if op not in {"=", "#", "<", "<=", ">", ">="}:
            raise ParseError(f"expected a comparison, found {op!r}")
        return Compare(op=op, left=left, right=self.expression())

    def expression(self):
        negate = False
        if self.at_text("+", "-"):
            negate = self.take()[1] == "-"
        node = self.term()
        if negate:
            node = Neg(value=node)
        while self.at_text("+", "-"):
            op = self.take()[1]
            node = BinOp(op=op, left=node, right=self.term())
        return node

    def term(self):
        node = self.factor()
        while self.at_text("*", "/"):
            op = self.take()[1]
            node = BinOp(op=op, left=node, right=self.factor())
        return node

    def factor(self):
        match self.peek():
            case ("name", _):
                return Name(name=self.name())
            case ("num", _):
                return Number(value=self.number())
            case (_, "("):
                self.take()
                node = self.expression()
                self.expect(")")
                return node
            case (_, text):
                raise ParseError(f"expected a factor, found {text!r}")


def parse(source: str) -> Program:
    return Parser(source).program()
